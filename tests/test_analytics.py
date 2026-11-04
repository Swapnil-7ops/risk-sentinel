from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import analytics_service
from app.routes import analytics as analytics_routes


class Cursor(list):
    def limit(self, _size):
        return self

    def sort(self, *_args):
        return self


class Collection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, query=None, projection=None):
        query = query or {}
        documents = self.documents
        if "status" in query and "$in" in query["status"]:
            documents = [item for item in documents if item.get("status") in query["status"]["$in"]]
        if "residual_level" in query and "$in" in query["residual_level"]:
            documents = [item for item in documents if item.get("residual_level") in query["residual_level"]["$in"]]
        if "control_id" in query and "$in" in query["control_id"]:
            documents = [item for item in documents if item.get("control_id") in query["control_id"]["$in"]]
        if projection:
            documents = [{key: item[key] for key in projection if key in item} for item in documents]
        return Cursor(documents)

    def count_documents(self, query):
        return len(self.find(query))


def test_filter_validation_rejects_unknown_bad_dates_oversized_and_operators():
    with pytest.raises(ValueError):
        analytics_service.validate_filters({"unknown": "value"})
    with pytest.raises(ValueError):
        analytics_service.validate_filters({"date_from": "2026-99-99"})
    with pytest.raises(ValueError):
        analytics_service.validate_filters({"level": ["Low"] * 21})
    with pytest.raises(ValueError):
        analytics_service.validate_filters({"status": {"$ne": ""}})


def test_csv_export_escapes_formula_characters():
    csv_text = analytics_service.csv_response([{"title": "=SUM(A1)", "owner": "+attacker", "score": "-1", "level": "@critical"}])
    assert "'=SUM(A1)" in csv_text
    assert "'+attacker" in csv_text
    assert "'-1" in csv_text
    assert "'@critical" in csv_text


def test_summary_counts_levels_heatmap_breaches_overdue_and_coverage(monkeypatch):
    risk_id = "risk-1"
    risks = [
        {"_id": risk_id, "status": "Open", "residual_level": "Critical", "residual_likelihood": 5, "residual_impact": 5, "residual_score": 25, "asset_id": "asset-1", "created_at": datetime(2026, 11, 1, tzinfo=timezone.utc), "owner": "owner"},
        {"_id": "risk-2", "status": "Closed", "residual_level": "Low", "residual_likelihood": 1, "residual_impact": 1, "residual_score": 1, "asset_id": "asset-1", "created_at": datetime(2026, 11, 2, tzinfo=timezone.utc), "owner": "owner"},
    ]
    controls = [{"id": "A.5.1", "theme": "Organizational"}]
    mappings = [{"risk_id": risk_id, "control_id": "A.5.1", "status": "Implemented", "due_date": "2026-11-03"}]
    assets = [{"_id": "asset-1", "type": "Hardware"}]
    db = SimpleNamespace(db=SimpleNamespace(risks=Collection(risks), controls=Collection(controls), risk_controls=Collection(mappings), assets=Collection(assets)))
    monkeypatch.setattr(analytics_service, "db", db)
    monkeypatch.setattr(analytics_service, "get_appetite_threshold", lambda: 10)
    summary = analytics_service.build_summary({"date_to": "2026-11-04"})
    assert summary["kpis"]["total_open"] == 1
    assert summary["kpis"]["critical"] == 1
    assert summary["kpis"]["appetite_breaches"] == 1
    assert summary["kpis"]["overdue_treatments"] == 0
    assert summary["kpis"]["control_coverage"] > 0
    assert next(item["count"] for item in summary["heatmap"] if item["likelihood"] == 5 and item["impact"] == 5) == 1


def test_summary_filter_validation_and_total_contract(monkeypatch):
    expected = {"kpis": {"total_open": 2}, "top_risks": [], "filters": {"status": ["Open"]}}
    monkeypatch.setattr(analytics_routes, "build_summary", lambda filters: expected)
    app = analytics_routes.analytics_bp
    flask_app = __import__("app").create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "user-1"
        session["_fresh"] = True
    flask_app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="user-1", email="u@example.com", role="auditor", is_authenticated=True)
    response = client.get("/api/analytics/summary?status=Open")
    assert response.status_code == 200
    assert response.get_json()["kpis"]["total_open"] == 2


def test_bookmarks_are_owned_and_csrf_protected(monkeypatch):
    from bson import ObjectId

    owner_bookmark = {"_id": ObjectId(), "user_id": "owner", "name": "Mine", "filters": {}}
    other_bookmark = {"_id": ObjectId(), "user_id": "other", "name": "Other", "filters": {}}

    class Bookmarks:
        def find(self, query):
            return Cursor([item for item in [owner_bookmark, other_bookmark] if item["user_id"] == query["user_id"]])

        def delete_one(self, query):
            return SimpleNamespace(deleted_count=int(query["user_id"] == "owner" and query["_id"] == owner_bookmark["_id"]))

    monkeypatch.setattr(analytics_routes, "db", SimpleNamespace(db=SimpleNamespace(analytics_bookmarks=Bookmarks())))
    flask_app = __import__("app").create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    flask_app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="owner", email="u@example.com", role="auditor", is_authenticated=True)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "owner"
        session["_fresh"] = True
    listed = client.get("/analytics/bookmarks")
    assert listed.status_code == 200
    assert [item["name"] for item in listed.get_json()] == ["Mine"]
    assert client.delete(f"/analytics/bookmarks/{other_bookmark['_id']}").status_code == 404
    flask_app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/analytics/bookmarks", data={"name": "No token", "filters": "{}"}).status_code == 400


def test_csv_export_returns_download_and_logs_current_filters(monkeypatch):
    flask_app = __import__("app").create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    flask_app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="owner", email="u@example.com", role="auditor", is_authenticated=True)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "owner"
        session["_fresh"] = True
    monkeypatch.setattr(analytics_routes, "filtered_risks", lambda filters: [{"title": "=formula", "owner": "owner", "score": 5, "level": "Low"}])
    recorded = []
    monkeypatch.setattr(analytics_routes, "record_audit", lambda *args, **kwargs: recorded.append(kwargs))
    response = client.get("/analytics/export.csv?level=Low")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    assert "'=formula" in response.get_data(as_text=True)
    assert recorded and recorded[0]["new_value"]["filters"]["level"] == ["Low"]

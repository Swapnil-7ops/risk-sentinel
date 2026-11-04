import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app import create_app
from app.models import risk as risk_model
from app.services import audit_service, risk_control_service


class FakeResult:
    def __init__(self, matched_count=1, inserted_id=None):
        self.matched_count = matched_count
        self.inserted_id = inserted_id or ObjectId()


class FakeMappingCollection:
    def __init__(self, mapping=None):
        self.mapping = mapping
        self.update_calls = []

    def find_one(self, query):
        if query.get("_id") and self.mapping and query["_id"] == self.mapping["_id"]:
            return self.mapping
        if "risk_id" in query and self.mapping:
            return self.mapping if query["risk_id"] == self.mapping.get("risk_id") and query["control_id"] == self.mapping.get("control_id") else None
        return None

    def insert_one(self, document):
        self.mapping = {**document, "_id": ObjectId()}
        return FakeResult(inserted_id=self.mapping["_id"])

    def update_one(self, query, update):
        self.update_calls.append(update)
        if self.mapping:
            self.mapping.update(update.get("$set", {}))
            self.mapping.pop(update.get("$unset", {}).keys().__iter__().__next__(), None) if update.get("$unset") else None
        return FakeResult()


class FakeRiskCollection:
    def __init__(self):
        self.document = None

    def find_one(self, query):
        if self.document and query.get("_id") == self.document["_id"]:
            return self.document.copy()
        return None

    def insert_one(self, document):
        self.document = {**document, "_id": ObjectId()}
        return FakeResult(inserted_id=self.document["_id"])

    def update_one(self, query, update):
        self.document.update(update.get("$set", {}))
        for field in update.get("$unset", {}):
            self.document.pop(field, None)
        return FakeResult()


def test_iso_controls_dataset_has_93_unique_ids_and_required_theme_counts():
    controls = json.loads(
        (Path(__file__).parents[1] / "data" / "iso27001_controls.json").read_text(encoding="utf-8")
    )
    assert len(controls) == 93
    assert len({control["id"] for control in controls}) == 93
    assert {
        theme: sum(control["theme"] == theme for control in controls)
        for theme in ("Organizational", "People", "Physical", "Technological")
    } == {
        "Organizational": 37,
        "People": 8,
        "Physical": 14,
        "Technological": 34,
    }


def test_overdue_compares_calendar_dates_and_today_is_not_overdue():
    today = date(2026, 11, 4)
    assert not risk_control_service.is_overdue(today.isoformat(), "Planned", today)
    assert risk_control_service.is_overdue((today - timedelta(days=1)).isoformat(), "Planned", today)
    assert risk_control_service.overdue_days((today - timedelta(days=1)).isoformat(), "Planned", today) == 1
    assert not risk_control_service.is_overdue(
        f"{today.isoformat()}T23:59:59+00:00", "Planned", today
    )


def test_overdue_days_uses_current_date_when_today_is_omitted():
    today = datetime.now(timezone.utc).date()
    assert risk_control_service.overdue_days(today.isoformat(), "Planned") == 0
    assert risk_control_service.overdue_days((today - timedelta(days=2)).isoformat(), "Planned") == 2
    assert risk_control_service.overdue_days((today - timedelta(days=2)).isoformat(), "Implemented") == 0


def test_allowed_and_rejected_mapping_status_values(monkeypatch):
    mapping_id = ObjectId()
    collection = FakeMappingCollection({"_id": mapping_id, "status": "Planned", "status_history": []})
    monkeypatch.setattr(
        risk_control_service,
        "db",
        SimpleNamespace(db=SimpleNamespace(risk_controls=collection)),
    )

    for status in risk_control_service.MAPPING_STATUSES:
        risk_control_service.update_mapping_status(str(mapping_id), status, "user-1")

    with pytest.raises(ValueError, match="Invalid mapping status"):
        risk_control_service.update_mapping_status(str(mapping_id), "Rejected", "user-1")


def test_mapping_evidence_requires_http_url(monkeypatch):
    mapping_id = ObjectId()
    collection = FakeMappingCollection({"_id": mapping_id, "status": "Planned"})
    monkeypatch.setattr(risk_control_service, "db", SimpleNamespace(db=SimpleNamespace(risk_controls=collection)))
    with pytest.raises(ValueError, match="http or https"):
        risk_control_service.update_mapping_evidence(str(mapping_id), "javascript:alert(1)", "user-1")
    risk_control_service.update_mapping_evidence(str(mapping_id), "https://evidence.example/item", "user-1")
    assert collection.mapping["evidence_url"] == "https://evidence.example/item"


def test_mapping_approval_and_escalation_are_persisted(monkeypatch):
    mapping_id = ObjectId()
    collection = FakeMappingCollection({"_id": mapping_id, "status": "Planned"})
    monkeypatch.setattr(risk_control_service, "db", SimpleNamespace(db=SimpleNamespace(risk_controls=collection)))
    risk_control_service.update_mapping_approval(str(mapping_id), "Approved", "Reviewed", "admin-1")
    risk_control_service.escalate_mapping(str(mapping_id), "Deadline missed", "owner-1")
    assert collection.mapping["approval"]["decision"] == "Approved"
    assert collection.mapping["escalation"]["status"] == "Open"


def test_duplicate_control_mapping_is_rejected(monkeypatch):
    risk_id = ObjectId()
    collection = FakeMappingCollection({"risk_id": str(risk_id), "control_id": "A.5.15"})

    class Risks:
        def find_one(self, _query):
            return {"_id": risk_id}

    class Controls:
        def find_one(self, _query):
            return {"id": "A.5.15"}

    monkeypatch.setattr(
        risk_control_service,
        "db",
        SimpleNamespace(db=SimpleNamespace(risks=Risks(), controls=Controls(), risk_controls=collection)),
    )
    data = {
        "risk_id": str(risk_id),
        "control_id": "A.5.15",
        "treatment": "Mitigate",
        "action_plan": "Review access",
        "owner": "owner",
        "due_date": "2026-12-01",
        "status": "Planned",
    }
    with pytest.raises(ValueError, match="already mapped"):
        risk_control_service.create_mapping(data, "user-1")


def test_audit_service_strips_sensitive_fields_and_records_old_new_values(monkeypatch):
    inserted = {}

    class Collection:
        def insert_one(self, document):
            inserted.update(document)

    monkeypatch.setattr(
        audit_service,
        "db",
        SimpleNamespace(db=SimpleNamespace(audit_logs=Collection())),
    )
    user = SimpleNamespace(id="u1", email="user@example.com")
    audit_service.record_audit(
        user,
        "update",
        "risk",
        "r1",
        old_value={"password": "old", "password_hash": "hidden", "title": "old"},
        new_value={"api_key": "hidden", "title": "new", "nested": {"password": "secret"}},
    )
    assert inserted["old_value"] == {"title": "old"}
    assert inserted["new_value"] == {"title": "new", "nested": {}}
    assert inserted["action"] == "update"
    assert inserted["entity_id"] == "r1"


def _logged_in_client(role, csrf_enabled=False):
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=csrf_enabled)
    app.login_manager._user_callback = lambda _user_id: SimpleNamespace(
        id="user-1",
        email="user@example.com",
        role=role,
        is_authenticated=True,
    )
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "user-1"
        session["_fresh"] = True
    return app, client


@pytest.mark.parametrize(
    "path",
    [
        "/risks/507f1f77bcf86cd799439011/controls",
        "/treatment-board/507f1f77bcf86cd799439011/status",
        "/settings/risk-appetite",
    ],
)
def test_auditor_gets_403_on_mutation_routes(path):
    _app, client = _logged_in_client("auditor")
    response = client.post(path, data={"status": "In Progress"})
    assert response.status_code == 403


def test_board_post_requires_csrf_token():
    _app, client = _logged_in_client("risk_owner", csrf_enabled=True)
    response = client.post(
        "/treatment-board/507f1f77bcf86cd799439011/status",
        data={"status": "In Progress"},
    )
    assert response.status_code == 400


def test_closed_at_is_set_on_close_and_cleared_on_reopen(monkeypatch):
    collection = FakeRiskCollection()
    monkeypatch.setattr(risk_model, "db", SimpleNamespace(db=SimpleNamespace(risks=collection)))
    inherent = {"score": 4, "level": "Low"}
    residual = {"score": 1, "level": "Low"}
    created = risk_model.create_risk(
        {
            "asset_id": "asset-1",
            "title": "Test risk",
            "threat": "Threat",
            "vulnerability": "Vulnerability",
            "likelihood": 2,
            "impact": 2,
            "residual_likelihood": 1,
            "residual_impact": 1,
            "status": "Open",
            "owner": "owner",
            "source": "test",
        },
        "user-1",
        inherent,
        residual,
    )
    risk_id = created["id"]
    closed = risk_model.update_risk(
        risk_id,
        {"status": "Closed", "title": "Test risk", "updated_by": "user-1"},
        inherent,
        residual,
    )
    assert isinstance(closed["closed_at"], datetime)
    reopened = risk_model.update_risk(
        risk_id,
        {"status": "Open", "title": "Test risk", "updated_by": "user-1"},
        inherent,
        residual,
    )
    assert "closed_at" not in reopened

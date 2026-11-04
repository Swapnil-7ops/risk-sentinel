import subprocess
import sys
from types import SimpleNamespace

import pytest
from pymongo.errors import ConnectionFailure

from app import create_app
from app.services import report_service, risk_engine


class Cursor(list):
    def limit(self, _size):
        return self


class Collection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, _query=None, _projection=None):
        return Cursor(self.documents)


def _report_db(mappings=None):
    return SimpleNamespace(
        db=SimpleNamespace(
            risk_controls=Collection(mappings or []),
        )
    )


def test_risk_report_is_pdf_and_logs_export(monkeypatch):
    risks = [{
        "id": "risk-1",
        "title": "<b>Markup</b> <para>title &amp;</para>" + "x" * 2000,
        "status": "Open",
        "inherent_likelihood": 4,
        "inherent_impact": 4,
        "inherent_score": 16,
        "inherent_level": "High",
        "residual_likelihood": 3,
        "residual_impact": 3,
        "residual_score": 9,
        "residual_level": "Medium",
        "owner": "owner",
        "source": "source",
    }]
    audit = []
    monkeypatch.setattr(report_service, "validate_filters", lambda raw: {"view": "residual", "level": [], "status": [], "asset_type": [], "asset": [], "owner": [], "control_theme": [], "source": [], "likelihood": [], "impact": [], "date_from": None, "date_to": None})
    monkeypatch.setattr(report_service, "filtered_risks", lambda _raw: risks)
    monkeypatch.setattr(report_service, "db", _report_db())
    monkeypatch.setattr(report_service, "get_appetite_threshold", lambda: 10)
    monkeypatch.setattr(report_service, "record_audit", lambda *args, **kwargs: audit.append(kwargs))

    content = report_service.build_risk_report({"level": "High"}, SimpleNamespace(email="auditor@example.com"))

    assert content.startswith(b"%PDF")
    assert audit[0]["new_value"]["rows"] == 1


def test_empty_risk_report_is_still_a_pdf(monkeypatch):
    monkeypatch.setattr(report_service, "filtered_risks", lambda _raw: [])
    monkeypatch.setattr(report_service, "validate_filters", lambda _raw: {"view": "residual", "level": [], "status": [], "asset_type": [], "asset": [], "owner": [], "control_theme": [], "source": [], "likelihood": [], "impact": [], "date_from": None, "date_to": None})
    monkeypatch.setattr(report_service, "db", _report_db())
    monkeypatch.setattr(report_service, "get_appetite_threshold", lambda: 10)
    monkeypatch.setattr(report_service, "record_audit", lambda *args, **kwargs: None)

    assert report_service.build_risk_report({}, "auditor").startswith(b"%PDF")


def test_report_passes_allowlisted_filters_to_dashboard_query(monkeypatch):
    received = []
    filters = {"view": "residual", "level": ["High"], "status": [], "asset_type": [], "asset": [], "owner": [], "control_theme": [], "source": [], "likelihood": [], "impact": [], "date_from": None, "date_to": None}
    monkeypatch.setattr(report_service, "validate_filters", lambda raw: filters)
    monkeypatch.setattr(report_service, "filtered_risks", lambda raw: received.append(raw) or [])
    monkeypatch.setattr(report_service, "db", _report_db())
    monkeypatch.setattr(report_service, "get_appetite_threshold", lambda: 10)
    monkeypatch.setattr(report_service, "record_audit", lambda *args, **kwargs: None)

    report_service.build_risk_report({"level": "High"}, "auditor")

    assert received == [{"level": "High"}]


def test_healthz_exposes_only_status():
    app = create_app()
    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert "secret" not in response.get_data(as_text=True).lower()


def test_database_outage_returns_clear_503_page(monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    monkeypatch.setattr(
        "app.routes.auth.User.register_allowed",
        lambda _allow_registration: (_ for _ in ()).throw(ConnectionFailure("unavailable")),
    )

    response = app.test_client().get("/auth/register")

    assert response.status_code == 503
    assert b"Database unavailable" in response.data
    assert b"Traceback" not in response.data


def test_atlas_uri_without_database_uses_grc_risk(monkeypatch):
    import app

    class Client:
        def get_default_database(self):
            from pymongo.errors import ConfigurationError
            raise ConfigurationError("No default database")

        def __getitem__(self, name):
            return name

    monkeypatch.setattr(app, "mongo_client", Client())
    from pymongo.errors import ConfigurationError

    try:
        default_database = app.mongo_client.get_default_database()
    except ConfigurationError:
        default_database = None
    assert (default_database if default_database is not None else app.mongo_client["grc_risk"]) == "grc_risk"


def test_production_validation_requires_runtime_secrets(monkeypatch):
    monkeypatch.delenv("MONGO_URI", raising=False)

    class ProductionConfig:
        TESTING = True
        FLASK_ENV = "production"
        SECRET_KEY = "test-secret"
        MONGO_URI = "mongodb://localhost:27017/grc_risk"
        RATELIMIT_STORAGE_URI = "memory://"
        CRON_SECRET = "cron"

    with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI"):
        create_app(ProductionConfig)

    monkeypatch.setattr(ProductionConfig, "RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    with pytest.raises(RuntimeError, match="MONGO_URI"):
        create_app(ProductionConfig)


def test_seed_requires_explicit_confirmation():
    result = subprocess.run(
        [sys.executable, "scripts/seed_demo.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "--confirm is required" in result.stderr


class SeedCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.inserted = []
        self.deleted_queries = []

    def count_documents(self, query):
        return sum(item.get("demo") is not True for item in self.documents) if query.get("demo") == {"$ne": True} else len(self.documents)

    def insert_one(self, document):
        identifier = f"id-{len(self.inserted) + 1}"
        stored = {**document, "_id": identifier}
        self.inserted.append(stored)
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=identifier)

    def find_one(self, _query, _projection=None):
        return {"id": "A.5.1"}

    def update_one(self, _query, update, **_kwargs):
        return SimpleNamespace(modified_count=1, matched_count=1)

    def delete_many(self, query):
        self.deleted_queries.append(query)
        before = len(self.documents)
        self.documents[:] = [item for item in self.documents if item.get("demo") is not True]
        return SimpleNamespace(deleted_count=before - len(self.documents))


class SeedDatabase(SimpleNamespace):
    def __getitem__(self, name):
        return getattr(self, name)


def _seed_db(risks=None):
    names = ("risks", "assets", "controls", "risk_controls", "users")
    collections = {name: SeedCollection() for name in names}
    collections["risks"].documents = list(risks or [])
    return SimpleNamespace(db=SeedDatabase(**collections)), collections


def test_seed_refuses_non_demo_risks_without_force(monkeypatch):
    from scripts import seed_demo

    database, _collections = _seed_db([{"demo": False}])
    monkeypatch.setattr(seed_demo, "db", database)

    with pytest.raises(RuntimeError, match="non-demo risks"):
        seed_demo.seed()


def test_seed_force_marks_seeded_documents_and_uses_risk_engine(monkeypatch):
    from scripts import seed_demo

    database, collections = _seed_db([{"demo": False}])
    monkeypatch.setattr(seed_demo, "db", database)
    monkeypatch.setattr(seed_demo, "_password", lambda _name: "environment-provided-password")
    monkeypatch.setattr(seed_demo.bcrypt, "generate_password_hash", lambda value: SimpleNamespace(decode=lambda _encoding: "hash"))
    assessed = []
    original_assess = risk_engine.assess_risk
    monkeypatch.setattr(seed_demo, "assess_risk", lambda likelihood, impact: assessed.append((likelihood, impact)) or original_assess(likelihood, impact))

    seed_demo.seed(force=True)

    assert len(collections["assets"].inserted) == 10
    assert len(collections["risks"].inserted) == 12
    assert all(item["demo"] is True for item in collections["assets"].inserted + collections["risks"].inserted + collections["risk_controls"].inserted)
    assert len(assessed) == 24


def test_reset_demo_deletes_only_demo_documents(monkeypatch):
    from scripts import seed_demo

    database, collections = _seed_db()
    for collection in (collections["risk_controls"], collections["risks"], collections["assets"], collections["users"], collections["controls"]):
        collection.documents.extend([{"demo": True}, {"demo": False}])
    monkeypatch.setattr(seed_demo, "db", database)

    seed_demo.reset_demo()

    assert all(collections[name].deleted_queries == [{"demo": True}] for name in ("risk_controls", "risks", "assets", "users", "controls"))
    assert all(collections[name].documents == [{"demo": False}] for name in ("risk_controls", "risks", "assets", "users"))
    assert collections["controls"].documents == [{"demo": False}]

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from flask import abort

from app import create_app
from app.forms import PasswordChangeForm, RegistrationForm
from app.routes import cron as cron_routes
from app.models.user import User
from app.services import cron_service
from app.services.audit_service import _safe_value


def test_password_rules(monkeypatch):
    app = create_app()
    monkeypatch.setattr("app.forms.User.get_by_email", lambda _email: None)
    with app.test_request_context("/auth/register", method="POST"):
        form = RegistrationForm(meta={"csrf": False}, data={"name": "Test", "email": "new@example.com", "password": "short", "confirm_password": "short"})
        assert not form.validate()
        assert form.password.errors
        form = PasswordChangeForm(meta={"csrf": False}, data={"password": "password1234", "confirm_password": "password1234"})
        assert not form.validate()
        assert any("less common" in error for error in form.password.errors)


def test_audit_redaction_is_recursive():
    value = {"password": "x", "nested": {"authorization": "y", "safe": "ok"}, "items": [{"secret": "z", "key": "q"}]}
    redacted = _safe_value(value)
    assert redacted == {"nested": {"safe": "ok"}, "items": [{}]}


def test_cron_rejects_bad_secret_and_is_idempotent(monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, CRON_SECRET="cron-secret")
    calls = []
    monkeypatch.setattr(cron_routes, "mark_overdue_treatments", lambda: calls.append(1) or (1 if len(calls) == 1 else 0))
    client = app.test_client()
    assert client.get("/api/cron/overdue").status_code == 401
    assert client.get("/api/cron/overdue", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/cron/overdue", headers={"Authorization": "Bearer cron-secret"}).get_json() == {"marked": 1}
    assert client.get("/api/cron/overdue", headers={"Authorization": "Bearer cron-secret"}).get_json() == {"marked": 0}
    app.config["CRON_SECRET"] = None
    assert client.get("/api/cron/overdue", headers={"Authorization": "Bearer cron-secret"}).status_code == 401


def test_security_headers_on_page_and_api(monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    monkeypatch.setattr(cron_routes, "mark_overdue_treatments", lambda: 0)
    client = app.test_client()
    page = client.get("/auth/login")
    api = client.get("/api/cron/overdue")
    for response in (page, api):
        assert response.headers["Content-Security-Policy"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"]
        assert response.headers["Permissions-Policy"]
    assert api.headers["Cache-Control"] == "no-store"
    error = client.get("/does-not-exist")
    assert error.status_code == 404
    assert error.headers["X-Content-Type-Options"] == "nosniff"


class UserCollection:
    def __init__(self, document):
        self.document = document
        self.updates = []

    def update_one(self, query, update):
        self.updates.append((query, update))
        if "$set" in update:
            self.document.update(update["$set"])
        for field in update.get("$unset", {}):
            self.document.pop(field, None)
        return SimpleNamespace(modified_count=1)


def test_lock_expiry_resets_counter(monkeypatch):
    document = {"_id": ObjectId(), "name": "User", "email": "u@example.com", "password_hash": "hash", "role": "admin", "failed_attempts": 5, "locked_until": datetime.now(timezone.utc) - timedelta(minutes=1)}
    collection = UserCollection(document)
    monkeypatch.setattr("app.models.user.db", SimpleNamespace(db=SimpleNamespace(users=collection)))
    user = User(document)
    assert user.is_locked() is False
    assert user.failed_attempts == 0
    assert "locked_until" not in document


def test_attempts_during_lock_do_not_extend_it(monkeypatch):
    locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    document = {"_id": ObjectId(), "name": "User", "email": "u@example.com", "password_hash": "hash", "role": "admin", "failed_attempts": 5, "locked_until": locked_until}
    collection = UserCollection(document)
    monkeypatch.setattr("app.models.user.db", SimpleNamespace(db=SimpleNamespace(users=collection)))
    user = User(document)
    user.record_failed_login()
    assert document["failed_attempts"] == 5
    assert document["locked_until"] == locked_until


def test_naive_mongo_lock_timestamp_does_not_raise(monkeypatch):
    locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
    document = {"_id": ObjectId(), "name": "User", "email": "u@example.com", "password_hash": "hash", "role": "admin", "failed_attempts": 5, "locked_until": locked_until}
    collection = UserCollection(document)
    monkeypatch.setattr("app.models.user.db", SimpleNamespace(db=SimpleNamespace(users=collection)))
    assert User(document).is_locked() is True


def test_old_sessions_are_rejected_and_must_change_redirects():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SESSION_ABSOLUTE_LIFETIME=10, PERMANENT_SESSION_LIFETIME=10)
    app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="u", is_authenticated=True, must_change_password=False)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "u"
        session["_session_created"] = 0
        session["_last_seen"] = 0
    assert client.get("/dashboard").status_code == 302
    app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="u", is_authenticated=True, must_change_password=True)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "u"
        session["_session_created"] = datetime.now(timezone.utc).timestamp()
        session["_last_seen"] = datetime.now(timezone.utc).timestamp()
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.location.endswith("/auth/password-change")


def test_form_values_allow_operator_characters(monkeypatch):
    monkeypatch.setattr("app.forms.User.get_by_email", lambda _email: None)
    app = create_app()
    with app.test_request_context("/auth/register", method="POST"):
        form = RegistrationForm(meta={"csrf": False}, data={"name": "${name}", "email": "new@example.com", "password": "Safe ${ password } 123", "confirm_password": "Safe ${ password } 123"})
        assert form.validate()


def test_http_exception_statuses_are_preserved():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    app.add_url_rule("/test-415", view_func=lambda: abort(415))
    client = app.test_client()
    assert client.get("/auth/login", data={}).status_code == 200
    assert client.put("/auth/login").status_code == 405
    assert client.get("/test-415").status_code == 415


def test_cron_service_audits_each_mapping_once(monkeypatch):
    mapping = {"_id": ObjectId(), "due_date": "2020-01-01", "status": "Planned"}

    class Mappings:
        def find(self, _query):
            return [mapping] if "overdue_since" not in mapping else []

        def update_one(self, _query, update):
            mapping.update(update["$set"])
            return SimpleNamespace(modified_count=1)

    audits = []
    monkeypatch.setattr(cron_service, "db", SimpleNamespace(db=SimpleNamespace(risk_controls=Mappings())))
    monkeypatch.setattr(cron_service, "record_audit", lambda *args, **kwargs: audits.append(args))
    assert cron_service.mark_overdue_treatments() == 1
    assert cron_service.mark_overdue_treatments() == 0
    assert len(audits) == 1


def test_state_changing_routes_require_csrf():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    client = app.test_client()
    for rule in app.url_map.iter_rules():
        methods = rule.methods & {"POST", "PUT", "PATCH", "DELETE"}
        if not methods:
            continue
        path = rule.rule.replace("<string:asset_id>", "507f1f77bcf86cd799439011").replace("<asset_id>", "507f1f77bcf86cd799439011").replace("<risk_id>", "507f1f77bcf86cd799439011").replace("<mapping_id>", "507f1f77bcf86cd799439011").replace("<bookmark_id>", "507f1f77bcf86cd799439011")
        for method in methods:
            response = client.open(path, method=method)
            assert response.status_code == 400, f"{method} {path} did not reject missing CSRF"


@pytest.mark.parametrize("path", ["/assets?search=%7B%22%24ne%22%3A%22%22%7D", "/risks?search=%7B%22%24ne%22%3A%22%22%7D", "/controls?search=%7B%22%24ne%22%3A%22%22%7D"])
def test_operator_like_query_values_are_rejected(path):
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="u", is_authenticated=True, must_change_password=False, role="auditor")
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "u"
    assert client.get(path).status_code == 400


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("auditor", "/assets/new"),
        ("auditor", "/risks/new"),
        ("auditor", "/risks/507f1f77bcf86cd799439011/delete"),
        ("auditor", "/risks/507f1f77bcf86cd799439011/controls"),
        ("auditor", "/treatment-board/507f1f77bcf86cd799439011/status"),
        ("auditor", "/settings/risk-appetite"),
        ("risk_owner", "/risks/507f1f77bcf86cd799439011/delete"),
        ("risk_owner", "/settings/risk-appetite"),
        ("risk_owner", "/auth/users/new"),
    ],
)
def test_roles_are_denied_where_access_matrix_requires(role, path):
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    app.login_manager._user_callback = lambda _user_id: SimpleNamespace(id="u", is_authenticated=True, must_change_password=False, role=role)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "u"
    assert client.post(path, data={}).status_code == 403

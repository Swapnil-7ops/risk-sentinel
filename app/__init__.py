from datetime import datetime, timezone
from types import SimpleNamespace

import logging
import json
import os
import time
import uuid
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException

from config import Config

bcrypt = Bcrypt()
csrf = CSRFProtect()
mongo_client = MongoClient(
    Config.MONGO_URI,
    maxPoolSize=10,
    serverSelectionTimeoutMS=5000,
)
try:
    default_database = mongo_client.get_default_database()
except ConfigurationError:
    default_database = None
db = SimpleNamespace(db=default_database if default_database is not None else mongo_client["grc_risk"])
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        })


def create_app(config_class=Config):
    app = Flask(__name__, static_folder="../public/static", static_url_path="/static")
    app.config.from_object(config_class)
    if app.config.get("FLASK_ENV") == "production":
        required = ("SECRET_KEY", "MONGO_URI", "RATELIMIT_STORAGE_URI", "CRON_SECRET")
        missing = [
            name for name in required
            if not app.config.get(name)
            or (name == "MONGO_URI" and app.config[name] == "mongodb://localhost:27017/grc_risk" and not os.getenv(name))
            or (name == "RATELIMIT_STORAGE_URI" and app.config[name] == "memory://")
        ]
        if missing:
            raise RuntimeError("Missing production environment variables: " + ", ".join(missing))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    logger = logging.getLogger("risk_sentinel")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    bcrypt.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    app.config["SESSION_COOKIE_NAME"] = "risk_sentinel_session"

    @app.before_request
    def enforce_session_lifetime():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        if not session.get("_user_id"):
            return None
        now = time.time()
        created = session.get("_session_created", now)
        last_seen = session.get("_last_seen", now)
        if now - created > app.config.get("SESSION_ABSOLUTE_LIFETIME", 28800) or now - last_seen > app.config.get("PERMANENT_SESSION_LIFETIME", 1800):
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized."}), 401
            return login_manager.unauthorized()
        session["_last_seen"] = now
        session.permanent = True
        from flask_login import current_user
        if current_user.is_authenticated and not getattr(current_user, "is_active", True):
            session.clear()
            return login_manager.unauthorized()
        if current_user.is_authenticated and getattr(current_user, "must_change_password", False) and request.endpoint not in {"auth.change_password", "auth.logout"} and not request.path.startswith("/static/"):
            return redirect(url_for("auth.change_password"))
        return None

    from app.routes.auth import auth_bp
    from app.routes.assets import assets_bp
    from app.routes.errors import errors_bp
    from app.routes.risks import risks_bp
    from app.routes.controls import controls_bp
    from app.routes.analytics import analytics_bp
    from app.routes.cron import cron_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(errors_bp)
    app.register_blueprint(risks_bp)
    app.register_blueprint(controls_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(cron_bp)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.context_processor
    def provide_asset_url():
        def asset_url(path):
            return f"/static/{path.lstrip('/')}?v=20261104-4"

        return {"asset_url": asset_url, "now_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Request-ID"] = g.get("request_id", uuid.uuid4().hex)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config.get("FLASK_ENV") == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if current_user_is_authenticated():
            response.headers.setdefault("Cache-Control", "no-store")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    def current_user_is_authenticated():
        return bool(session.get("_user_id"))

    @app.errorhandler(ConnectionFailure)
    def handle_database_error(error):
        logging.getLogger("risk_sentinel").error("Database unavailable: %s", type(error).__name__, extra={"request_id": g.get("request_id")})
        if request.path.startswith("/api/"):
            return jsonify({"error": "Database temporarily unavailable."}), 503
        return render_template("errors/503.html"), 503

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise error
        logging.getLogger("risk_sentinel").error("Unhandled application error: %s", type(error).__name__, extra={"request_id": g.get("request_id")})
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error."}), 500
        return render_template("errors/500.html"), 500

    return app


from app.models.user import User  # noqa: E402


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

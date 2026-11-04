import os

from dotenv import load_dotenv

load_dotenv()

FLASK_ENV = os.getenv("FLASK_ENV", "development").lower()
SECRET_KEY = os.getenv("SECRET_KEY")
if FLASK_ENV == "production" and not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set when FLASK_ENV=production.")


class Config:
    SECRET_KEY = SECRET_KEY or "local-development-only-secret"
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/grc_risk")
    FLASK_ENV = FLASK_ENV
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if FLASK_ENV == "production" else "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 1800
    SESSION_ABSOLUTE_LIFETIME = 28800
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"
    CRON_SECRET = os.getenv("CRON_SECRET")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM = os.getenv("SMTP_FROM")
    PASSWORD_RESET_TTL_MINUTES = 30
    EMAIL_VERIFICATION_TTL_HOURS = 24

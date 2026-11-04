import hmac

from flask import Blueprint, current_app, jsonify, request

from app.services.cron_service import mark_overdue_treatments

cron_bp = Blueprint("cron", __name__)


@cron_bp.get("/api/cron/overdue")
def overdue():
    expected = current_app.config.get("CRON_SECRET")
    supplied = request.headers.get("Authorization", "")
    valid = bool(expected) and hmac.compare_digest(supplied, f"Bearer {expected}")
    if not valid:
        return jsonify({"error": "Unauthorized."}), 401
    return jsonify({"marked": mark_overdue_treatments()})

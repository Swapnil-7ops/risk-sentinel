from copy import deepcopy
from datetime import datetime, timezone

from app import db

SENSITIVE_FIELDS = {"password", "password_hash", "token", "secret", "key", "authorization", "api_key"}


def _safe_value(value):
    if isinstance(value, dict):
        return {
            key: _safe_value(item)
            for key, item in value.items()
            if key.lower() not in SENSITIVE_FIELDS
        }
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return deepcopy(value)


def record_audit(user, action, entity_type, entity_id, old_value=None, new_value=None):
    if action not in {"create", "update", "delete"}:
        raise ValueError("Invalid audit action.")
    document = {
        "user_id": str(user.id) if user else None,
        "user_email": user.email if user else None,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "old_value": _safe_value(old_value),
        "new_value": _safe_value(new_value),
        "timestamp": datetime.now(timezone.utc),
    }
    return db.db.audit_logs.insert_one(document)


def list_audit_logs(page=1, per_page=20, user_id=None, entity_type=None, action=None, search=None):
    query = {}
    if user_id:
        query["user_id"] = user_id
    if entity_type in {"asset", "risk", "risk_control", "setting", "user", "analytics_export", "analytics_bookmark"}:
        query["entity_type"] = entity_type
    if action in {"create", "update", "delete"}:
        query["action"] = action
    if search:
        query["$or"] = [
            {"user_email": {"$regex": search.strip(), "$options": "i"}},
            {"entity_id": {"$regex": search.strip(), "$options": "i"}},
        ]
    total = db.db.audit_logs.count_documents(query)
    cursor = db.db.audit_logs.find(query).sort("timestamp", -1).skip((page - 1) * per_page).limit(per_page)
    return [dict(item, id=str(item.pop("_id"))) for item in cursor], total

from datetime import datetime, timezone

from app import db
from app.services.audit_service import record_audit


def mark_overdue_treatments():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mappings = db.db.risk_controls.find({
        "due_date": {"$lt": today},
        "status": {"$ne": "Implemented"},
        "overdue_since": {"$exists": False},
    })
    count = 0
    for mapping in mappings:
        result = db.db.risk_controls.update_one(
            {"_id": mapping["_id"], "overdue_since": {"$exists": False}},
            {"$set": {"overdue_since": today}},
        )
        if result.modified_count:
            record_audit(None, "update", "risk_control", mapping["_id"], old_value=mapping, new_value={"overdue_since": today})
            count += 1
    return count

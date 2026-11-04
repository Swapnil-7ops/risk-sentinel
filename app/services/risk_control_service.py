from datetime import date, datetime, timezone
from urllib.parse import urlparse

from bson import ObjectId
from bson.errors import InvalidId

from app import db

TREATMENTS = ("Mitigate", "Accept", "Transfer", "Avoid")
MAPPING_STATUSES = ("Planned", "In Progress", "Implemented")


def _calendar_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def is_overdue(due_date, status, today=None):
    if not due_date or status == "Implemented":
        return False
    today = today or datetime.now(timezone.utc).date()
    return _calendar_date(due_date) < _calendar_date(today)


def overdue_days(due_date, status, today=None):
    today = today or datetime.now(timezone.utc).date()
    if not is_overdue(due_date, status, today):
        return 0
    return (_calendar_date(today) - _calendar_date(due_date)).days


def validate_object_id(value):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise ValueError("Invalid identifier.")


def validate_mapping(data):
    validate_object_id(data["risk_id"])
    if not db.db.risks.find_one({"_id": ObjectId(data["risk_id"])}):
        raise ValueError("Risk does not exist.")
    if not db.db.controls.find_one({"id": data["control_id"]}):
        raise ValueError("Control does not exist.")
    if data["treatment"] not in TREATMENTS or data["status"] not in MAPPING_STATUSES:
        raise ValueError("Invalid treatment or status.")
    if data.get("due_date"):
        datetime.strptime(data["due_date"], "%Y-%m-%d")
    if db.db.risk_controls.find_one({"risk_id": data["risk_id"], "control_id": data["control_id"]}):
        raise ValueError("This control is already mapped to the risk.")


def create_mapping(data, user_id):
    validate_mapping(data)
    now = datetime.now(timezone.utc)
    document = {**data, "created_by": user_id, "created_at": now, "updated_at": now, "status_history": [{"status": data["status"], "changed_at": now, "changed_by": user_id}]}
    if data["status"] == "Implemented":
        document["implemented_at"] = now
    return db.db.risk_controls.insert_one(document)


def list_mappings(risk_id=None, owner=None, theme=None, overdue=False):
    query = {}
    if risk_id:
        query["risk_id"] = risk_id
    if owner:
        query["owner"] = owner
    if theme in ("Organizational", "People", "Physical", "Technological"):
        controls = [item["id"] for item in db.db.controls.find({"theme": theme}, {"id": 1})]
        query["control_id"] = {"$in": controls}
    if overdue:
        query["due_date"] = {"$lt": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        query["status"] = {"$ne": "Implemented"}
    mappings = list(db.db.risk_controls.find(query).sort("due_date", 1))
    for mapping in mappings:
        mapping["id"] = str(mapping.pop("_id"))
    return mappings


def update_mapping_status(mapping_id, status, user_id):
    if status not in MAPPING_STATUSES:
        raise ValueError("Invalid mapping status.")
    mapping = db.db.risk_controls.find_one({"_id": validate_object_id(mapping_id)})
    if not mapping:
        raise ValueError("Mapping does not exist.")
    now = datetime.now(timezone.utc)
    update = {"$set": {"status": status, "updated_at": now}, "$push": {"status_history": {"status": status, "changed_at": now, "changed_by": user_id}}}
    if status == "Implemented":
        update["implemented_at"] = now
    else:
        update["$unset"] = {"implemented_at": ""}
    db.db.risk_controls.update_one({"_id": mapping["_id"]}, update)
    return mapping


def update_mapping_evidence(mapping_id, evidence_url, user_id):
    parsed = urlparse(evidence_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Evidence must be an http or https URL.")
    mapping = db.db.risk_controls.find_one({"_id": validate_object_id(mapping_id)})
    if not mapping:
        raise ValueError("Mapping does not exist.")
    now = datetime.now(timezone.utc)
    db.db.risk_controls.update_one(
        {"_id": mapping["_id"]},
        {"$set": {"evidence_url": evidence_url.strip(), "evidence_updated_at": now, "evidence_updated_by": user_id, "updated_at": now}},
    )
    return mapping


def update_mapping_approval(mapping_id, decision, comment, user_id):
    if decision not in {"Approved", "Rejected"}:
        raise ValueError("Invalid approval decision.")
    mapping = db.db.risk_controls.find_one({"_id": validate_object_id(mapping_id)})
    if not mapping:
        raise ValueError("Mapping does not exist.")
    now = datetime.now(timezone.utc)
    approval = {"decision": decision, "comment": comment.strip(), "approved_by": user_id, "approved_at": now}
    db.db.risk_controls.update_one(
        {"_id": mapping["_id"]},
        {"$set": {"approval": approval, "updated_at": now}},
    )
    return mapping


def escalate_mapping(mapping_id, reason, user_id):
    mapping = db.db.risk_controls.find_one({"_id": validate_object_id(mapping_id)})
    if not mapping:
        raise ValueError("Mapping does not exist.")
    now = datetime.now(timezone.utc)
    escalation = {"reason": reason.strip(), "escalated_by": user_id, "escalated_at": now, "status": "Open"}
    db.db.risk_controls.update_one(
        {"_id": mapping["_id"]},
        {"$set": {"escalation": escalation, "updated_at": now}},
    )
    return mapping

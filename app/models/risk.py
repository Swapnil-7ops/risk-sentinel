from datetime import datetime, timezone
import re

from bson import ObjectId
from bson.errors import InvalidId

from app import db


def _serialize(document):
    if not document:
        return None
    document = dict(document)
    document["id"] = str(document.pop("_id"))
    return document


def list_risks(search=None, status=None, level=None, page=1, per_page=10, sort="updated_at", direction="desc"):
    query = {}
    if search:
        expression = re.escape(search.strip())
        query["$or"] = [{"title": {"$regex": expression, "$options": "i"}}, {"threat": {"$regex": expression, "$options": "i"}}]
    if status in ("Open", "In Treatment", "Closed"):
        query["status"] = status
    if level in ("Low", "Medium", "High", "Critical"):
        query["residual_level"] = level
    sort_field = sort if sort in {"title", "status", "residual_score", "updated_at"} else "updated_at"
    sort_direction = -1 if direction != "asc" else 1
    total = db.db.risks.count_documents(query)
    cursor = db.db.risks.find(query).sort(sort_field, sort_direction).skip((page - 1) * per_page).limit(per_page)
    return [_serialize(item) for item in cursor], total


def get_risk(risk_id):
    try:
        document = db.db.risks.find_one({"_id": ObjectId(risk_id)})
    except InvalidId:
        return None
    return _serialize(document)


def create_risk(data, user_id, inherent, residual):
    now = datetime.now(timezone.utc)
    document = {
        **data, "inherent_score": inherent["score"], "inherent_level": inherent["level"],
        "residual_score": residual["score"], "residual_level": residual["level"],
        "created_by": user_id, "created_at": now, "updated_at": now,
        "status_history": [{"status": data["status"], "changed_at": now, "changed_by": user_id}],
    }
    if data["status"] == "Closed":
        document["closed_at"] = now
    result = db.db.risks.insert_one(document)
    return get_risk(str(result.inserted_id))


def update_risk(risk_id, data, inherent, residual):
    try:
        old = db.db.risks.find_one({"_id": ObjectId(risk_id)})
        changed_by = data.pop("updated_by", None)
        update = {"$set": {
            **data, "inherent_score": inherent["score"], "inherent_level": inherent["level"],
            "residual_score": residual["score"], "residual_level": residual["level"],
            "updated_at": datetime.now(timezone.utc),
        }}
        if old and old.get("status") != data["status"]:
            update["$push"] = {"status_history": {"status": data["status"], "changed_at": datetime.now(timezone.utc), "changed_by": changed_by}}
        if data["status"] == "Closed":
            update["$set"]["closed_at"] = datetime.now(timezone.utc)
        else:
            update["$unset"] = {"closed_at": ""}
        result = db.db.risks.update_one({"_id": ObjectId(risk_id)}, update)
    except InvalidId:
        return None
    return get_risk(risk_id) if result.matched_count else None

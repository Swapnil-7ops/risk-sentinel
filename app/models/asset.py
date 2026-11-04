from datetime import datetime, timezone
import re

from bson import ObjectId
from bson.errors import InvalidId

from app import db

ASSET_TYPES = ("Hardware", "Software", "Data", "Service", "People")


def _serialize(document):
    if not document:
        return None
    document["id"] = str(document.pop("_id"))
    return document


def list_assets(search=None, asset_type=None):
    query = {}
    if search:
        query["name"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    if asset_type in ASSET_TYPES:
        query["type"] = asset_type
    return [_serialize(item) for item in db.db.assets.find(query).sort("name", 1)]


def get_asset(asset_id):
    try:
        document = db.db.assets.find_one({"_id": ObjectId(asset_id)})
    except InvalidId:
        return None
    return _serialize(document)


def create_asset(data, user_id):
    now = datetime.now(timezone.utc)
    document = {**data, "created_by": user_id, "created_at": now, "updated_at": now}
    result = db.db.assets.insert_one(document)
    return get_asset(str(result.inserted_id))


def update_asset(asset_id, data):
    try:
        result = db.db.assets.update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": {**data, "updated_at": datetime.now(timezone.utc)}},
        )
    except InvalidId:
        return None
    return get_asset(asset_id) if result.matched_count else None


def delete_asset(asset_id):
    try:
        result = db.db.assets.delete_one({"_id": ObjectId(asset_id)})
    except InvalidId:
        return False
    return result.deleted_count == 1

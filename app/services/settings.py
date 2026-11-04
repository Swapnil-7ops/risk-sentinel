DEFAULT_APPETITE_THRESHOLD = 10


def get_appetite_threshold():
    from app import db
    setting = db.db.settings.find_one({"_id": "risk_appetite"})
    return setting.get("threshold", DEFAULT_APPETITE_THRESHOLD) if setting else DEFAULT_APPETITE_THRESHOLD


def set_appetite_threshold(threshold):
    from app import db
    db.db.settings.update_one({"_id": "risk_appetite"}, {"$set": {"threshold": threshold}}, upsert=True)

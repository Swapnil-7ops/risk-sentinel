import re

from app import db

THEMES = ("Organizational", "People", "Physical", "Technological")


def list_controls(search=None, theme=None):
    query = {}
    if search:
        expression = re.escape(search.strip())
        query["$or"] = [{"id": {"$regex": expression, "$options": "i"}}, {"name": {"$regex": expression, "$options": "i"}}]
    if theme in THEMES:
        query["theme"] = theme
    controls = list(db.db.controls.find(query).sort("id", 1))
    for control in controls:
        control["risk_count"] = db.db.risk_controls.count_documents({"control_id": control["id"]})
        control.pop("_id", None)
    return controls


def get_control(control_id):
    return db.db.controls.find_one({"id": control_id})


def seed_controls(controls):
    for control in controls:
        db.db.controls.update_one({"id": control["id"]}, {"$set": control}, upsert=True)

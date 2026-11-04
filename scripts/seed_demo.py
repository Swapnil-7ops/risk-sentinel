"""Seed clearly marked local demo data; never import this module from the app."""
import argparse
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import bcrypt, db
from app.services.risk_engine import assess_risk


SCENARIOS = [
    ("Ransomware disruption", "Ransomware encrypts shared services", "Endpoint defenses are incomplete", 5, 5, 3, 4, "Open"),
    ("Misconfigured cloud storage", "Public bucket exposes records", "Access policy was not reviewed", 4, 5, 2, 4, "In Treatment"),
    ("Employee phishing campaign", "Targeted phishing steals credentials", "Awareness training is inconsistent", 4, 4, 2, 3, "In Treatment"),
    ("Unpatched application server", "Known exploit reaches an internet service", "Patch window is overdue", 5, 4, 3, 3, "Open"),
    ("Insider data theft", "Privileged user copies sensitive data", "Monitoring coverage is limited", 3, 5, 2, 4, "Open"),
    ("Third-party breach", "Supplier compromise affects shared data", "Supplier assurance evidence is incomplete", 4, 4, 2, 3, "In Treatment"),
    ("Lost laptop", "Portable device is lost during travel", "Disk protection is inconsistently verified", 3, 3, 1, 2, "Closed"),
    ("Weak access control", "Excess permissions allow unauthorized changes", "Role reviews are infrequent", 4, 4, 2, 3, "In Treatment"),
    ("Backup failure", "Recovery copies are unavailable after an incident", "Restore testing is incomplete", 3, 5, 2, 4, "Open"),
    ("Physical access lapse", "Unauthorized visitor reaches a restricted area", "Visitor controls are inconsistently followed", 3, 3, 1, 2, "Closed"),
    ("Mobile device exposure", "Unmanaged device exposes business data", "Mobile inventory is incomplete", 3, 4, 2, 3, "Open"),
    ("Supplier credential reuse", "Reused supplier credentials are abused", "Unique credential enforcement is partial", 4, 4, 2, 3, "In Treatment"),
]

DEMO_CONTROL_IDS = (
    "A.5.1", "A.5.7", "A.5.15", "A.6.3", "A.7.4",
    "A.7.7", "A.8.8", "A.8.9", "A.8.13",
)

DEMO_CONTROLS = (
    ("A.5.1", "Policies for information security", "Organizational"),
    ("A.5.7", "Threat intelligence", "Organizational"),
    ("A.5.15", "Access control", "Organizational"),
    ("A.6.3", "Information security awareness", "People"),
    ("A.7.4", "Physical security monitoring", "Physical"),
    ("A.7.7", "Clear desk and clear screen", "Physical"),
    ("A.8.8", "Management of technical vulnerabilities", "Technological"),
    ("A.8.9", "Configuration management", "Technological"),
    ("A.8.13", "Information backup", "Technological"),
)


def _password(env_name):
    value = os.getenv(env_name)
    if value:
        return value
    value = secrets.token_urlsafe(16)
    print(f"{env_name}={value}")
    return value


def reset_demo():
    for name in ("risk_controls", "risks", "assets", "users", "controls"):
        db.db[name].delete_many({"demo": True})


def seed(force=False):
    if db.db.risks.count_documents({"demo": {"$ne": True}}) and not force:
        raise RuntimeError("Database contains non-demo risks; use --force to continue.")
    now = datetime.now(timezone.utc)
    assets = []
    for index in range(10):
        result = db.db.assets.insert_one({"name": f"Demo asset {index + 1}", "type": ("Software", "Data", "Service", "Hardware", "People")[index % 5], "owner": "Demo team", "criticality": (index % 5) + 1, "description": "Generic demonstration asset.", "demo": True, "created_at": now - timedelta(days=180 - index * 10)})
        assets.append(str(result.inserted_id))
    for control_id, name, theme in DEMO_CONTROLS:
        db.db.controls.update_one({"id": control_id}, {"$set": {"id": control_id, "name": name, "theme": theme, "description": "Demo control for analytics and workflow previews.", "demo": True}}, upsert=True)
    controls = []
    for control_id in DEMO_CONTROL_IDS:
        control = db.db.controls.find_one({"id": control_id}, {"id": 1})
        if control:
            controls.append(control["id"])
    if not controls:
        fallback = db.db.controls.find_one({}, {"id": 1})
        if fallback:
            controls.append(fallback["id"])
    for index, scenario in enumerate(SCENARIOS):
        title, threat, vulnerability, likelihood, impact, residual_likelihood, residual_impact, status = scenario
        inherent = assess_risk(likelihood, impact)
        residual = assess_risk(residual_likelihood, residual_impact)
        created = now - timedelta(days=170 - index * 12)
        document = {"asset_id": assets[index % len(assets)], "title": title, "threat": threat, "vulnerability": vulnerability, "likelihood": likelihood, "impact": impact, "residual_likelihood": residual_likelihood, "residual_impact": residual_impact, "status": status, "owner": "Demo risk owner", "source": "Demo scenario", "inherent_score": inherent["score"], "inherent_level": inherent["level"], "residual_score": residual["score"], "residual_level": residual["level"], "created_by": "demo", "created_at": created, "updated_at": created, "status_history": [{"status": "Open", "changed_at": created, "changed_by": "demo"}, {"status": status, "changed_at": created + timedelta(days=10), "changed_by": "demo"}], "demo": True}
        if status == "Closed":
            document["closed_at"] = created + timedelta(days=20)
        risk_id = db.db.risks.insert_one(document).inserted_id
        if controls and index < 10:
            db.db.risk_controls.insert_one({"risk_id": str(risk_id), "control_id": controls[index % len(controls)], "treatment": "Mitigate", "action_plan": "Review and improve the control.", "owner": ("Demo risk owner", "Demo security team", "Demo operations team")[index % 3], "due_date": (now - timedelta(days=5) if index < 2 else now + timedelta(days=30)).strftime("%Y-%m-%d"), "status": ("Planned", "In Progress", "Implemented")[index % 3], "created_by": "demo", "created_at": created, "updated_at": created, "demo": True})
    password = _password("DEMO_AUDITOR_PASSWORD")
    db.db.users.update_one({"email": "demo-auditor@example.com"}, {"$set": {"name": "Demo auditor", "email": "demo-auditor@example.com", "password_hash": bcrypt.generate_password_hash(password).decode("utf-8"), "role": "auditor", "demo": True}}, upsert=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reset-demo", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("--confirm is required; this changes the local database.")
    if args.reset_demo:
        reset_demo()
        return
    seed(force=args.force)


if __name__ == "__main__":
    main()

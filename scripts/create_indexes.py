"""Create MongoDB indexes manually before or after a deployment."""

from app import db


def create_indexes():
    db.db.users.create_index("email", unique=True)
    db.db.assets.create_index("name")
    db.db.assets.create_index("type")
    db.db.risks.create_index("status")
    db.db.risks.create_index("residual_level")
    db.db.risks.create_index([("title", "text"), ("threat", "text")])
    db.db.controls.create_index("id", unique=True)
    db.db.risk_controls.create_index("risk_id")
    db.db.risk_controls.create_index("control_id")
    db.db.risk_controls.create_index("status")
    db.db.risk_controls.create_index("due_date")
    db.db.audit_logs.create_index("timestamp")
    db.db.audit_logs.create_index("entity_type")
    db.db.audit_logs.create_index("user_id")
    db.db.risks.create_index("created_at")
    db.db.risks.create_index("closed_at")
    db.db.risks.create_index("asset_id")
    db.db.risks.create_index("owner")
    db.db.risks.create_index("source")
    db.db.risks.create_index("inherent_level")
    db.db.risks.create_index("inherent_likelihood")
    db.db.risks.create_index("inherent_impact")
    db.db.risks.create_index("residual_likelihood")
    db.db.risks.create_index("residual_impact")
    db.db.risk_controls.create_index([("status", 1), ("due_date", 1)])
    db.db.analytics_bookmarks.create_index([("user_id", 1), ("created_at", -1)])


if __name__ == "__main__":
    create_indexes()
    print("MongoDB indexes created.")

import csv
import io
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from app import db
from app.services.risk_control_service import is_overdue
from app.services.settings import get_appetite_threshold

FILTER_KEYS = {
    "level", "status", "asset_type", "asset", "owner", "control_theme", "source",
    "date_from", "date_to", "view", "likelihood", "impact",
}
LEVELS = ("Low", "Medium", "High", "Critical")
STATUSES = ("Open", "In Treatment", "Closed")
ASSET_TYPES = ("Hardware", "Software", "Data", "Service", "People")
THEMES = ("Organizational", "People", "Physical", "Technological")
VIEWS = ("inherent", "residual")
MAX_LIST_VALUES = 20


def _values(value):
    if value is None or value == "":
        return []
    values = value if isinstance(value, list) else str(value).split(",")
    if len(values) > MAX_LIST_VALUES:
        raise ValueError("Filter contains too many values.")
    if any("$" in str(item) or "{" in str(item) or "}" in str(item) for item in values):
        raise ValueError("Operator-like filter values are not allowed.")
    return [str(item).strip() for item in values if str(item).strip()]


def _date(value):
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError) as error:
        raise ValueError("Dates must use YYYY-MM-DD.") from error


def validate_filters(raw):
    raw = raw or {}
    unknown = set(raw) - FILTER_KEYS
    if unknown:
        raise ValueError("Unknown analytics filter.")
    result = {}
    for key in ("level", "status", "asset_type", "asset", "owner", "control_theme", "source", "likelihood", "impact"):
        values = _values(raw.get(key))
        result[key] = values
    for key, allowed in (("level", LEVELS), ("status", STATUSES), ("asset_type", ASSET_TYPES), ("control_theme", THEMES), ("view", VIEWS)):
        if key == "view":
            value = raw.get(key, "residual")
            if not isinstance(value, str):
                raise ValueError("Invalid analytics filter.")
            if value not in allowed:
                raise ValueError("Invalid analytics filter.")
            result[key] = value
        elif any(value not in allowed for value in result[key]):
            raise ValueError("Invalid analytics filter.")
    result["date_from"] = _date(raw.get("date_from"))
    result["date_to"] = _date(raw.get("date_to"))
    if result["date_from"] and result["date_to"] and result["date_from"] > result["date_to"]:
        raise ValueError("date_from must not be after date_to.")
    for key in ("likelihood", "impact"):
        if any(not value.isdigit() or not 1 <= int(value) <= 5 for value in result[key]):
            raise ValueError("Likelihood and impact must be between 1 and 5.")
        result[key] = [int(value) for value in result[key]]
    return result


def _risk_query(filters):
    query = {}
    score_prefix = filters["view"]
    if filters["level"]:
        query[f"{score_prefix}_level"] = {"$in": filters["level"]}
    if filters["status"]:
        query["status"] = {"$in": filters["status"]}
    if filters["owner"]:
        query["owner"] = {"$in": filters["owner"]}
    if filters["source"]:
        query["source"] = {"$in": filters["source"]}
    if filters["likelihood"]:
        query[f"{score_prefix}_likelihood"] = {"$in": filters["likelihood"]}
    if filters["impact"]:
        query[f"{score_prefix}_impact"] = {"$in": filters["impact"]}
    created = {}
    if filters["date_from"]:
        created["$gte"] = datetime.combine(filters["date_from"], datetime.min.time(), timezone.utc)
    if filters["date_to"]:
        created["$lt"] = datetime.combine(filters["date_to"] + timedelta(days=1), datetime.min.time(), timezone.utc)
    if created:
        query["created_at"] = created
    return query


def _risk_documents(filters):
    risks = list(db.db.risks.find(_risk_query(filters)).limit(5000))
    if filters["asset_type"]:
        asset_ids = {str(item["_id"]): item["type"] for item in db.db.assets.find({"type": {"$in": filters["asset_type"]}}, {"type": 1})}
        risks = [risk for risk in risks if risk.get("asset_id") in asset_ids]
    if filters["asset"]:
        risks = [risk for risk in risks if str(risk.get("asset_id")) in filters["asset"]]
    if filters["control_theme"]:
        control_ids = {item["id"] for item in db.db.controls.find({"theme": {"$in": filters["control_theme"]}}, {"id": 1})}
        mapped = {item["risk_id"] for item in db.db.risk_controls.find({"control_id": {"$in": list(control_ids)}}, {"risk_id": 1})}
        risks = [risk for risk in risks if str(risk["_id"]) in mapped]
    return risks


def filtered_risks(raw_filters):
    filters = validate_filters(raw_filters)
    risks = _risk_documents(filters)
    for risk in risks:
        risk["id"] = str(risk.pop("_id"))
    return risks


def _trend(risks, filters):
    dates = [risk.get("created_at") for risk in risks if risk.get("created_at")]
    if not dates:
        return {"current": 0, "previous": 0, "direction": "no prior data"}
    end = filters["date_to"] or date.today()
    start = filters["date_from"] or (end - timedelta(days=30))
    length = max((end - start).days + 1, 1)
    previous_start = start - timedelta(days=length)
    current = sum(start <= item.date() <= end for item in dates)
    previous = sum(previous_start <= item.date() < start for item in dates)
    points = []
    cursor = start.replace(day=1)
    while cursor <= end:
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        points.append({"period": cursor.isoformat()[:7], "opened": sum(bool(item.get("created_at") and cursor <= item["created_at"].date() < next_month) for item in risks), "closed": sum(bool(item.get("closed_at") and cursor <= item["closed_at"].date() < next_month) for item in risks)})
        cursor = next_month
    return {"current": current, "previous": previous, "direction": "no prior data" if previous == 0 else ("up" if current > previous else "down" if current < previous else "flat"), "points": points}


def build_summary(raw_filters):
    filters = validate_filters(raw_filters)
    risks = _risk_documents(filters)
    threshold = get_appetite_threshold()
    levels = Counter(risk.get(f"{filters['view']}_level") for risk in risks)
    heat = [{"likelihood": likelihood, "impact": impact, "count": sum(risk.get(f"{filters['view']}_likelihood") == likelihood and risk.get(f"{filters['view']}_impact") == impact for risk in risks)} for likelihood in range(1, 6) for impact in range(1, 6)]
    risk_ids = {str(risk["_id"]) for risk in risks}
    mappings = list(db.db.risk_controls.find({"risk_id": {"$in": list(risk_ids)}}).limit(5000))
    implemented_controls = {item["control_id"] for item in mappings if item.get("status") == "Implemented"}
    control_theme_by_id = {item["id"]: item["theme"] for item in db.db.controls.find({"id": {"$in": list(implemented_controls)}}, {"id": 1, "theme": 1})}
    coverage = [{"theme": theme, "implemented": sum(control_theme_by_id.get(control_id) == theme for control_id in implemented_controls)} for theme in THEMES]
    assets = Counter()
    asset_ids = {str(item["_id"]): item.get("type") for item in db.db.assets.find({}, {"_id": 1, "type": 1})}
    for risk in risks:
        assets[asset_ids.get(risk.get("asset_id"), "Unknown")] += 1
    treatments = Counter(item.get("status") for item in mappings)
    overdue = sum(is_overdue(item.get("due_date"), item.get("status")) for item in mappings)
    return {
        "filters": {key: (value.isoformat() if isinstance(value, date) else value) for key, value in filters.items()},
        "kpis": {"total_open": sum(risk.get("status") != "Closed" for risk in risks), "critical": levels["Critical"], "appetite_breaches": sum(risk.get("residual_score", 0) > threshold for risk in risks), "overdue_treatments": overdue, "control_coverage": round(len(implemented_controls) / 93 * 100, 1)},
        "heatmap": heat,
        "levels": [{"level": level, "count": levels[level]} for level in LEVELS],
        "asset_types": [{"type": key, "count": value} for key, value in assets.items()],
        "treatments": [{"status": status, "count": treatments[status]} for status in ("Planned", "In Progress", "Implemented")],
        "coverage": coverage,
        "trend": _trend(risks, filters),
        "top_risks": [{"id": str(risk["_id"]), "title": risk.get("title", ""), "score": risk.get("residual_score", 0), "level": risk.get("residual_level", "Low"), "owner": risk.get("owner", "")} for risk in sorted(risks, key=lambda item: item.get("residual_score", 0), reverse=True)[:10]],
    }


def drill(raw_filters, dimension, value):
    filters = validate_filters(raw_filters)
    if dimension not in {"level", "asset_type"}:
        raise ValueError("Invalid drill dimension.")
    if dimension == "level" and value not in LEVELS:
        raise ValueError("Invalid drill value.")
    if dimension == "asset_type" and value not in ASSET_TYPES:
        raise ValueError("Invalid drill value.")
    next_filters = dict(raw_filters)
    next_filters[dimension] = value
    return build_summary(next_filters)


def csv_response(rows):
    output = io.StringIO()
    writer = csv.writer(output)
    if not rows:
        writer.writerow(["No data"])
    else:
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([_csv_cell(value) for value in row.values()])
    return output.getvalue()


def serializable_filters(filters):
    return {key: value.isoformat() if isinstance(value, date) else value for key, value in filters.items()}


def _csv_cell(value):
    value = "" if value is None else str(value)
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value

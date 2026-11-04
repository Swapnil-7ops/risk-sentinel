import json
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.services.analytics_service import build_summary, csv_response, drill, filtered_risks, serializable_filters, validate_filters
from app.services.audit_service import list_audit_logs, record_audit
from app.services.auth_utils import role_required, safe_string
from app.services.report_service import build_risk_report
from app import limiter

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("analytics/dashboard.html")


@analytics_bp.get("/reports/risk-report.pdf")
@login_required
def risk_report():
    try:
        raw = {key: values if len(values) > 1 else values[0] for key, values in request.args.lists()}
        content = build_risk_report(raw, current_user)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return Response(content, mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=risk-report.pdf"})


@analytics_bp.get("/api/analytics/summary")
@login_required
@limiter.limit("30 per minute")
def summary():
    try:
        raw = {key: values if len(values) > 1 else values[0] for key, values in request.args.lists()}
        return jsonify(build_summary(raw))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@analytics_bp.get("/api/analytics/drill")
@login_required
@limiter.limit("30 per minute")
def drill_api():
    try:
        raw = {key: values if len(values) > 1 else values[0] for key, values in request.args.lists() if key not in {"dimension", "value"}}
        dimension = request.args.get("dimension")
        value = request.args.get("value")
        if not isinstance(dimension, str) or not isinstance(value, str):
            abort(400)
        return jsonify(drill(raw, dimension, value))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@analytics_bp.get("/analytics/export.csv")
@login_required
def export_csv():
    try:
        raw = {key: values if len(values) > 1 else values[0] for key, values in request.args.lists()}
        filters = validate_filters(raw)
        risks = filtered_risks(raw)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    content = csv_response(risks)
    record_audit(current_user, "create", "analytics_export", "csv", new_value={"filters": serializable_filters(filters)})
    return Response(content, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=filtered-risks.csv"})


@analytics_bp.post("/analytics/bookmarks")
@login_required
def save_bookmark():
    name = request.form.get("name", "")
    if not isinstance(name, str):
        abort(400)
    name = name.strip()
    if not 1 <= len(name) <= 50:
        flash("Bookmark names must be 1-50 characters.", "danger")
        return redirect(url_for("analytics.dashboard"))
    try:
        decoded = json.loads(request.form.get("filters", "{}"))
        if not isinstance(decoded, dict):
            raise ValueError("Bookmark filters must be an object.")
        filters = validate_filters(decoded)
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("analytics.dashboard"))
    if db.db.analytics_bookmarks.count_documents({"user_id": str(current_user.id)}) >= 20:
        flash("You can save up to 20 bookmarks.", "warning")
        return redirect(url_for("analytics.dashboard"))
    result = db.db.analytics_bookmarks.insert_one({"user_id": str(current_user.id), "name": name, "filters": serializable_filters(filters), "created_at": datetime.now(timezone.utc)})
    record_audit(current_user, "create", "analytics_bookmark", result.inserted_id, new_value={"name": name, "filters": filters})
    return redirect(url_for("analytics.dashboard"))


@analytics_bp.get("/analytics/bookmarks")
@login_required
def list_bookmarks():
    bookmarks = list(db.db.analytics_bookmarks.find({"user_id": str(current_user.id)}).sort("created_at", -1).limit(20))
    return jsonify([{"id": str(item["_id"]), "name": item["name"], "filters": item["filters"]} for item in bookmarks])


@analytics_bp.delete("/analytics/bookmarks/<bookmark_id>")
@login_required
def delete_bookmark(bookmark_id):
    try:
        object_id = ObjectId(bookmark_id)
    except InvalidId:
        return jsonify({"error": "Bookmark not found."}), 404
    result = db.db.analytics_bookmarks.delete_one({"_id": object_id, "user_id": str(current_user.id)})
    if not result.deleted_count:
        return jsonify({"error": "Bookmark not found."}), 404
    return ("", 204)


@analytics_bp.patch("/analytics/bookmarks/<bookmark_id>")
@login_required
def rename_bookmark(bookmark_id):
    payload = request.get_json(silent=True)
    name = payload.get("name", "") if isinstance(payload, dict) else ""
    if not isinstance(name, str):
        abort(400)
    name = name.strip()
    if not 1 <= len(name) <= 50:
        return jsonify({"error": "Bookmark names must be 1-50 characters."}), 400
    try:
        object_id = ObjectId(bookmark_id)
    except InvalidId:
        return jsonify({"error": "Bookmark not found."}), 404
    result = db.db.analytics_bookmarks.update_one({"_id": object_id, "user_id": str(current_user.id)}, {"$set": {"name": name}})
    return ("", 204) if result.matched_count else (jsonify({"error": "Bookmark not found."}), 404)


@analytics_bp.get("/audit-logs/export.csv")
@login_required
@role_required("admin", "auditor")
def export_audit_csv():
    import csv
    from io import StringIO

    page = 1
    entity_type = safe_string(request.args.get("entity_type", ""), max_length=30)
    action = safe_string(request.args.get("action", ""), max_length=20)
    search = safe_string(request.args.get("search", ""), max_length=100)
    logs, _total = list_audit_logs(
        page=page,
        per_page=5000,
        entity_type=entity_type,
        action=action,
        search=search,
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "actor", "action", "entity_type", "entity_id"])
    for log in logs:
        writer.writerow([log.get("timestamp"), log.get("user_email") or "System", log.get("action"), log.get("entity_type"), log.get("entity_id")])
    record_audit(current_user, "create", "analytics_export", "audit-csv", new_value={"count": len(logs)})
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=audit-log.csv"})

from math import ceil

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import MappingApprovalForm, MappingEscalationForm, MappingEvidenceForm, MappingForm, MappingStatusForm
from app.services.audit_service import list_audit_logs, record_audit
from app.services.control_service import THEMES, get_control, list_controls
from app.services.risk_control_service import create_mapping, escalate_mapping, is_overdue, list_mappings, overdue_days, update_mapping_approval, update_mapping_evidence, update_mapping_status
from app.services.auth_utils import role_required, safe_string

controls_bp = Blueprint("controls", __name__)


@controls_bp.get("/controls")
@login_required
def controls_library():
    return render_template("controls/list.html", controls=list_controls(safe_string(request.args.get("search", ""), max_length=150), safe_string(request.args.get("theme", ""), max_length=30)), themes=THEMES)


@controls_bp.route("/risks/<risk_id>/controls", methods=["GET", "POST"])
@login_required
@role_required("admin", "risk_owner")
def map_control(risk_id):
    form = MappingForm()
    form.control_ids.choices = [(item["id"], f'{item["id"]} — {item["name"]}') for item in list_controls()]
    if form.validate_on_submit():
        try:
            for control_id in form.control_ids.data:
                data = {"risk_id": risk_id, "control_id": control_id, "treatment": form.treatment.data, "action_plan": form.action_plan.data.strip(), "owner": form.owner.data.strip(), "due_date": form.due_date.data.strip(), "status": form.status.data}
                result = create_mapping(data, current_user.id)
                record_audit(current_user, "create", "risk_control", result.inserted_id, new_value=data)
            flash("Control mapped.", "success")
            return redirect(url_for("risks.detail_risk", risk_id=risk_id))
        except ValueError as error:
            form.control_ids.errors.append(str(error))
    return render_template("controls/map.html", form=form, risk_id=risk_id)


@controls_bp.get("/treatment-board")
@login_required
def treatment_board():
    owner = safe_string(request.args.get("owner", ""), max_length=150)
    theme = safe_string(request.args.get("theme", ""), max_length=30)
    overdue = safe_string(request.args.get("overdue", ""), max_length=1)
    if overdue not in {"", "1", "0"}:
        return "Invalid filter.", 400
    mappings = list_mappings(owner=owner, theme=theme, overdue=overdue == "1")
    for mapping in mappings:
        risk = db.db.risks.find_one({"_id": __import__("bson").ObjectId(mapping["risk_id"])})
        mapping["risk_title"] = risk.get("title", "Unknown risk") if risk else "Unknown risk"
        mapping["level"] = risk.get("residual_level", "Low") if risk else "Low"
        mapping["is_overdue"] = is_overdue(mapping.get("due_date"), mapping.get("status"))
        mapping["overdue_days"] = overdue_days(mapping.get("due_date"), mapping.get("status"))
    return render_template("controls/board.html", mappings=mappings)


@controls_bp.post("/treatment-board/<mapping_id>/status")
@login_required
@role_required("admin", "risk_owner")
def update_board_status(mapping_id):
    form = MappingStatusForm()
    if not form.validate_on_submit():
        return "Invalid status.", 400
    try:
        old = db.db.risk_controls.find_one({"_id": __import__("bson").ObjectId(mapping_id)})
        update_mapping_status(mapping_id, form.status.data, current_user.id)
        record_audit(current_user, "update", "risk_control", mapping_id, old_value=old, new_value={"status": form.status.data})
    except ValueError as error:
        return str(error), 400
    return redirect(url_for("controls.treatment_board"))


@controls_bp.post("/treatment-board/<mapping_id>/evidence")
@login_required
@role_required("admin", "risk_owner")
def update_evidence(mapping_id):
    form = MappingEvidenceForm()
    if not form.validate_on_submit():
        return "Invalid evidence link.", 400
    try:
        old = db.db.risk_controls.find_one({"_id": __import__("bson").ObjectId(mapping_id)})
        update_mapping_evidence(mapping_id, form.evidence_url.data, current_user.id)
        record_audit(current_user, "update", "risk_control", mapping_id, old_value={"evidence_url": old.get("evidence_url") if old else None}, new_value={"evidence_url": form.evidence_url.data.strip()})
    except ValueError as error:
        return str(error), 400
    return redirect(url_for("controls.treatment_board"))


@controls_bp.post("/treatment-board/<mapping_id>/approval")
@login_required
@role_required("admin")
def review_mapping(mapping_id):
    form = MappingApprovalForm()
    if not form.validate_on_submit():
        return "Invalid review.", 400
    try:
        old = db.db.risk_controls.find_one({"_id": __import__("bson").ObjectId(mapping_id)})
        update_mapping_approval(mapping_id, form.decision.data, form.comment.data, current_user.id)
        record_audit(current_user, "update", "risk_control", mapping_id, old_value={"approval": old.get("approval") if old else None}, new_value={"decision": form.decision.data, "comment": form.comment.data.strip()})
    except ValueError as error:
        return str(error), 400
    return redirect(url_for("controls.treatment_board"))


@controls_bp.post("/treatment-board/<mapping_id>/escalate")
@login_required
@role_required("admin", "risk_owner")
def escalate_treatment(mapping_id):
    form = MappingEscalationForm()
    if not form.validate_on_submit():
        return "Invalid escalation.", 400
    try:
        escalate_mapping(mapping_id, form.reason.data, current_user.id)
        record_audit(current_user, "update", "risk_control", mapping_id, new_value={"escalation_reason": form.reason.data.strip(), "escalation_status": "Open"})
    except ValueError as error:
        return str(error), 400
    flash("Treatment escalated.", "success")
    return redirect(url_for("controls.treatment_board"))


@controls_bp.get("/audit-logs")
@login_required
@role_required("admin", "auditor")
def audit_logs():
    page_value = request.args.get("page", 1, type=int)
    if page_value is None:
        return "Invalid page.", 400
    page = max(page_value, 1)
    logs, total = list_audit_logs(page=page, user_id=safe_string(request.args.get("user_id", ""), max_length=100), entity_type=safe_string(request.args.get("entity_type", ""), max_length=30), action=safe_string(request.args.get("action", ""), max_length=20), search=safe_string(request.args.get("search", ""), max_length=100))
    return render_template("audit/list.html", logs=logs, page=page, pages=max(1, ceil(total / 20)), total=total)

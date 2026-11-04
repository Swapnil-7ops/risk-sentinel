from math import ceil

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import AppetiteForm, RiskApprovalForm, RiskForm
from app.models.risk import create_risk, get_risk, list_risks, update_risk
from app.services.audit_service import record_audit
from app.services.analytics_service import FILTER_KEYS, filtered_risks
from app.services.risk_control_service import list_mappings
from app.services.auth_utils import role_required, safe_string
from app.services.risk_engine import assess_risk, is_appetite_breach
from app.services.settings import get_appetite_threshold, set_appetite_threshold

risks_bp = Blueprint("risks", __name__)


def _risk_data(form):
    return {
        "asset_id": form.asset_id.data.strip(), "title": form.title.data.strip(),
        "threat": form.threat.data.strip(), "vulnerability": form.vulnerability.data.strip(),
        "likelihood": form.likelihood.data, "impact": form.impact.data,
        "residual_likelihood": form.residual_likelihood.data, "residual_impact": form.residual_impact.data,
        "status": form.status.data, "owner": form.owner.data.strip(), "source": form.source.data.strip(),
    }


@risks_bp.get("/risks")
@login_required
def list_risks_view():
    for key in request.args:
        safe_string(request.args.get(key, ""), max_length=200)
    analytics_keys = set(request.args) & FILTER_KEYS
    if analytics_keys:
        try:
            risks = filtered_risks({key: request.args.getlist(key) if len(request.args.getlist(key)) > 1 else request.args.get(key) for key in analytics_keys})
        except ValueError:
            risks = []
        return render_template("risks/list.html", risks=risks, threshold=get_appetite_threshold(), page=1, pages=1, total=len(risks))
    page_value = request.args.get("page", 1, type=int)
    if page_value is None:
        return "Invalid page.", 400
    page = max(page_value, 1)
    risks, total = list_risks(request.args.get("search"), request.args.get("status"), request.args.get("level"), page, sort=request.args.get("sort", "updated_at"), direction=request.args.get("direction", "desc"))
    threshold = get_appetite_threshold()
    return render_template("risks/list.html", risks=risks, threshold=threshold, page=page, pages=max(1, ceil(total / 10)), total=total)


@risks_bp.route("/risks/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "risk_owner")
def add_risk():
    form = RiskForm()
    if form.validate_on_submit():
        data = _risk_data(form)
        if data["residual_likelihood"] > data["likelihood"] or data["residual_impact"] > data["impact"]:
            form.residual_likelihood.errors.append("Residual values cannot exceed inherent values.")
            return render_template("risks/form.html", form=form, title="Add risk")
        risk = create_risk(data, current_user.id, assess_risk(data["likelihood"], data["impact"]), assess_risk(data["residual_likelihood"], data["residual_impact"]))
        record_audit(current_user, "create", "risk", risk["id"], new_value=data)
        flash("Risk created.", "success")
        return redirect(url_for("risks.list_risks_view"))
    return render_template("risks/form.html", form=form, title="Add risk")


@risks_bp.route("/risks/<risk_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "risk_owner")
def edit_risk(risk_id):
    risk = get_risk(risk_id)
    if not risk:
        return render_template("errors/404.html"), 404
    form = RiskForm(data=risk)
    if form.validate_on_submit():
        data = _risk_data(form)
        if data["residual_likelihood"] > data["likelihood"] or data["residual_impact"] > data["impact"]:
            form.residual_likelihood.errors.append("Residual values cannot exceed inherent values.")
            return render_template("risks/form.html", form=form, title="Edit risk")
        old = risk
        data["updated_by"] = current_user.id
        update_risk(risk_id, data, assess_risk(data["likelihood"], data["impact"]), assess_risk(data["residual_likelihood"], data["residual_impact"]))
        record_audit(current_user, "update", "risk", risk_id, old_value=old, new_value=data)
        flash("Risk updated.", "success")
        return redirect(url_for("risks.detail_risk", risk_id=risk_id))
    return render_template("risks/form.html", form=form, title="Edit risk")


@risks_bp.get("/risks/<risk_id>")
@login_required
def detail_risk(risk_id):
    risk = get_risk(risk_id)
    if not risk:
        return render_template("errors/404.html"), 404
    return render_template("risks/detail.html", risk=risk, threshold=get_appetite_threshold(), mappings=list_mappings(risk_id=risk_id), approval_form=RiskApprovalForm())


@risks_bp.post("/risks/<risk_id>/approval")
@login_required
@role_required("admin")
def approve_risk(risk_id):
    form = RiskApprovalForm()
    risk = get_risk(risk_id)
    if not risk:
        return render_template("errors/404.html"), 404
    if not form.validate_on_submit():
        return "Invalid risk decision.", 400
    approval = {
        "decision": form.decision.data,
        "rationale": form.rationale.data.strip(),
        "reviewed_by": current_user.id,
        "reviewed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }
    db.db.risks.update_one({"_id": __import__("bson").ObjectId(risk_id)}, {"$set": {"approval": approval, "updated_at": approval["reviewed_at"]}})
    record_audit(current_user, "update", "risk", risk_id, old_value={"approval": risk.get("approval")}, new_value={"approval": approval})
    flash("Risk decision recorded.", "success")
    return redirect(url_for("risks.detail_risk", risk_id=risk_id))


@risks_bp.post("/risks/<risk_id>/delete")
@login_required
@role_required("admin")
def delete_risk_route(risk_id):
    from bson import ObjectId
    risk = get_risk(risk_id)
    if not risk:
        return render_template("errors/404.html"), 404
    for mapping in db.db.risk_controls.find({"risk_id": risk_id}):
        record_audit(current_user, "delete", "risk_control", mapping["_id"], old_value=mapping)
    db.db.risk_controls.delete_many({"risk_id": risk_id})
    db.db.risks.delete_one({"_id": ObjectId(risk_id)})
    record_audit(current_user, "delete", "risk", risk_id, old_value=risk)
    flash("Risk deleted.", "success")
    return redirect(url_for("risks.list_risks_view"))


@risks_bp.route("/settings/risk-appetite", methods=["GET", "POST"])
@login_required
@role_required("admin")
def appetite_settings():
    form = AppetiteForm(threshold=get_appetite_threshold())
    if form.validate_on_submit():
        old = {"threshold": get_appetite_threshold()}
        set_appetite_threshold(form.threshold.data)
        record_audit(current_user, "update", "setting", "risk_appetite", old_value=old, new_value={"threshold": form.threshold.data})
        flash("Risk appetite updated.", "success")
        return redirect(url_for("risks.appetite_settings"))
    return render_template("settings/appetite.html", form=form)

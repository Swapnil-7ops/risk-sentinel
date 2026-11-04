from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.forms import AssetForm
from app.models.asset import create_asset, delete_asset, get_asset, list_assets, update_asset
from app.services.auth_utils import role_required, safe_string
from app.services.audit_service import record_audit

assets_bp = Blueprint("assets", __name__)


@assets_bp.get("/")
def home():
    return redirect(url_for("assets.list_assets_view"))


@assets_bp.get("/assets")
@login_required
def list_assets_view():
    search = safe_string(request.args.get("search", ""), max_length=150)
    asset_type = safe_string(request.args.get("type", ""), max_length=30)
    assets = list_assets(search, asset_type)
    return render_template("assets/list.html", assets=assets)


@assets_bp.route("/assets/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "risk_owner")
def add_asset():
    form = AssetForm()
    if form.validate_on_submit():
        asset = create_asset(
            {"name": form.name.data.strip(), "type": form.type.data, "owner": form.owner.data.strip(),
             "criticality": form.criticality.data, "description": form.description.data.strip()},
            current_user.id,
        )
        record_audit(current_user, "create", "asset", asset["id"], new_value=asset)
        flash("Asset created.", "success")
        return redirect(url_for("assets.list_assets_view"))
    return render_template("assets/form.html", form=form, title="Add asset")


@assets_bp.route("/assets/<asset_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "risk_owner")
def edit_asset(asset_id):
    asset = get_asset(asset_id)
    if not asset:
        return render_template("errors/404.html"), 404
    form = AssetForm(data=asset)
    if form.validate_on_submit():
        old = asset
        update_asset(
            asset_id,
            {"name": form.name.data.strip(), "type": form.type.data, "owner": form.owner.data.strip(),
             "criticality": form.criticality.data, "description": form.description.data.strip()},
        )
        record_audit(current_user, "update", "asset", asset_id, old_value=old, new_value=request.form.to_dict())
        flash("Asset updated.", "success")
        return redirect(url_for("assets.list_assets_view"))
    return render_template("assets/form.html", form=form, title="Edit asset")


@assets_bp.post("/assets/<asset_id>/delete")
@login_required
@role_required("admin", "risk_owner")
def remove_asset(asset_id):
    old = get_asset(asset_id)
    if delete_asset(asset_id):
        record_audit(current_user, "delete", "asset", asset_id, old_value=old)
        flash("Asset deleted.", "success")
    else:
        flash("Asset not found.", "warning")
    return redirect(url_for("assets.list_assets_view"))

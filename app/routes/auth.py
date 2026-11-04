import secrets
import time
from datetime import datetime, timedelta, timezone

import pyotp
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import bcrypt, db, limiter
from app.forms import LoginForm, MfaForm, PasswordChangeForm, RegistrationForm, UserCreateForm, UserRoleForm, UserStateForm
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.auth_utils import role_required
from app.services.email_service import send_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.9gJ8V7Y4kQh7xQyQvY6w8fL7Q2N5n6W"


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("assets.list_assets_view"))
    if not User.register_allowed(current_app.config["ALLOW_REGISTRATION"]):
        return render_template("errors/404.html"), 404
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.create(form.name.data, form.email.data, form.password.data)
        _send_verification(user)
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("assets.list_assets_view"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_email(form.email.data)
        password_matches = bcrypt.check_password_hash(
            user.password_hash if user else DUMMY_PASSWORD_HASH,
            form.password.data,
        )
        if user and user.is_active and not user.is_locked() and password_matches:
            session.clear()
            if user.role in {"admin", "risk_owner"}:
                session["_mfa_pending_user"] = user.id
                if not user.mfa_enabled:
                    return redirect(url_for("auth.mfa_setup"))
                return redirect(url_for("auth.mfa_verify"))
            login_user(user)
            session["_session_created"] = time.time()
            session["_last_seen"] = time.time()
            user.reset_login_failures()
            if user.must_change_password:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("assets.list_assets_view"))
        if user:
            user.record_failed_login()
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/mfa/setup", methods=["GET", "POST"])
def mfa_setup():
    pending_id = session.get("_mfa_pending_user")
    if not pending_id:
        return redirect(url_for("auth.login"))
    user = User.get_by_id(pending_id)
    if not user or not user.is_active:
        session.clear()
        return redirect(url_for("auth.login"))
    secret = session.get("_mfa_secret") or pyotp.random_base32()
    session["_mfa_secret"] = secret
    form = MfaForm()
    if form.validate_on_submit() and pyotp.TOTP(secret).verify(form.code.data, valid_window=1):
        user.enable_mfa(secret)
        session.pop("_mfa_secret", None)
        _finish_login(user)
        return redirect(url_for("auth.change_password" if user.must_change_password else "assets.list_assets_view"))
    return render_template("auth/mfa_setup.html", form=form, secret=secret, provisioning_uri=pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name="Risk Sentinel"))


@auth_bp.route("/mfa/verify", methods=["GET", "POST"])
def mfa_verify():
    pending_id = session.get("_mfa_pending_user")
    user = User.get_by_id(pending_id) if pending_id else None
    if not user or not user.is_active or not user.mfa_enabled:
        session.clear()
        return redirect(url_for("auth.login"))
    form = MfaForm()
    if form.validate_on_submit() and pyotp.TOTP(user.mfa_secret).verify(form.code.data, valid_window=1):
        _finish_login(user)
        return redirect(url_for("auth.change_password" if user.must_change_password else "assets.list_assets_view"))
    if form.is_submitted():
        flash("Invalid authenticator code.", "danger")
    return render_template("auth/mfa_verify.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password-change", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per minute")
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not current_user.must_change_password and not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Current password is incorrect.")
            return render_template("auth/password_change.html", form=form)
        current_user.set_password(form.password.data)
        flash("Password changed.", "success")
        return redirect(url_for("assets.list_assets_view"))
    return render_template("auth/password_change.html", form=form)


@auth_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_user():
    form = UserCreateForm()
    if form.validate_on_submit():
        temporary_password = secrets.token_urlsafe(12)
        user = User.create(form.name.data, form.email.data, temporary_password, role=form.role.data, must_change_password=True)
        _send_verification(user)
        return render_template("auth/create_user.html", form=form, created_user=user, temporary_password=temporary_password)
    return render_template("auth/create_user.html", form=form)


@auth_bp.get("/users")
@login_required
@role_required("admin")
def users():
    all_users = User.list_all()
    return render_template("auth/users.html", users=all_users, role_forms={user.id: UserRoleForm() for user in all_users}, state_forms={user.id: UserStateForm() for user in all_users})


@auth_bp.post("/users/<user_id>/role")
@login_required
@role_required("admin")
def change_user_role(user_id):
    target = User.get_by_id(user_id)
    form = UserRoleForm()
    if not target or not form.validate_on_submit():
        return "Invalid user or role.", 400
    if target.id == current_user.id and form.role.data != "admin":
        flash("You cannot demote yourself.", "danger")
        return redirect(url_for("auth.users"))
    if target.role == "admin" and form.role.data != "admin" and target.is_active and _active_admin_count() <= 1:
        flash("The last active admin cannot be demoted.", "danger")
        return redirect(url_for("auth.users"))
    old_role = target.role
    target.update_admin_state(role=form.role.data)
    record_audit(current_user, "update", "user", target.id, old_value={"role": old_role}, new_value={"role": target.role})
    return redirect(url_for("auth.users"))


@auth_bp.post("/users/<user_id>/status")
@login_required
@role_required("admin")
def change_user_status(user_id):
    target = User.get_by_id(user_id)
    form = UserStateForm()
    if not target or not form.validate_on_submit():
        return "Invalid user or status.", 400
    if target.id == current_user.id and not form.is_active.data:
        flash("You cannot deactivate yourself.", "danger")
        return redirect(url_for("auth.users"))
    if target.role == "admin" and target.is_active and not form.is_active.data and _active_admin_count() <= 1:
        flash("The last active admin cannot be deactivated.", "danger")
        return redirect(url_for("auth.users"))
    old_state = target.is_active
    target.update_admin_state(is_active=form.is_active.data)
    record_audit(current_user, "update", "user", target.id, old_value={"is_active": old_state}, new_value={"is_active": target.is_active})
    return redirect(url_for("auth.users"))


@auth_bp.post("/users/<user_id>/reset-password")
@login_required
@role_required("admin")
def reset_user_password(user_id):
    target = User.get_by_id(user_id)
    if not target:
        return "User not found.", 404
    temporary_password = secrets.token_urlsafe(12)
    old_must_change = target.must_change_password
    target.set_temporary_password(temporary_password)
    record_audit(current_user, "update", "user", target.id, old_value={"must_change_password": old_must_change}, new_value={"must_change_password": True})
    return render_template("auth/temporary_password.html", target=target, temporary_password=temporary_password)


@auth_bp.get("/verify-email/<token>")
def verify_email(token):
    user = User.get_by_token("email_verification", token)
    if not user:
        flash("That verification link is invalid or expired.", "danger")
        return redirect(url_for("auth.login"))
    user.set_email_verified()
    user.clear_token("email_verification")
    flash("Email verified. You can now sign in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.get_by_email(email) if email else None
        if user:
            token = secrets.token_urlsafe(32)
            user.issue_token("password_reset", token, datetime.now(timezone.utc) + timedelta(minutes=current_app.config["PASSWORD_RESET_TTL_MINUTES"]))
            _send_reset(user, token)
        flash("If that email exists, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.get_by_token("password_reset", token)
    if not user:
        flash("That password reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.login"))
    form = PasswordChangeForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.clear_token("password_reset")
        flash("Password reset successfully. Please sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/password_change.html", form=form)


def _finish_login(user):
    session.clear()
    login_user(user)
    session["_session_created"] = time.time()
    session["_last_seen"] = time.time()
    session.permanent = True
    user.reset_login_failures()


def _active_admin_count():
    return db.db.users.count_documents({"role": "admin", "is_active": {"$ne": False}})


def _send_verification(user):
    token = secrets.token_urlsafe(32)
    user.issue_token("email_verification", token, datetime.now(timezone.utc) + timedelta(hours=current_app.config["EMAIL_VERIFICATION_TTL_HOURS"]))
    if current_app.config.get("SMTP_HOST"):
        send_email(user.email, "Verify your Risk Sentinel account", url_for("auth.verify_email", token=token, _external=True))


def _send_reset(user, token):
    if current_app.config.get("SMTP_HOST"):
        send_email(user.email, "Reset your Risk Sentinel password", url_for("auth.reset_password", token=token, _external=True))

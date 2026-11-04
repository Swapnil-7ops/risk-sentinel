from pathlib import Path

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, ValidationError

from app.models.asset import ASSET_TYPES
from app.models.user import User

COMMON_PASSWORDS = frozenset(
    password.strip().casefold()
    for password in (Path(__file__).parents[1] / "data" / "common_passwords.txt").read_text(encoding="utf-8").splitlines()
    if password.strip()
)


class RegistrationForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Register")

    def validate_email(self, field):
        if User.get_by_email(field.data):
            raise ValidationError("That email is already registered.")

    def validate_password(self, field):
        if field.data.casefold() in COMMON_PASSWORDS:
            raise ValidationError("Choose a less common password.")


class UserCreateForm(RegistrationForm):
    role = SelectField("Role", choices=[("admin", "Admin"), ("risk_owner", "Risk owner"), ("auditor", "Auditor")], validators=[DataRequired()])
    password = PasswordField("Temporary password")
    confirm_password = PasswordField("Confirm temporary password")


class MfaForm(FlaskForm):
    code = StringField("Authenticator code", validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField("Verify")


class UserRoleForm(FlaskForm):
    role = SelectField("Role", choices=[("admin", "Admin"), ("risk_owner", "Risk owner"), ("auditor", "Auditor")], validators=[DataRequired()])
    submit = SubmitField("Save role")


class UserStateForm(FlaskForm):
    is_active = BooleanField("Active")
    submit = SubmitField("Save status")


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField("Current password")
    password = PasswordField("New password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Change password")

    def validate_password(self, field):
        if field.data.casefold() in COMMON_PASSWORDS:
            raise ValidationError("Choose a less common password.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class AssetForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=1, max=150)])
    type = SelectField("Type", choices=[(value, value) for value in ASSET_TYPES], validators=[DataRequired()])
    owner = StringField("Owner", validators=[DataRequired(), Length(min=1, max=150)])
    criticality = IntegerField("Criticality", validators=[DataRequired(), NumberRange(min=1, max=5)])
    description = TextAreaField("Description", validators=[Length(max=2000)])
    submit = SubmitField("Save asset")


class RiskForm(FlaskForm):
    asset_id = StringField("Asset ID", validators=[DataRequired()])
    title = StringField("Title", validators=[DataRequired(), Length(min=1, max=200)])
    threat = TextAreaField("Threat", validators=[DataRequired(), Length(max=2000)])
    vulnerability = TextAreaField("Vulnerability", validators=[DataRequired(), Length(max=2000)])
    likelihood = IntegerField("Likelihood", validators=[DataRequired(), NumberRange(min=1, max=5)])
    impact = IntegerField("Impact", validators=[DataRequired(), NumberRange(min=1, max=5)])
    residual_likelihood = IntegerField("Residual likelihood", validators=[DataRequired(), NumberRange(min=1, max=5)])
    residual_impact = IntegerField("Residual impact", validators=[DataRequired(), NumberRange(min=1, max=5)])
    status = SelectField("Status", choices=[("Open", "Open"), ("In Treatment", "In Treatment"), ("Closed", "Closed")], validators=[DataRequired()])
    owner = StringField("Owner", validators=[DataRequired(), Length(max=150)])
    source = StringField("Source", validators=[DataRequired(), Length(max=150)])
    submit = SubmitField("Save risk")


class AppetiteForm(FlaskForm):
    threshold = IntegerField("Risk appetite threshold", validators=[DataRequired(), NumberRange(min=1, max=25)])
    submit = SubmitField("Save threshold")


class MappingForm(FlaskForm):
    control_ids = SelectMultipleField("Controls", choices=[], validators=[DataRequired()])
    treatment = SelectField("Treatment", choices=[(value, value) for value in ("Mitigate", "Accept", "Transfer", "Avoid")], validators=[DataRequired()])
    action_plan = TextAreaField("Action plan", validators=[DataRequired(), Length(max=2000)])
    owner = StringField("Owner", validators=[DataRequired(), Length(max=150)])
    due_date = StringField("Due date", validators=[Length(max=10)])
    status = SelectField("Status", choices=[(value, value) for value in ("Planned", "In Progress", "Implemented")], validators=[DataRequired()])
    submit = SubmitField("Map control")


class MappingStatusForm(FlaskForm):
    status = SelectField("Status", choices=[(value, value) for value in ("Planned", "In Progress", "Implemented")], validators=[DataRequired()])
    submit = SubmitField("Update status")


class MappingEvidenceForm(FlaskForm):
    evidence_url = StringField("Evidence link", validators=[DataRequired(), Length(max=500)])
    submit = SubmitField("Save evidence")


class MappingApprovalForm(FlaskForm):
    decision = SelectField("Decision", choices=[("Approved", "Approve"), ("Rejected", "Reject")], validators=[DataRequired()])
    comment = TextAreaField("Review comment", validators=[Length(max=1000)])
    submit = SubmitField("Save review")


class MappingEscalationForm(FlaskForm):
    reason = TextAreaField("Escalation reason", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Escalate")


class RiskApprovalForm(FlaskForm):
    decision = SelectField("Decision", choices=[("Accepted", "Accept risk"), ("Rejected", "Reject risk")], validators=[DataRequired()])
    rationale = TextAreaField("Rationale", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Save decision")
from pathlib import Path

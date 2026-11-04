from datetime import datetime, timedelta, timezone
import hashlib

from bson import ObjectId
from bson.errors import InvalidId
from flask_login import UserMixin

from app import bcrypt, db


class User(UserMixin):
    def __init__(self, document):
        self.id = str(document["_id"])
        self.name = document["name"]
        self.email = document["email"]
        self.password_hash = document["password_hash"]
        self.role = document["role"]
        self.failed_attempts = document.get("failed_attempts", 0)
        self.locked_until = document.get("locked_until")
        self.must_change_password = document.get("must_change_password", False)
        self._is_active = document.get("is_active", True)
        self.email_verified = document.get("email_verified", False)
        self.mfa_enabled = document.get("mfa_enabled", False)
        self.mfa_secret = document.get("mfa_secret")

    @staticmethod
    def get_by_id(user_id):
        try:
            document = db.db.users.find_one({"_id": ObjectId(user_id)})
        except InvalidId:
            return None
        return User(document) if document else None

    @staticmethod
    def get_by_email(email):
        document = db.db.users.find_one({"email": email.strip().lower()})
        return User(document) if document else None

    @staticmethod
    def create(name, email, password, role=None, must_change_password=False):
        normalized_email = email.strip().lower()
        role = role or ("admin" if db.db.users.count_documents({}) == 0 else "risk_owner")
        document = {
            "name": name.strip(),
            "email": normalized_email,
            "password_hash": bcrypt.generate_password_hash(password).decode("utf-8"),
            "role": role,
            "failed_attempts": 0,
            "must_change_password": must_change_password,
            "created_at": datetime.now(timezone.utc),
        }
        result = db.db.users.insert_one(document)
        document["_id"] = result.inserted_id
        return User(document)

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @staticmethod
    def register_allowed(allow_registration):
        return allow_registration or db.db.users.count_documents({}) == 0

    def is_locked(self):
        if not self.locked_until:
            return False
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            return True
        db.db.users.update_one(
            {"_id": ObjectId(self.id), "locked_until": {"$lte": datetime.now(timezone.utc)}},
            {"$set": {"failed_attempts": 0}, "$unset": {"locked_until": ""}},
        )
        self.failed_attempts = 0
        self.locked_until = None
        return False

    def record_failed_login(self):
        if self.is_locked():
            return
        now = datetime.now(timezone.utc)
        update = {"$inc": {"failed_attempts": 1}}
        if self.failed_attempts + 1 >= 5:
            update["$set"] = {"locked_until": now + timedelta(minutes=15)}
        db.db.users.update_one({"_id": ObjectId(self.id)}, update)

    def reset_login_failures(self):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"failed_attempts": 0}, "$unset": {"locked_until": ""}},
        )

    def set_password(self, password):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"password_hash": bcrypt.generate_password_hash(password).decode("utf-8"), "must_change_password": False}},
        )

    def get_document(self):
        return db.db.users.find_one({"_id": ObjectId(self.id)})

    @property
    def is_active(self):
        return self._is_active

    @staticmethod
    def list_all():
        return [User(document) for document in db.db.users.find({}).sort("email", 1)]

    def update_admin_state(self, *, role=None, is_active=None):
        update = {}
        if role is not None:
            update["role"] = role
        if is_active is not None:
            update["is_active"] = is_active
        if update:
            db.db.users.update_one({"_id": ObjectId(self.id)}, {"$set": update})
            if role is not None:
                self.role = role
            if is_active is not None:
                self._is_active = is_active

    def enable_mfa(self, secret):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"mfa_secret": secret, "mfa_enabled": True}},
        )
        self.mfa_secret = secret
        self.mfa_enabled = True

    def disable_mfa(self):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"mfa_enabled": False}, "$unset": {"mfa_secret": ""}},
        )
        self.mfa_secret = None
        self.mfa_enabled = False

    def set_email_verified(self, verified=True):
        db.db.users.update_one({"_id": ObjectId(self.id)}, {"$set": {"email_verified": verified}})
        self.email_verified = verified

    def set_temporary_password(self, password):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"password_hash": bcrypt.generate_password_hash(password).decode("utf-8"), "must_change_password": True}},
        )
        self.must_change_password = True

    def issue_token(self, field, token, expires_at):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {f"{field}_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(), f"{field}_expires_at": expires_at}},
        )

    @staticmethod
    def get_by_token(field, token):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        document = db.db.users.find_one(
            {f"{field}_hash": token_hash, f"{field}_expires_at": {"$gt": datetime.now(timezone.utc)}}
        )
        return User(document) if document else None

    def clear_token(self, field):
        db.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$unset": {f"{field}_hash": "", f"{field}_expires_at": ""}},
        )

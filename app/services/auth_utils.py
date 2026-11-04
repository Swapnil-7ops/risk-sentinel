from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or not getattr(current_user, "is_active", True) or current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def active_user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_active:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def safe_string(value, *, max_length=254):
    if not isinstance(value, str) or len(value) > max_length:
        abort(400)
    if any(token in value for token in ("$", "{", "}")):
        abort(400)
    return value

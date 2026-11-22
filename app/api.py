import re
from datetime import timezone
from functools import wraps

from flask import g, request


class APIError(Exception):
    def __init__(self, status, message, details=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details


def require_user(role=None):
    def decorator(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            if g.user is None:
                raise APIError(401, "Sign in to continue.")
            if role and g.user.role != role:
                raise APIError(403, "Your account does not have permission for this action.")
            return function(*args, **kwargs)

        return guarded
    return decorator


def payload():
    if not request.data:
        return {}
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError(400, "Send a JSON object.")
    return data


def integer(value, label, minimum=1, maximum=2147483647):
    if type(value) is int:
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]{1,10}", value):
        number = int(value)
    else:
        raise APIError(400, f"{label} must be a whole number.")
    if not minimum <= number <= maximum:
        raise APIError(400, f"{label} must be between {minimum} and {maximum}.")
    return number


def string(value, label, maximum, required=True):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or "\x00" in value:
        raise APIError(400, f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise APIError(400, f"{label} is required.")
    if len(value) > maximum:
        raise APIError(400, f"{label} must have at most {maximum} characters.")
    return value


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if value else None

import re

from flask import Blueprint, g, session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash

from app import csrf_token
from app.api import APIError, payload, require_user, string
from app.extensions import db
from app.models import User
from app.passwords import hash_password
from app.serializers import user_data


auth = Blueprint("auth", __name__, url_prefix="/api")
EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+")


def email_address(value):
    email = string(value, "Email", 255).lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise APIError(400, "Enter a valid email address.")
    return email


def password_value(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or "\x00" in value:
        raise APIError(400, "Enter a password of at most 128 characters.")
    return value


def interest_list(value):
    if not isinstance(value, list) or len(value) > 20:
        raise APIError(400, "Provide up to 20 interests as a list.")
    interests = {}
    for item in value:
        label = string(item, "Interest", 100)
        interests.setdefault(label.casefold(), label)
    return list(interests.values())


def find_by_email(email):
    return db.session.scalar(db.select(User).where(User.email == email))


def session_data(user):
    return {"user": user_data(user) if user else None, "csrf_token": csrf_token()}


def sign_in(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user.user_id
    return session_data(user)


def save_user():
    try:
        db.session.commit()
    except IntegrityError as error:
        if getattr(error.orig, "args", (None,))[0] == 1062:
            raise APIError(409, "An account already uses this email address.") from error
        raise


@auth.get("/session")
def get_session():
    return session_data(g.user)


@auth.post("/auth/register")
def register():
    data = payload()
    if data.get("role", "student") != "student":
        raise APIError(400, "Self-registration is available for students.")
    name = string(data.get("name"), "Name", 120)
    email = email_address(data.get("email"))
    password = password_value(data.get("password"))
    if len(password) < 8:
        raise APIError(400, "Passwords must have at least 8 characters.")
    interests = interest_list(data.get("interests", []))
    if find_by_email(email):
        raise APIError(409, "An account already uses this email address.")
    user = User(name=name, email=email, role="student", password_hash=hash_password(password),
                interests=interests)
    db.session.add(user)
    save_user()
    return sign_in(user), 201


@auth.post("/auth/login")
def login():
    data = payload()
    user = find_by_email(email_address(data.get("email")))
    password = password_value(data.get("password"))
    if user is None or not check_password_hash(user.password_hash, password):
        raise APIError(401, "The email or password is incorrect.")
    return sign_in(user)


@auth.post("/auth/logout")
def logout():
    session.clear()
    return session_data(None)


@auth.get("/me")
@require_user()
def me():
    return user_data(g.user)


@auth.patch("/me")
@require_user()
def edit_profile():
    data = payload()
    if set(data) - {"name", "email", "interests"}:
        raise APIError(400, "You can update your name, email, and interests.")
    if "name" in data:
        g.user.name = string(data["name"], "Name", 120)
    if "email" in data:
        g.user.email = email_address(data["email"])
    if "interests" in data:
        g.user.interests = interest_list(data["interests"])
    save_user()
    return user_data(g.user)

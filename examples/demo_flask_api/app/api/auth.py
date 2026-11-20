"""Authentication endpoints (registration, login, profile)."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import User
from app.schemas import (
    user_login_schema,
    user_register_schema,
    user_schema,
    user_update_schema,
)
from app.utils.helpers import error_response, load_current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _load_json(schema, partial=False):
    """Validate the JSON request body, raising `ValidationError` on failure."""
    return schema.load(request.get_json(silent=True) or {}, partial=partial)


@auth_bp.post("/register")
def register():
    """Register a new user and return an access token."""
    try:
        data = _load_json(user_register_schema)
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    email = data["email"].lower()
    if User.query.filter_by(username=data["username"]).first():
        return error_response(409, "This username is already taken.")
    if User.query.filter_by(email=email).first():
        return error_response(409, "This email is already registered.")

    user = User(username=data["username"], email=email, bio=data.get("bio"))
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return (
        jsonify({"user": user_schema.dump(user), "access_token": token}),
        201,
    )


@auth_bp.post("/login")
def login():
    """Authenticate with a username (or email) + password."""
    try:
        data = _load_json(user_login_schema)
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    identifier = data["username"].strip()
    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier.lower())
    ).first()

    if user is None or not user.check_password(data["password"]):
        return error_response(401, "Invalid username or password.")

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "user": user_schema.dump(user)}), 200


@auth_bp.get("/me")
@jwt_required()
def get_me():
    """Return the authenticated user's profile."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")
    return jsonify(user_schema.dump(user))


@auth_bp.patch("/me")
@jwt_required()
def update_me():
    """Update the authenticated user's bio and/or password."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    try:
        data = _load_json(user_update_schema, partial=True)
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    if data.get("bio") is not None:
        user.bio = data["bio"]
    if data.get("password"):
        user.set_password(data["password"])

    db.session.commit()
    return jsonify(user_schema.dump(user))


@auth_bp.delete("/me")
@jwt_required()
def delete_me():
    """Delete the authenticated account and all of its content."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    db.session.delete(user)
    db.session.commit()
    return "", 204

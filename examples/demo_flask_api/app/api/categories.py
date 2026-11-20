"""Category endpoints."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy import func

from app.extensions import db
from app.models import Category
from app.schemas import (
    categories_schema,
    category_create_schema,
    category_schema,
    category_update_schema,
)
from app.utils.helpers import (
    error_response,
    get_or_404,
    load_current_user,
    unique_slug,
)

categories_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@categories_bp.get("")
def list_categories():
    """List every category (public)."""
    query = Category.query.order_by(Category.name.asc())
    search = request.args.get("q")
    if search:
        query = query.filter(Category.name.ilike(f"%{search}%"))
    return jsonify(categories_schema.dump(query.all()))


@categories_bp.post("")
@jwt_required()
def create_category():
    """Create a category (authenticated)."""
    if load_current_user() is None:
        return error_response(401, "The user linked to this token no longer exists.")

    try:
        data = category_create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    if Category.query.filter(func.lower(Category.name) == data["name"].lower()).first():
        return error_response(409, "This category already exists.")

    category = Category(
        name=data["name"],
        slug=unique_slug(Category, data["name"]),
        description=data.get("description"),
    )
    db.session.add(category)
    db.session.commit()
    return jsonify(category_schema.dump(category)), 201


@categories_bp.get("/<int:category_id>")
def get_category(category_id):
    """Retrieve a single category (public)."""
    category = get_or_404(Category, category_id)
    return jsonify(category_schema.dump(category))


@categories_bp.route("/<int:category_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_category(category_id):
    """Update a category (authenticated)."""
    if load_current_user() is None:
        return error_response(401, "The user linked to this token no longer exists.")

    category = get_or_404(Category, category_id)
    raw = request.get_json(silent=True) or {}
    try:
        data = category_update_schema.load(raw)
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    if data.get("name") is not None and data["name"] != category.name:
        clash = Category.query.filter(
            func.lower(Category.name) == data["name"].lower(),
            Category.id != category.id,
        ).first()
        if clash:
            return error_response(409, "This category already exists.")
        category.name = data["name"]
        category.slug = unique_slug(Category, data["name"], exclude_id=category.id)

    if "description" in raw:
        category.description = data.get("description")

    db.session.commit()
    return jsonify(category_schema.dump(category))


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    """Delete a category (authenticated). Articles keep existing, uncategorized."""
    if load_current_user() is None:
        return error_response(401, "The user linked to this token no longer exists.")

    category = get_or_404(Category, category_id)
    db.session.delete(category)
    db.session.commit()
    return "", 204

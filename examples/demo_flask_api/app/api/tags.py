"""Tag (hashtag) endpoints."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import Tag
from app.schemas import tag_create_schema, tag_schema, tags_schema
from app.utils.helpers import error_response, get_or_404, load_current_user, slugify

tags_bp = Blueprint("tags", __name__, url_prefix="/api/tags")


@tags_bp.get("")
def list_tags():
    """List every hashtag, most used first (public)."""
    search = request.args.get("q")
    query = Tag.query
    if search:
        query = query.filter(Tag.name.ilike(f"%{search.lstrip('#')}%"))
    tags = query.all()
    tags.sort(key=lambda tag: (-len(tag.articles), tag.name.lower()))
    limit = request.args.get("limit", type=int)
    if limit:
        tags = tags[:limit]
    return jsonify(tags_schema.dump(tags))


@tags_bp.post("")
@jwt_required()
def create_tag():
    """Create a hashtag (authenticated)."""
    if load_current_user() is None:
        return error_response(401, "The user linked to this token no longer exists.")

    try:
        data = tag_create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    name = data["name"].strip().lstrip("#")
    slug = slugify(name)
    if Tag.query.filter_by(slug=slug).first():
        return error_response(409, "This tag already exists.")

    tag = Tag(name=name, slug=slug)
    db.session.add(tag)
    db.session.commit()
    return jsonify(tag_schema.dump(tag)), 201


@tags_bp.get("/<int:tag_id>")
def get_tag(tag_id):
    """Retrieve a single hashtag (public)."""
    tag = get_or_404(Tag, tag_id)
    return jsonify(tag_schema.dump(tag))


@tags_bp.delete("/<int:tag_id>")
@jwt_required()
def delete_tag(tag_id):
    """Delete a hashtag (authenticated). Articles are kept."""
    if load_current_user() is None:
        return error_response(401, "The user linked to this token no longer exists.")

    tag = get_or_404(Tag, tag_id)
    db.session.delete(tag)
    db.session.commit()
    return "", 204

"""Comment endpoints."""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import Article, Comment
from app.schemas import (
    comment_create_schema,
    comment_schema,
    comment_update_schema,
    comments_schema
)
from app.utils.helpers import (
    error_response,
    get_or_404,
    load_current_user,
    paginated_response,
)

comments_bp = Blueprint("comments", __name__)


# --------------------------------------------------------------------------
# Comments on an article
# --------------------------------------------------------------------------
@comments_bp.get("/api/articles/<int:article_id>/comments")
def list_comments(article_id):
    """List the comments of an article, oldest first (public)."""
    get_or_404(Article, article_id)

    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per_page = request.args.get("per_page", 20, type=int) or 20
    per_page = min(max(per_page, 1), current_app.config["MAX_PER_PAGE"])

    query = (
        Comment.query.filter_by(article_id=article_id)
        .order_by(Comment.created_at.asc())
    )
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return paginated_response(pagination, comments_schema.dump)


@comments_bp.post("/api/articles/<int:article_id>/comments")
@jwt_required()
def create_comment(article_id):
    """Post a comment on an article (authenticated)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    article = get_or_404(Article, article_id)

    try:
        data = comment_create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    comment = Comment(
        content=data["content"], author_id=user.id, article_id=article.id
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment_schema.dump(comment)), 201


@comments_bp.get("/api/comments/<int:comment_id>")
def get_comment(comment_id):
    """Retrieve a single comment (public)."""
    comment = get_or_404(Comment, comment_id)
    return jsonify(comment_schema.dump(comment))


@comments_bp.route("/api/comments/<int:comment_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_comment(comment_id):
    """Edit your own comment (authenticated, owner only)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    comment = get_or_404(Comment, comment_id)
    if comment.author_id != user.id:
        return error_response(403, "You can only modify your own comments.")

    try:
        data = comment_update_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    comment.content = data["content"]
    db.session.commit()
    return jsonify(comment_schema.dump(comment))


@comments_bp.delete("/api/comments/<int:comment_id>")
@jwt_required()
def delete_comment(comment_id):
    """Delete your own comment (authenticated, owner only)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    comment = get_or_404(Comment, comment_id)
    if comment.author_id != user.id:
        return error_response(403, "You can only delete your own comments.")

    db.session.delete(comment)
    db.session.commit()
    return "", 204


# Convenience: every comment written by a user (public).
@comments_bp.get("/api/users/<int:user_id>/comments")
def list_user_comments(user_id):
    """List the comments written by a user (public)."""
    from app.models import User

    get_or_404(User, user_id)
    comments = (
        Comment.query.filter_by(author_id=user_id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    return jsonify(comments_schema.dump(comments))

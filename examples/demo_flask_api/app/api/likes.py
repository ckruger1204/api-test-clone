"""Like endpoints."""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Article, Like
from app.schemas import public_users_schema
from app.utils.helpers import current_user, error_response, get_or_404, load_current_user

likes_bp = Blueprint("likes", __name__)


def _like_payload(article, message):
    return {
        "message": message,
        "article_id": article.id,
        "likes_count": article.likes_count,
        "liked_by_me": True,
    }


@likes_bp.get("/api/articles/<int:article_id>/likes")
@jwt_required(optional=True)
def list_likes(article_id):
    """List the users who liked an article (public)."""
    load_current_user()
    article = get_or_404(Article, article_id)
    likes = (
        Like.query.filter_by(article_id=article.id)
        .order_by(Like.created_at.desc())
        .all()
    )
    return jsonify(
        {
            "article_id": article.id,
            "likes_count": len(likes),
            "liked_by_me": article.is_liked_by(current_user()),
            "users": public_users_schema.dump([like.user for like in likes]),
        }
    )


@likes_bp.post("/api/articles/<int:article_id>/likes")
@jwt_required()
def like_article(article_id):
    """Like an article (authenticated). Idempotent."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    article = get_or_404(Article, article_id)

    existing = Like.query.filter_by(user_id=user.id, article_id=article.id).first()
    if existing is not None:
        return jsonify(_like_payload(article, "You already liked this article.")), 200

    db.session.add(Like(user_id=user.id, article_id=article.id))
    db.session.commit()
    return jsonify(_like_payload(article, "Article liked.")), 201


@likes_bp.delete("/api/articles/<int:article_id>/likes")
@jwt_required()
def unlike_article(article_id):
    """Remove your like from an article (authenticated, owner only)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    article = get_or_404(Article, article_id)

    like = Like.query.filter_by(user_id=user.id, article_id=article.id).first()
    if like is None:
        return error_response(404, "You have not liked this article.")

    db.session.delete(like)
    db.session.commit()
    return "", 204

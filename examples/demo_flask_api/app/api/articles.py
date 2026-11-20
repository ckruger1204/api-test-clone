"""Article endpoints."""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import Article, Category, Tag, article_tags
from app.schemas import (
    article_create_schema,
    article_schema,
    articles_schema,
    article_update_schema,
)
from app.utils.helpers import (
    current_user,
    error_response,
    get_or_404,
    load_current_user,
    paginated_response,
    slugify,
    unique_slug,
)

articles_bp = Blueprint("articles", __name__, url_prefix="/api/articles")


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------
def _resolve_tags(tag_names):
    """Return `Tag` objects for the given names, creating missing ones."""
    resolved = []
    for raw_name in tag_names or []:
        name = (raw_name or "").strip().lstrip("#")
        if not name:
            continue
        slug = slugify(name)
        tag = Tag.query.filter_by(slug=slug).first()
        if tag is None:
            tag = Tag(name=name, slug=slug)
            db.session.add(tag)
            db.session.flush()
        if tag not in resolved:
            resolved.append(tag)
    return resolved


def _default_summary(content, limit=200):
    content = " ".join((content or "").split())
    return content[:limit] + ("…" if len(content) > limit else "")


def _pagination_args():
    per_page_default = current_app.config["ARTICLES_PER_PAGE"]
    max_per_page = current_app.config["MAX_PER_PAGE"]
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", per_page_default, type=int)
    if per_page is None or per_page < 1:
        per_page = per_page_default
    return max(page, 1), min(per_page, max_per_page)


# --------------------------------------------------------------------------
# Read endpoints (public)
# --------------------------------------------------------------------------
@articles_bp.get("")
@jwt_required(optional=True)
def list_articles():
    """List articles with filtering, sorting and pagination (public).

    Query parameters: `page`, `per_page`, `category` (slug), `tag` (slug),
    `author` (username), `q` (search in title/content), `published`, `sort`.
    """
    load_current_user()
    user = current_user()

    query = Article.query

    category_slug = request.args.get("category")
    if category_slug:
        query = query.join(Category, Article.category_id == Category.id).filter(
            Category.slug == category_slug
        )

    tag_slug = request.args.get("tag")
    if tag_slug:
        query = (
            query.join(article_tags, Article.id == article_tags.c.article_id)
            .join(Tag, Tag.id == article_tags.c.tag_id)
            .filter(Tag.slug == slugify(tag_slug))
        )

    author = request.args.get("author")
    if author:
        from app.models import User

        query = query.join(User, Article.author_id == User.id).filter(
            User.username == author
        )

    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Article.title.ilike(like), Article.summary.ilike(like),
                Article.content.ilike(like))
        )

    published_param = request.args.get("published")
    if published_param is None:
        if user is None:
            query = query.filter(Article.published.is_(True))
    elif published_param.lower() in {"1", "true", "yes"}:
        query = query.filter(Article.published.is_(True))
    else:
        if user is None:
            return error_response(
                401, "Authentication is required to list unpublished articles."
            )
        # Drafts are private: only your own.
        query = query.filter(
            Article.published.is_(False), Article.author_id == user.id
        )

    sort = request.args.get("sort", "recent")
    if sort == "oldest":
        query = query.order_by(Article.created_at.asc())
    elif sort == "title":
        query = query.order_by(Article.title.asc())
    else:
        query = query.order_by(Article.created_at.desc())

    page, per_page = _pagination_args()
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return paginated_response(pagination, articles_schema.dump)


@articles_bp.get("/<int:article_id>")
@jwt_required(optional=True)
def get_article(article_id):
    """Retrieve a single article (public)."""
    load_current_user()
    user = current_user()
    article = get_or_404(Article, article_id)

    if not article.published:
        if user is None or article.author_id != user.id:
            return error_response(403, "This article is not published yet.")

    return jsonify(article_schema.dump(article))


# --------------------------------------------------------------------------
# Write endpoints (authenticated)
# --------------------------------------------------------------------------
@articles_bp.post("")
@jwt_required()
def create_article():
    """Create an article (authenticated)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    try:
        data = article_create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    category_id = data.get("category_id")
    if category_id is not None and db.session.get(Category, category_id) is None:
        return error_response(400, "Validation failed.", {"category_id": ["Unknown category."]})

    article = Article(
        title=data["title"],
        slug=unique_slug(Article, data["title"]),
        content=data["content"],
        summary=data.get("summary") or _default_summary(data["content"]),
        published=data.get("published", True),
        author_id=user.id,
        category_id=category_id,
    )
    article.tags = _resolve_tags(data.get("tags"))
    db.session.add(article)
    db.session.commit()
    return jsonify(article_schema.dump(article)), 201


@articles_bp.route("/<int:article_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_article(article_id):
    """Update one of your articles (authenticated, owner only)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    article = get_or_404(Article, article_id)
    if article.author_id != user.id:
        return error_response(403, "You can only modify your own articles.")

    raw = request.get_json(silent=True) or {}
    try:
        data = article_update_schema.load(raw)
    except ValidationError as err:
        return error_response(400, "Validation failed.", err.messages)

    if data.get("title") is not None and data["title"] != article.title:
        article.title = data["title"]
        article.slug = unique_slug(Article, data["title"], exclude_id=article.id)

    if data.get("content") is not None:
        article.content = data["content"]

    if "summary" in raw:
        article.summary = data.get("summary") or _default_summary(article.content)

    if data.get("published") is not None:
        article.published = data["published"]

    if "category_id" in raw:
        category_id = data.get("category_id")
        if category_id is not None and db.session.get(Category, category_id) is None:
            return error_response(
                400, "Validation failed.", {"category_id": ["Unknown category."]}
            )
        article.category_id = category_id

    if data.get("tags") is not None:
        article.tags = _resolve_tags(data["tags"])

    db.session.commit()
    return jsonify(article_schema.dump(article))


@articles_bp.delete("/<int:article_id>")
@jwt_required()
def delete_article(article_id):
    """Delete one of your articles (authenticated, owner only)."""
    user = load_current_user()
    if user is None:
        return error_response(401, "The user linked to this token no longer exists.")

    article = get_or_404(Article, article_id)
    if article.author_id != user.id:
        return error_response(403, "You can only delete your own articles.")

    db.session.delete(article)
    db.session.commit()
    return "", 204

"""Model package.

Importing the models here guarantees that they are all registered on the
SQLAlchemy metadata before `db.create_all()` runs.
"""
from app.models.article import Article, article_tags
from app.models.base import TimestampMixin, utcnow
from app.models.category import Category
from app.models.comment import Comment
from app.models.like import Like
from app.models.tag import Tag
from app.models.user import User

__all__ = [
    "Article",
    "article_tags",
    "TimestampMixin",
    "utcnow",
    "Category",
    "Comment",
    "Like",
    "Tag",
    "User",
]

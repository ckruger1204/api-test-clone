"""Category model: one article belongs to at most one category."""
from app.extensions import db
from app.models.base import TimestampMixin


class Category(db.Model, TimestampMixin):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)

    articles = db.relationship("Article", back_populates="category")

    def __repr__(self):  # pragma: no cover
        return f"<Category {self.name}>"

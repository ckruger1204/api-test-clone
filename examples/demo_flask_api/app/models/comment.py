"""Comment model."""
from app.extensions import db
from app.models.base import TimestampMixin


class Comment(db.Model, TimestampMixin):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)

    author_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    article_id = db.Column(
        db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )

    author = db.relationship("User", back_populates="comments")
    article = db.relationship("Article", back_populates="comments")

    def __repr__(self):  # pragma: no cover
        return f"<Comment {self.id} on article {self.article_id}>"

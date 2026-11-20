"""Like model: a user can like an article at most once."""
from app.extensions import db
from app.models.base import utcnow


class Like(db.Model):
    __tablename__ = "likes"
    __table_args__ = (
        db.UniqueConstraint("user_id", "article_id", name="uq_like_user_article"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    article_id = db.Column(
        db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="likes")
    article = db.relationship("Article", back_populates="likes")

    def __repr__(self):  # pragma: no cover
        return f"<Like user={self.user_id} article={self.article_id}>"

"""Tag model (hashtags). An article can have many tags."""
from app.extensions import db


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)

    articles = db.relationship(
        "Article", secondary="article_tags", back_populates="tags"
    )

    def __repr__(self):  # pragma: no cover
        return f"<Tag #{self.name}>"

"""Article model + the article <-> tag association table."""
from app.extensions import db
from app.models.base import TimestampMixin

# Many-to-many join table between articles and tags (hashtags).
article_tags = db.Table(
    "article_tags",
    db.Column(
        "article_id",
        db.Integer,
        db.ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Article(db.Model, TimestampMixin):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(300), nullable=True)
    content = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, default=True, nullable=False, index=True)

    author_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    author = db.relationship("User", back_populates="articles")
    category = db.relationship("Category", back_populates="articles")
    tags = db.relationship(
        "Tag", secondary=article_tags, back_populates="articles", lazy="selectin"
    )
    comments = db.relationship(
        "Comment",
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    likes = db.relationship(
        "Like", back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )

    # --- computed helpers --------------------------------------------
    @property
    def comments_count(self) -> int:
        return len(self.comments)

    @property
    def likes_count(self) -> int:
        return len(self.likes)

    def is_liked_by(self, user) -> bool:
        if user is None:
            return False
        return any(like.user_id == user.id for like in self.likes)

    def __repr__(self):  # pragma: no cover
        return f"<Article {self.slug}>"

"""User model."""
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True)

    # Relationships
    articles = db.relationship(
        "Article", back_populates="author", cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "Comment", back_populates="author", cascade="all, delete-orphan"
    )
    likes = db.relationship(
        "Like", back_populates="user", cascade="all, delete-orphan"
    )

    # --- helpers ------------------------------------------------------
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def articles_count(self) -> int:
        return len(self.articles)

    def __repr__(self):  # pragma: no cover
        return f"<User {self.username}>"

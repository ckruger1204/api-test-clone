"""Shared model helpers."""
from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds `created_at` / `updated_at` columns to a model."""

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

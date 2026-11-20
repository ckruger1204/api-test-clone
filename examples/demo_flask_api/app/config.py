"""Application configuration."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _engine_options(uri):
    """SQLite-specific engine options; safe for other database backends."""
    options = {"pool_pre_ping": True}
    if str(uri).startswith("sqlite"):
        # Allow the connection to be shared with the Flask development server.
        options["connect_args"] = {"check_same_thread": False}
    return options


class Config:
    """Base configuration, driven by environment variables."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # --- Database -----------------------------------------------------
    # Defaults to a local SQLite file living at the project root.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'blog.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)

    # --- JWT ----------------------------------------------------------
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "12"))
    )
    JWT_ERROR_MESSAGE_KEY = "message"

    # --- Misc ---------------------------------------------------------
    ARTICLES_PER_PAGE = int(os.getenv("ARTICLES_PER_PAGE", "10"))
    MAX_PER_PAGE = 100
    AUTO_CREATE_TABLES = _as_bool(os.getenv("AUTO_CREATE_TABLES"), default=True)


class TestConfig(Config):
    """Configuration used by the test-suite (in-memory database)."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    AUTO_CREATE_TABLES = True
    JWT_SECRET_KEY = "test-jwt-secret"

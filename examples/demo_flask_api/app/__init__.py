"""Application factory."""
import click
from flask import Flask, jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import db, jwt, migrate
from app.utils.helpers import error_response


def create_app(config_class=Config):
    """Build and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False

    # --- extensions ---------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # --- application pieces -------------------------------------------
    from app.api import register_blueprints

    register_blueprints(app)
    register_root_routes(app)
    register_error_handlers(app)
    register_jwt_handlers(app)
    register_cli(app)

    with app.app_context():
        # Importing the models registers them on the SQLAlchemy metadata.
        from app import models  # noqa: F401

        if app.config.get("AUTO_CREATE_TABLES"):
            db.create_all()

    return app


# --------------------------------------------------------------------------
# Root / meta routes
# --------------------------------------------------------------------------
def register_root_routes(app):
    @app.get("/")
    def index():
        return jsonify(
            {
                "name": "Flask Blog API",
                "version": "1.0.0",
                "documentation": {
                    "swagger_ui": "/docs",
                    "openapi_yaml": "/openapi.yaml",
                    "openapi_json": "/openapi.json",
                },
                "endpoints": {
                    "auth": "/api/auth",
                    "articles": "/api/articles",
                    "categories": "/api/categories",
                    "tags": "/api/tags",
                    "comments": "/api/articles/<article_id>/comments",
                    "likes": "/api/articles/<article_id>/likes",
                },
            }
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------
def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return error_response(400, "Validation failed.", error.messages)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return error_response(error.code, error.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Let the debugger / test-suite see the real traceback.
        if app.config.get("TESTING") or app.debug:
            raise error

        db.session.rollback()
        app.logger.exception("Unhandled exception")
        return error_response(500, "An unexpected error occurred.")


# --------------------------------------------------------------------------
# JWT error handling
# --------------------------------------------------------------------------
def register_jwt_handlers(app):
    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response(
            401, "Missing or invalid Authorization header.", {"reason": reason}
        )

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response(401, "Invalid token.", {"reason": reason})

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response(401, "The token has expired.")

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return error_response(401, "The token has been revoked.")

    @jwt.user_lookup_error_loader
    def user_lookup_error(jwt_header, jwt_payload):
        return error_response(
            401, "The user linked to this token no longer exists."
        )


# --------------------------------------------------------------------------
# CLI commands (`flask --app run.py <command>`)
# --------------------------------------------------------------------------
def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create every database table."""
        db.create_all()
        click.echo("✔ Database tables created.")

    @app.cli.command("drop-db")
    def drop_db():
        """Drop every database table."""
        db.drop_all()
        click.echo("✔ Database tables dropped.")

    @app.cli.command("seed")
    def seed_command():
        """Populate the database with demo users, articles, comments and likes."""
        from app.seed import seed

        seed()
        click.echo("✔ Demo data inserted.")

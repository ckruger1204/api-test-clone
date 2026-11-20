"""Blueprint registry."""
from app.api.articles import articles_bp
from app.api.auth import auth_bp
from app.api.categories import categories_bp
from app.api.comments import comments_bp
from app.api.docs import docs_bp
from app.api.likes import likes_bp
from app.api.tags import tags_bp

BLUEPRINTS = (
    auth_bp,
    articles_bp,
    categories_bp,
    tags_bp,
    comments_bp,
    likes_bp,
    docs_bp,
)


def register_blueprints(app):
    """Attach every blueprint to the application."""
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

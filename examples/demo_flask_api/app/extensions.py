"""Flask extension instances.

They are created here (without an app) so that models, schemas and blueprints
can import them without creating circular imports, then bound to the app
inside the application factory.
"""
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite disables foreign keys by default; enable them per connection.

    Without this, `ON DELETE CASCADE` / `ON DELETE SET NULL` declared on the
    models would silently be ignored.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

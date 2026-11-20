"""Generic helpers used across the API."""
import re
import unicodedata

from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity

from app.extensions import db


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------
def error_response(status_code, message, details=None):
    """Build a consistent JSON error payload."""
    payload = {"error": {"code": status_code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status_code


# --------------------------------------------------------------------------
# Authentication helpers
# --------------------------------------------------------------------------
def load_current_user():
    """Resolve the authenticated user (if any) and cache it on `flask.g`.

    Must be called from a view protected with `@jwt_required(optional=True)`
    or `@jwt_required()`. Returns `None` for anonymous requests.
    """
    g.current_user = None
    try:
        identity = get_jwt_identity()
    except RuntimeError:
        # No JWT context at all (neither required nor optional).
        return None
    if identity is not None:
        from app.models import User

        g.current_user = db.session.get(User, int(identity))
    return g.current_user


def current_user():
    """Return the user cached on `flask.g` by :func:`load_current_user`."""
    return g.get("current_user")


def get_or_404(model, object_id):
    """Fetch a row by primary key or abort with the standard 404 payload."""
    obj = db.session.get(model, object_id)
    if obj is None:
        from werkzeug.exceptions import NotFound

        raise NotFound(f"{model.__name__} with id {object_id} was not found.")
    return obj


# --------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------
def paginated_response(pagination, dump_fn, extra_meta=None):
    """Serialize a Flask-SQLAlchemy `Pagination` object into a JSON response.

    Layout::

        {
          "items": [...],
          "meta": {"page": 1, "per_page": 10, "total": 3, "pages": 1,
                   "has_next": false, "has_prev": false}
        }
    """
    meta = {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }
    if extra_meta:
        meta.update(extra_meta)
    return jsonify({"items": dump_fn(pagination.items), "meta": meta})


# --------------------------------------------------------------------------
# Slugs
# --------------------------------------------------------------------------
def slugify(value: str) -> str:
    """Turn an arbitrary string into a URL-friendly slug."""
    value = unicodedata.normalize("NFKD", str(value))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value or "item"


def unique_slug(model, base_value: str, exclude_id=None) -> str:
    """Generate a slug that is unique for `model`.

    Appends `-2`, `-3`, ... when a collision is found.
    """
    base = slugify(base_value)
    candidate = base
    counter = 2
    while True:
        query = model.query.filter(model.slug == candidate)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1

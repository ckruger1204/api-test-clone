"""Documentation endpoints: serve the OpenAPI spec and a Swagger UI page."""
from pathlib import Path

import yaml
from flask import Blueprint, current_app, jsonify, render_template, send_from_directory

docs_bp = Blueprint("docs", __name__)

SPEC_FILENAME = "openapi.yaml"


def _spec_path() -> Path:
    return Path(current_app.root_path).parent / SPEC_FILENAME


@docs_bp.get("/openapi.yaml")
def openapi_spec():
    """Return the raw OpenAPI 3.0 document."""
    path = _spec_path()
    if not path.exists():
        return jsonify({"error": {"code": 404, "message": "openapi.yaml not found."}}), 404
    return send_from_directory(path.parent, path.name, mimetype="application/yaml")


@docs_bp.get("/openapi.json")
def openapi_spec_json():
    """Return the OpenAPI document converted to JSON."""
    path = _spec_path()
    if not path.exists():
        return jsonify({"error": {"code": 404, "message": "openapi.yaml not found."}}), 404
    with path.open("r", encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)
    return jsonify(spec)


@docs_bp.get("/docs")
@docs_bp.get("/swagger")
def swagger_ui():
    """Interactive Swagger UI rendered from the OpenAPI document."""
    return render_template("swagger.html")

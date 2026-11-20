from __future__ import annotations

from typing import Any

MAX_DEPTH = 6


def build_example_from_schema(schema: Any, _depth: int = 0) -> Any:
    """Construit une valeur JSON minimale respectant un schéma OpenAPI déjà
    résolu (sans $ref, voir analysis/contract.py). Best-effort : sert de filet
    de sécurité quand le modèle a oublié de fournir un body pour un endpoint
    qui en a besoin — jamais à remplacer un body que le modèle a fourni."""
    if _depth > MAX_DEPTH or not isinstance(schema, dict):
        return None

    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]

    if isinstance(schema.get("allOf"), list):
        merged: dict[str, Any] = {}
        for sub_schema in schema["allOf"]:
            sub_example = build_example_from_schema(sub_schema, _depth + 1)
            if isinstance(sub_example, dict):
                merged.update(sub_example)
        return merged

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return enum_values[0]

    schema_type = schema.get("type")

    if schema_type == "object" or (schema_type is None and "properties" in schema):
        properties = schema.get("properties") or {}
        required = schema.get("required") or list(properties.keys())
        return {
            name: build_example_from_schema(prop_schema, _depth + 1)
            for name, prop_schema in properties.items()
            if name in required
        }

    if schema_type == "array":
        item_example = build_example_from_schema(schema.get("items") or {}, _depth + 1)
        return [item_example] if item_example is not None else []

    if schema_type == "integer":
        return _bounded_int(schema.get("minimum"), schema.get("maximum"))

    if schema_type == "number":
        return float(_bounded_int(schema.get("minimum"), schema.get("maximum")))

    if schema_type == "boolean":
        return True

    if schema_type == "string" or schema_type is None:
        return _build_string_example(schema)

    return None


def build_invalid_example_from_schema(schema: Any) -> Any:
    """Construit une valeur qui viole volontairement le schéma, à partir d'un
    exemple valide : retire le premier champ requis s'il y en a, sinon
    corrompt le type du premier champ connu. Renvoie None si le schéma ne
    décrit pas un objet exploitable (sans champ requis ni propriété)."""
    if not isinstance(schema, dict):
        return None

    schema_type = schema.get("type")
    if schema_type != "object" and "properties" not in schema:
        return None

    properties = schema.get("properties") or {}
    required = schema.get("required") or []

    valid = build_example_from_schema(schema)
    if not isinstance(valid, dict):
        return None

    if required:
        missing_field = required[0]
        return {key: value for key, value in valid.items() if key != missing_field}

    if properties:
        first_field = next(iter(properties))
        corrupted = dict(valid)
        corrupted[first_field] = {"__type_invalide_pour_ce_champ__": True}
        return corrupted

    return None


def _bounded_int(minimum: Any, maximum: Any) -> int:
    value = int(minimum) if isinstance(minimum, (int, float)) else 1
    if isinstance(maximum, (int, float)) and value > maximum:
        value = int(maximum)
    return value


def _build_string_example(schema: dict[str, Any]) -> str:
    fmt = schema.get("format")
    if fmt == "email":
        base = "user@example.com"
    elif fmt == "date-time":
        base = "2024-01-01T00:00:00Z"
    elif fmt == "date":
        base = "2024-01-01"
    elif fmt == "password":
        base = "Secret123"
    else:
        base = "texte_test"

    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(base) < min_length:
        base = (base * ((min_length // max(len(base), 1)) + 1))[:min_length]

    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and len(base) > max_length:
        base = base[:max_length]

    return base

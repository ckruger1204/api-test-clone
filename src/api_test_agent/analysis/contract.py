from __future__ import annotations

from typing import Any

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def extract_contract_payload(spec: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
    info = spec.get("info") or {}
    title = info.get("title") or "API"
    version = info.get("version") or "unknown"
    global_security = spec.get("security")
    security_schemes = _extract_security_schemes(spec)
    components = spec.get("components") or {}

    endpoints: list[dict[str, Any]] = []
    for path, path_item in sorted((spec.get("paths") or {}).items()):
        if not isinstance(path_item, dict):
            continue

        for method, operation in sorted(path_item.items()):
            method_lower = str(method).lower()
            if method_lower not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            responses = operation.get("responses") or {}
            response_codes = sorted(str(code) for code in responses.keys())

            endpoints.append(
                {
                    "method": method_lower.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "summary": operation.get("summary"),
                    "tags": operation.get("tags") or [],
                    "has_request_body": "requestBody" in operation,
                    "response_codes": response_codes,
                    "requires_auth": _requires_auth(operation.get("security", global_security)),
                    "request_body_schema": _resolve_request_body_schema(operation, components),
                    "response_schemas": _resolve_response_schemas(operation, components),
                }
            )

    return {
        "openapi": spec.get("openapi"),
        "title": title,
        "version": version,
        "base_url": base_url.rstrip("/"),
        "security_schemes": security_schemes,
        "endpoints": endpoints,
    }


def _extract_security_schemes(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Résumé des schémas déclarés sous components.securitySchemes (type, scheme,
    emplacement du header pour une apiKey, etc.) — informatif, pas utilisé pour
    décider requires_auth (voir _requires_auth)."""
    raw_schemes = ((spec.get("components") or {}).get("securitySchemes")) or {}
    if not isinstance(raw_schemes, dict):
        return {}

    schemes: dict[str, dict[str, Any]] = {}
    for name, scheme in raw_schemes.items():
        if not isinstance(scheme, dict):
            continue
        schemes[name] = {
            "type": scheme.get("type"),
            "scheme": scheme.get("scheme"),
            "in": scheme.get("in"),
            "name": scheme.get("name"),
        }
    return schemes


def _resolve_request_body_schema(
    operation: dict[str, Any], components: dict[str, Any]
) -> dict[str, Any] | None:
    """Résout le schéma JSON du requestBody (content application/json) d'une
    opération, en substituant récursivement ses $ref. Renvoie None si
    l'opération n'a pas de requestBody JSON décrit."""
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None

    resolved_body = _resolve_refs(request_body, components, frozenset())
    if not isinstance(resolved_body, dict):
        return None

    content = (resolved_body.get("content") or {}).get("application/json")
    if not isinstance(content, dict):
        return None

    schema = content.get("schema")
    return schema if isinstance(schema, dict) and schema else None


def _resolve_response_schemas(
    operation: dict[str, Any], components: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Résout le schéma JSON (content application/json) de chaque réponse
    déclarée pour l'opération — y compris quand la réponse elle-même est une
    $ref vers components/responses (ex: #/components/responses/NotFound), pas
    seulement quand c'est son schema qui l'est. Clé : code HTTP en texte."""
    responses = operation.get("responses") or {}
    resolved_schemas: dict[str, dict[str, Any]] = {}

    for code, response in responses.items():
        if not isinstance(response, dict):
            continue

        resolved_response = _resolve_refs(response, components, frozenset())
        if not isinstance(resolved_response, dict):
            continue

        content = (resolved_response.get("content") or {}).get("application/json")
        if not isinstance(content, dict):
            continue

        schema = content.get("schema")
        if isinstance(schema, dict) and schema:
            resolved_schemas[str(code)] = schema

    return resolved_schemas


def _resolve_refs(node: Any, components: dict[str, Any], seen: frozenset[str]) -> Any:
    """Remplace récursivement les $ref vers #/components/<groupe>/<nom> (schemas,
    responses, ...) par l'élément qu'elles désignent — une substitution est
    elle-même entièrement résolue avant d'être renvoyée, donc une réponse
    $ref-ée dont le schéma est lui-même $ref-é ressort complètement résolue.
    `seen` empêche de boucler sur une référence circulaire (une ref déjà
    traversée dans la branche courante est coupée à un schéma vide plutôt que
    de récurser indéfiniment)."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/"):
            pointer = ref[len("#/components/") :]
            if pointer in seen:
                return {}
            group_name, _, member_name = pointer.partition("/")
            group = components.get(group_name)
            target = group.get(member_name) if isinstance(group, dict) else None
            if target is None:
                return {}
            return _resolve_refs(target, components, seen | {pointer})
        return {key: _resolve_refs(value, components, seen) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, components, seen) for item in node]
    return node


def _requires_auth(security: Any) -> bool:
    """Un endpoint requiert une authentification si sa liste `security` (celle
    de l'opération, sinon celle de la racine du spec) n'est ni vide ni réduite
    à des alternatives vides ({} = accès anonyme autorisé). Voir OpenAPI 3.0
    §4.8.30 : chaque élément de la liste est une alternative (OR), dont les
    clés internes sont requises ensemble (AND)."""
    if not isinstance(security, list) or not security:
        return False
    return not any(requirement == {} for requirement in security)

from __future__ import annotations

import re
from typing import Any

from .payloads import build_example_from_schema
from .scenarios import Scenario

INVALID_TOKEN_HEADER = {"Authorization": "Bearer invalid.token.value"}

# Types scalaires pour lesquels on sait construire une valeur manifestement
# du mauvais type ; les autres (object imbriqué, type absent...) sont ignorés
# plutôt que de risquer un faux négatif.
_MISMATCHED_VALUES: dict[str, Any] = {
    "string": 12345,
    "integer": "pas-un-entier",
    "number": "pas-un-nombre",
    "boolean": "pas-un-booleen",
    "array": "pas-un-tableau",
    "object": "pas-un-objet",
}


def build_deterministic_scenarios(endpoint: dict[str, Any]) -> list[Scenario]:
    """Scénarios négatifs garantis par le code, pour TOUT endpoint concerné —
    indépendamment de ce que le modèle a (ou non) proposé pour ce lot :
    - absence de token / token invalide, si l'endpoint est protégé ;
    - champ requis manquant / mauvais type, si son requestBody a un schéma
      connu avec des champs requis.
    Ne remplace jamais les scénarios du modèle, s'y ajoute (voir generator.py)."""
    operation_id = endpoint.get("operation_id")
    if not operation_id:
        return []

    method = str(endpoint.get("method", "GET"))
    path = _concrete_path(str(endpoint.get("path", "/")))
    schema = endpoint.get("request_body_schema")
    has_schema = endpoint.get("has_request_body") and isinstance(schema, dict)

    scenarios: list[Scenario] = []

    if endpoint.get("requires_auth"):
        nominal_body = build_example_from_schema(schema) if has_schema else None
        expected_status, response_schemas = _expected_status_401(endpoint)

        scenarios.append(
            Scenario(
                operation_id=operation_id,
                scenario="token_absent",
                method=method,
                path=path,
                body=nominal_body,
                expected_status=expected_status,
                requires_auth=False,  # surtout ne pas attacher AUTH_HEADERS ici
                response_schemas=response_schemas,
                description=(
                    f"Vérifie que {method} {path} rejette un appel sans aucun "
                    "jeton d'authentification."
                ),
            )
        )
        scenarios.append(
            Scenario(
                operation_id=operation_id,
                scenario="token_invalide",
                method=method,
                path=path,
                body=nominal_body,
                expected_status=expected_status,
                requires_auth=False,
                response_schemas=response_schemas,
                extra_headers=INVALID_TOKEN_HEADER,
                description=(
                    f"Vérifie que {method} {path} rejette un appel avec un "
                    "jeton d'authentification manifestement invalide."
                ),
            )
        )

    if has_schema:
        requires_auth = bool(endpoint.get("requires_auth"))
        valid_body = build_example_from_schema(schema)
        if isinstance(valid_body, dict):
            expected_status, response_schemas = _expected_status_for_body_error(endpoint)
            required_fields = [f for f in (schema.get("required") or []) if f in valid_body]
            properties = schema.get("properties") or {}

            for field_name in required_fields:
                corrupted = {k: v for k, v in valid_body.items() if k != field_name}
                scenarios.append(
                    Scenario(
                        operation_id=operation_id,
                        scenario=f"champ_{_slug(field_name)}_manquant",
                        method=method,
                        path=path,
                        body=corrupted,
                        expected_status=expected_status,
                        requires_auth=requires_auth,
                        response_schemas=response_schemas,
                        description=(
                            f"Vérifie que {method} {path} rejette un body où le "
                            f"champ requis '{field_name}' est absent."
                        ),
                    )
                )

                field_schema = properties.get(field_name) or {}
                mismatched = _MISMATCHED_VALUES.get(field_schema.get("type"))
                if mismatched is None:
                    continue
                corrupted_type = dict(valid_body)
                corrupted_type[field_name] = mismatched
                scenarios.append(
                    Scenario(
                        operation_id=operation_id,
                        scenario=f"champ_{_slug(field_name)}_type_invalide",
                        method=method,
                        path=path,
                        body=corrupted_type,
                        expected_status=expected_status,
                        requires_auth=requires_auth,
                        response_schemas=response_schemas,
                        description=(
                            f"Vérifie que {method} {path} rejette un body où le "
                            f"champ '{field_name}' a un type incorrect."
                        ),
                    )
                )

    return scenarios


def _concrete_path(raw_path: str) -> str:
    """Remplace chaque {param} du chemin par une valeur plausible — ces
    scénarios ne testent pas la résolution de l'identifiant, seulement
    l'authentification ou la validation du body, donc n'importe quelle
    valeur syntaxiquement correcte convient."""
    return re.sub(r"\{[^}]+\}", "1", raw_path)


def _expected_status_401(endpoint: dict[str, Any]) -> tuple[list[int], dict[int, Any]]:
    response_schemas = endpoint.get("response_schemas") or {}
    schemas = {401: response_schemas["401"]} if "401" in response_schemas else {}
    return [401], schemas


def _expected_status_for_body_error(endpoint: dict[str, Any]) -> tuple[list[int], dict[int, Any]]:
    """400 et/ou 422 parmi ceux réellement documentés par l'endpoint, sinon
    les deux par défaut (le serveur testé n'est pas censé renvoyer autre
    chose pour un body invalide, documenté ou non)."""
    declared = set(endpoint.get("response_codes") or [])
    candidates = [code for code in (400, 422) if str(code) in declared] or [400, 422]
    response_schemas = endpoint.get("response_schemas") or {}
    schemas = {code: response_schemas[str(code)] for code in candidates if str(code) in response_schemas}
    return candidates, schemas


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower() or "champ"

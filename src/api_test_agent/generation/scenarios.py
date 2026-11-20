from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .payloads import build_example_from_schema, build_invalid_example_from_schema

# Mots indiquant qu'un scénario vise volontairement un body invalide (voir
# _fallback_body) — correspond aux noms de scénarios 'id_introuvable' n'en
# fait pas partie : seul le body est en cause, pas l'identifiant.
INVALID_BODY_SCENARIO_HINTS = ("malforme", "invalide", "invalid")


class ScenarioParseError(ValueError):
    """La réponse du modèle n'est pas un tableau JSON de scénarios exploitable."""


@dataclass(frozen=True)
class Scenario:
    operation_id: str
    scenario: str
    method: str
    path: str
    body: Any  # dict | str | None
    expected_status: list[int]
    requires_auth: bool = False
    # code HTTP -> schéma de réponse JSON attendu pour ce code (voir
    # analysis/contract.py:_resolve_response_schemas) ; seuls les codes
    # listés dans expected_status qui ont un schéma connu y figurent.
    response_schemas: dict[int, dict[str, Any]] = field(default_factory=dict)
    # Headers explicites à envoyer en plus (ex: token invalide) — jamais
    # renseigné pour un scénario issu du modèle, uniquement par du code qui
    # construit un Scenario directement (voir generation/negative_scenarios.py).
    extra_headers: dict[str, str] | None = None
    # Phrase expliquant ce que ce scénario vérifie et pourquoi (voir
    # _default_description) — jamais None après validate_scenario/construction
    # déterministe, mais le champ reste optionnel pour les Scenario construits
    # à la main (ex: dans les tests).
    description: str | None = None


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    """Sérialise un Scenario en dict JSON-compatible (voir generation/storage.py).
    Les clés int de response_schemas deviennent des chaînes : JSON n'autorise que
    des clés de type chaîne dans un objet."""
    data = asdict(scenario)
    data["response_schemas"] = {str(code): schema for code, schema in scenario.response_schemas.items()}
    return data


def scenario_from_dict(data: dict[str, Any]) -> Scenario:
    """Reconstruit un Scenario depuis le dict produit par scenario_to_dict —
    reconvertit les clés de response_schemas en int."""
    response_schemas = {int(code): schema for code, schema in (data.get("response_schemas") or {}).items()}
    return Scenario(
        operation_id=data["operation_id"],
        scenario=data["scenario"],
        method=data["method"],
        path=data["path"],
        body=data.get("body"),
        expected_status=list(data.get("expected_status") or []),
        requires_auth=bool(data.get("requires_auth", False)),
        response_schemas=response_schemas,
        extra_headers=data.get("extra_headers"),
        description=data.get("description"),
    )


def _default_description(operation_id: str, scenario_name: str, method: str, path: str) -> str:
    return f"Scénario « {scenario_name} » pour {operation_id} ({method} {path})."


def strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    match = re.match(r"^```(?:json|python)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def parse_scenario_response(text: str) -> list[Any]:
    """Parse la réponse du modèle en liste JSON brute (pas encore validée)."""
    cleaned = strip_markdown_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ScenarioParseError(f"réponse non JSON : {exc}") from exc
    if not isinstance(data, list):
        raise ScenarioParseError("la réponse JSON doit être un tableau de scénarios")
    return data


def endpoint_key(endpoint: dict[str, Any]) -> str:
    """Identifiant d'affichage d'un endpoint : son operation_id, ou method:path
    à défaut. Utilisé uniquement pour signaler les endpoints non couverts —
    le matching des scénarios exige lui un operation_id réel."""
    operation_id = endpoint.get("operation_id")
    if operation_id:
        return str(operation_id)
    method = str(endpoint.get("method", "GET")).upper()
    path = str(endpoint.get("path", "/"))
    return f"{method}:{path}"


def validate_scenario(
    raw: Any, endpoints_by_operation_id: dict[str, dict[str, Any]]
) -> tuple[Scenario | None, str | None]:
    """Valide un scénario brut (dict JSON) contre les endpoints du lot. Renvoie
    (Scenario, None) si valide, ou (None, message d'erreur) sinon."""
    if not isinstance(raw, dict):
        return None, "scénario ignoré : ce n'est pas un objet JSON"

    operation_id = raw.get("operation_id")
    if not isinstance(operation_id, str) or operation_id not in endpoints_by_operation_id:
        return None, f"scénario ignoré : operation_id inconnu dans ce lot ({operation_id!r})"

    endpoint = endpoints_by_operation_id[operation_id]

    method = raw.get("method")
    if not isinstance(method, str) or method.upper() != str(endpoint.get("method", "GET")).upper():
        return None, f"scénario ignoré pour {operation_id} : method ne correspond pas à l'endpoint ({method!r})"

    path = raw.get("path")
    if not isinstance(path, str) or not path:
        return None, f"scénario ignoré pour {operation_id} : path manquant ou invalide"
    if not _path_pattern_regex(str(endpoint.get("path", "/"))).match(path):
        return None, f"scénario ignoré pour {operation_id} : path {path!r} ne correspond pas à l'endpoint"

    scenario_name = raw.get("scenario")
    if not isinstance(scenario_name, str) or not scenario_name:
        return None, f"scénario ignoré pour {operation_id} : champ 'scenario' manquant"

    body = raw.get("body")
    if body is not None and not isinstance(body, (dict, str)):
        return None, f"scénario ignoré pour {operation_id} : body doit être un objet, une chaîne ou null"
    if body is None and endpoint.get("has_request_body"):
        body = _fallback_body(scenario_name, endpoint.get("request_body_schema"))

    raw_expected = raw.get("expected_status")
    if not isinstance(raw_expected, list) or not raw_expected:
        return None, f"scénario ignoré pour {operation_id} : expected_status doit être une liste non vide"

    expected_status = [
        code
        for code in raw_expected
        if isinstance(code, int) and not isinstance(code, bool) and 100 <= code <= 599
    ]
    if not expected_status:
        return None, f"scénario ignoré pour {operation_id} : aucun code HTTP valide (100-599) dans expected_status"

    known_response_schemas = endpoint.get("response_schemas") or {}
    response_schemas = {
        code: known_response_schemas[str(code)] for code in expected_status if str(code) in known_response_schemas
    }

    raw_description = raw.get("description")
    description = (
        raw_description.strip()
        if isinstance(raw_description, str) and raw_description.strip()
        else _default_description(operation_id, scenario_name, method.upper(), path)
    )

    return (
        Scenario(
            operation_id=operation_id,
            scenario=scenario_name,
            method=method.upper(),
            path=path,
            body=body,
            expected_status=expected_status,
            # Déduit du contrat OpenAPI (endpoint["requires_auth"]), jamais de la
            # réponse du modèle : on ne peut pas faire confiance au LLM pour
            # décider si une requête doit porter un token.
            requires_auth=bool(endpoint.get("requires_auth")),
            response_schemas=response_schemas,
            description=description,
        ),
        None,
    )


def assign_test_names(scenarios: list[Scenario]) -> list[tuple[str, Scenario]]:
    """Associe un nom de fonction pytest unique à chaque scénario :
    test_<operation_id>_<scenario>, avec un suffixe numérique en cas de doublon."""
    seen: dict[str, int] = {}
    named: list[tuple[str, Scenario]] = []
    for scenario in scenarios:
        base = _sanitize_name(f"test_{scenario.operation_id}_{scenario.scenario}")
        count = seen.get(base, 0)
        name = base if count == 0 else f"{base}_{count + 1}"
        seen[base] = count + 1
        named.append((name, scenario))
    return named


def render_scenario_lines(test_name: str, scenario: Scenario) -> list[str]:
    status_set = "{" + ", ".join(str(code) for code in sorted(set(scenario.expected_status))) + "}"
    auth_kwarg = ", auth=True" if scenario.requires_auth else ""
    headers_kwarg = f", headers={scenario.extra_headers!r}" if scenario.extra_headers else ""

    if isinstance(scenario.body, str):
        call = (
            f"request_api({scenario.method!r}, {scenario.path!r}, "
            f"raw_body={scenario.body!r}{headers_kwarg}{auth_kwarg})"
        )
    elif scenario.body is None:
        call = f"request_api({scenario.method!r}, {scenario.path!r}{headers_kwarg}{auth_kwarg})"
    else:
        call = (
            f"request_api({scenario.method!r}, {scenario.path!r}, "
            f"body={scenario.body!r}{headers_kwarg}{auth_kwarg})"
        )

    description = scenario.description or _default_description(
        scenario.operation_id, scenario.scenario, scenario.method, scenario.path
    )
    expected_status_sorted = sorted(set(scenario.expected_status))

    status_check = (
        f"'check': 'status_code', 'expected': {expected_status_sorted!r}, "
        f"'actual': status, 'passed': status in {status_set}"
    )
    lines = [
        f"def {test_name}():",
        f"    # {_single_line(description)}",
        f"    status, body_text = {call}",
        f"    checks = [{{{status_check}}}]",
    ]
    if scenario.response_schemas:
        # La correspondance status -> schéma se fait à l'exécution (pas ici),
        # pour rester correcte quel que soit le code réellement renvoyé parmi
        # ceux attendus.
        lines.append(f"    schema = {scenario.response_schemas!r}.get(status)")
        lines.append("    if schema is not None:")
        lines.append(
            "        checks.extend(collect_schema_checks(parse_json_body(body_text), schema, "
            f"{test_name!r}))"
        )
    lines.append("    log_assertions(checks)")
    lines.append("    assert all(c['passed'] for c in checks), format_checks(checks)")
    lines.append("")
    return lines


def _single_line(text: str) -> str:
    """Aplati une description sur une seule ligne pour un commentaire Python :
    une description multi-ligne casserait la syntaxe du fichier généré."""
    return " ".join(text.split())


def _fallback_body(scenario_name: str, schema: Any) -> Any:
    """Filet de sécurité quand le modèle a renvoyé body=null pour un endpoint
    qui a pourtant un requestBody : construit un body à partir du schéma
    OpenAPI résolu (analysis/contract.py) plutôt que de laisser partir une
    requête sans aucun payload. N'intervient jamais si le modèle a lui-même
    fourni un body (cf. validate_scenario) — on ne corrige ici qu'un oubli.
    Renvoie None si le schéma est absent ou inexploitable : le scénario reste
    alors valide, avec un body toujours vide (comportement précédent)."""
    if not isinstance(schema, dict):
        return None

    if any(hint in scenario_name.lower() for hint in INVALID_BODY_SCENARIO_HINTS):
        invalid = build_invalid_example_from_schema(schema)
        return invalid if invalid is not None else "{not-valid-json"

    return build_example_from_schema(schema)


def _path_pattern_regex(raw_path: str) -> re.Pattern[str]:
    """Transforme un chemin OpenAPI (ex: /articles/{id}) en regex acceptant
    n'importe quelle valeur concrète à la place des paramètres."""
    placeholder = "\x00"
    masked = re.sub(r"\{[^}]+\}", placeholder, raw_path)
    escaped = re.escape(masked).replace(placeholder, r"[^/]+")
    return re.compile(f"^{escaped}$")


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    return sanitized or "generated_test"

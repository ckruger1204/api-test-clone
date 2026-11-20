from __future__ import annotations

import json
from typing import Any


def build_batch_prompt(batch: list[dict[str, Any]]) -> str:
    """Construit le prompt envoyé au modèle pour UN lot d'endpoints. Qwen ne doit
    renvoyer qu'un tableau JSON de scénarios — jamais de code Python. C'est le
    code qui génère ensuite les fonctions pytest à partir de ces scénarios."""
    lines: list[str] = []
    for endpoint in batch:
        lines.append(
            "- operation_id={operation_id} method={method} path={path} "
            "response_codes={response_codes} has_request_body={has_request_body} "
            "requires_auth={requires_auth}".format(
                operation_id=endpoint.get("operation_id") or "endpoint",
                method=endpoint.get("method", "GET"),
                path=endpoint.get("path", "/"),
                response_codes=endpoint.get("response_codes", []),
                has_request_body=bool(endpoint.get("has_request_body")),
                requires_auth=bool(endpoint.get("requires_auth")),
            )
        )
        schema = endpoint.get("request_body_schema")
        if schema:
            lines.append(
                "  request_body_schema="
                + json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
    endpoints_description = "\n".join(lines)

    return (
        "Tu es un générateur de scénarios de test pour une API REST. Réponds "
        "UNIQUEMENT avec un tableau JSON valide, sans balises markdown et sans "
        "aucun texte autour. N'invente aucun endpoint hors de la liste fournie.\n\n"
        "Chaque élément du tableau est un objet avec exactement ces clés :\n"
        "- operation_id (string) : l'operation_id EXACT d'un endpoint listé ci-dessous.\n"
        "- scenario (string) : un identifiant court du cas testé, ex: 'nominal', "
        "'id_introuvable', 'body_malforme', ou un autre cas pertinent.\n"
        "- method (string) : la méthode HTTP de cet endpoint.\n"
        "- path (string) : le chemin concret à appeler, avec tout paramètre "
        "{...} déjà remplacé par une valeur (ex: 999999999 pour un ID introuvable, "
        "une valeur plausible pour un cas nominal).\n"
        "- body : un objet JSON pour un body valide, null si pas de body, ou une "
        "chaîne de texte si tu veux tester un body volontairement invalide "
        "(ex: '{not-valid-json').\n"
        "- expected_status : un tableau d'entiers HTTP (ex: [200] ou [400, 422]).\n"
        "- description (string) : une phrase expliquant ce que ce scénario "
        "vérifie et pourquoi (apparaît dans le rapport de test).\n\n"
        "Pour CHAQUE endpoint ci-dessous, propose au moins :\n"
        "1. un scénario 'nominal' (données valides, status attendu parmi les "
        "codes 2xx connus) ;\n"
        "2. un scénario 'id_introuvable' si le chemin a un paramètre et la "
        "méthode est GET/PUT/PATCH/DELETE (ID 999999999, status 404 ou 400) ;\n"
        "3. un scénario 'body_malforme' si l'endpoint a un body et la méthode "
        "est POST/PUT/PATCH (body texte invalide, status 400 ou 422).\n\n"
        "Quand request_body_schema est fourni pour un endpoint, construis le "
        "body du scénario 'nominal' en respectant ce schéma (champs listés "
        "dans required, bons types). Pour 'body_malforme', viole volontairement "
        "ce schéma — champ requis manquant, mauvais type — ou utilise un texte "
        "JSON syntaxiquement invalide ; les deux formes sont acceptées pour "
        "body. Si tu ne fournis pas de body alors que l'endpoint en attend un, "
        "il sera reconstruit automatiquement à partir du schéma.\n\n"
        "requires_auth=true signifie qu'un token d'authentification valide est "
        "automatiquement joint à la requête par le code d'exécution : pour le "
        "scénario 'nominal', suppose que cette authentification réussit (status "
        "attendu parmi les codes 2xx connus).\n\n"
        "Ne propose PAS toi-même de scénario d'absence/invalidité de token, ni de "
        "champ requis manquant/mauvais type isolé : le code les génère déjà "
        "automatiquement pour chaque endpoint concerné, à partir de requires_auth "
        "et request_body_schema. Concentre-toi plutôt sur les codes de réponse "
        "documentés (response_codes) que 'nominal'/'id_introuvable'/'body_malforme' "
        "ne couvrent pas (ex: 403, 409) : propose pour chacun un scénario métier "
        "plausible qui le déclenche réellement (ex: nom déjà utilisé pour un 409, "
        "ressource d'un autre utilisateur pour un 403).\n\n"
        f"Endpoints de ce lot :\n{endpoints_description}\n"
    )

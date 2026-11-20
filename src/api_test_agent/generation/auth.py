from __future__ import annotations

import base64
import os
import re
from typing import Any

_ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class AuthConfigError(ValueError):
    """La configuration auth.* est absente, incomplète ou d'un type inconnu."""


def resolve_auth_headers(auth_config: dict[str, Any] | None) -> dict[str, str]:
    """Construit les headers HTTP statiques à attacher aux requêtes des
    endpoints protégés, à partir de la section `auth` de config.json. Ne
    décide jamais quels endpoints en ont besoin — ça vient de
    endpoint["requires_auth"], déduit du spec OpenAPI (voir analysis/contract.py)."""
    if not auth_config:
        return {}

    auth_type = auth_config.get("type")

    if auth_type in (None, "none"):
        return {}

    if auth_type == "bearer":
        token = _resolve(auth_config.get("token"), "auth.token")
        return {"Authorization": f"Bearer {token}"}

    if auth_type == "api_key":
        header = auth_config.get("header") or "X-API-Key"
        value = _resolve(auth_config.get("value"), "auth.value")
        return {header: value}

    if auth_type == "basic":
        username = _resolve(auth_config.get("username"), "auth.username")
        password = _resolve(auth_config.get("password"), "auth.password")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}

    raise AuthConfigError(
        f"Type d'authentification inconnu : {auth_type!r} (attendu : bearer, api_key, basic, none)."
    )


def _resolve(raw: Any, field_name: str) -> str:
    """Résout une valeur de config : soit une chaîne littérale, soit une
    référence ${NOM_VAR} vers une variable d'environnement."""
    if not isinstance(raw, str) or not raw:
        raise AuthConfigError(f"{field_name} est requis et doit être une chaîne non vide.")

    match = _ENV_REF.match(raw)
    if not match:
        return raw

    env_name = match.group(1)
    value = os.environ.get(env_name)
    if not value:
        raise AuthConfigError(
            f"{field_name} référence la variable d'environnement {env_name!r}, "
            "qui n'est pas définie (ou vide)."
        )
    return value

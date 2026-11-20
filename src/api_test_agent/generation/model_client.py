from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    contract_payload: dict[str, Any]


class ModelClientError(RuntimeError):
    """Raised when model generation fails."""


class HTTPModelClient:
    def __init__(self, base_url: str, model_name: str, api_key: str, timeout: int = 600):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, request: GenerationRequest) -> str:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": 0,
        }
        req = urllib.request.Request(
            url=f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelClientError(f"Model HTTP error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ModelClientError(f"Model request failed: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
            content = parsed["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover - remote API schema variation
            raise ModelClientError("Model response did not contain choices[0].message.content") from exc

        # Le contenu brut du modèle est renvoyé tel quel : c'est
        # scenarios.parse_scenario_response() qui retire les balises markdown
        # et parse le JSON de scénarios.
        return content


def build_header_lines(base_url: str, auth_headers: dict[str, str] | None = None) -> list[str]:
    """En-tête commun du fichier généré : imports, BASE_URL, AUTH_HEADERS,
    request_api(), et le test générique de route inconnue. Écrit une seule
    fois par le code (jamais par le modèle), puisque chaque lot de tests
    générés par Qwen s'appuie sur request_api() sans le redéfinir.

    auth_headers vient de generation.auth.resolve_auth_headers(), à partir de
    la config auth.* de l'utilisateur (token bearer, clé API, basic auth...).
    Un scénario généré ne les reçoit que s'il porte requires_auth=True, déduit
    du contrat OpenAPI — jamais d'une décision du modèle."""
    return [
        "import json",
        "import os",
        "import re",
        "import urllib.error",
        "import urllib.request",
        "",
        f"BASE_URL = {base_url!r}",
        f"AUTH_HEADERS = {(auth_headers or {})!r}",
        "# Le dossier d'exécution (tests_dir/runs/<horodatage>/) diffère de celui",
        "# du fichier de test (tests_dir/) : runner.py impose son propre chemin",
        "# via cette variable d'environnement plutôt que de dépendre de __file__.",
        "REQUEST_LOG_PATH = os.environ.get('API_TEST_AGENT_REQUEST_LOG') or os.path.join(",
        "    os.path.dirname(os.path.abspath(__file__)), 'request_log.jsonl'",
        ")",
        "SENSITIVE_KEY_RE = re.compile(r'(password|token|secret|api[_-]?key|authorization)', re.IGNORECASE)",
        "",
        "",
        "def redact(value):",
        "    # Ne JAMAIS laisser un secret (token, mot de passe...) atteindre le",
        "    # rapport : tout champ dont la clé évoque un secret est masqué avant",
        "    # d'être journalisé, que ce soit dans un header ou dans un body JSON.",
        "    if isinstance(value, dict):",
        "        return {",
        "            key: ('***redacted***' if SENSITIVE_KEY_RE.search(str(key)) else redact(val))",
        "            for key, val in value.items()",
        "        }",
        "    if isinstance(value, list):",
        "        return [redact(item) for item in value]",
        "    return value",
        "",
        "",
        "def redact_body(raw):",
        "    if raw is None:",
        "        return None",
        "    if isinstance(raw, (dict, list)):",
        "        return redact(raw)",
        "    if isinstance(raw, str):",
        "        try:",
        "            return redact(json.loads(raw))",
        "        except (ValueError, TypeError):",
        "            return raw[:2000]",
        "    return raw",
        "",
        "",
        "def _append_log_entry(entry):",
        "    try:",
        "        with open(REQUEST_LOG_PATH, 'a', encoding='utf-8') as handle:",
        "            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + '\\n')",
        "    except OSError:",
        "        pass",
        "",
        "",
        "def log_call(method, path, req_headers, body_sent, status, response_text):",
        "    _append_log_entry({",
        "        'kind': 'request',",
        "        'test': os.environ.get('PYTEST_CURRENT_TEST', ''),",
        "        'method': method,",
        "        'path': path,",
        "        'request_headers': redact(req_headers),",
        "        'request_body': redact_body(body_sent),",
        "        'status': status,",
        "        'response_body': redact_body(response_text),",
        "    })",
        "",
        "",
        "def log_assertions(checks):",
        "    _append_log_entry({",
        "        'kind': 'assertions',",
        "        'test': os.environ.get('PYTEST_CURRENT_TEST', ''),",
        "        'checks': checks,",
        "    })",
        "",
        "",
        "def request_api(method, path, body=None, headers=None, raw_body=None, auth=False):",
        "    # raw_body contourne json.dumps() pour pouvoir envoyer du JSON volontairement invalide.",
        "    req_headers = {\"Accept\": \"application/json\"}",
        "    if auth:",
        "        req_headers.update(AUTH_HEADERS)",
        "    if headers:",
        "        req_headers.update(headers)",
        "    data = None",
        "    body_sent = None",
        "    if raw_body is not None:",
        "        data = raw_body.encode('utf-8')",
        "        req_headers['Content-Type'] = 'application/json'",
        "        body_sent = raw_body",
        "    elif body is not None:",
        "        data = json.dumps(body).encode('utf-8')",
        "        req_headers['Content-Type'] = 'application/json'",
        "        body_sent = body",
        "    req = urllib.request.Request(f\"{BASE_URL}{path}\", data=data, headers=req_headers, method=method)",
        "    try:",
        "        try:",
        "            with urllib.request.urlopen(req, timeout=10) as response:",
        "                status, response_text = response.status, response.read().decode('utf-8', errors='replace')",
        "        except urllib.error.HTTPError as exc:",
        "            status, response_text = exc.code, exc.read().decode('utf-8', errors='replace')",
        "    except Exception as exc:",
        "        log_call(method, path, req_headers, body_sent, None, f'{type(exc).__name__}: {exc}')",
        "        raise",
        "    log_call(method, path, req_headers, body_sent, status, response_text)",
        "    return status, response_text",
        "",
        "",
        "def parse_json_body(body_text):",
        "    try:",
        "        return json.loads(body_text)",
        "    except (ValueError, TypeError) as exc:",
        "        raise AssertionError(f'reponse non JSON : {exc} ; body={body_text!r}') from exc",
        "",
        "",
        "def collect_schema_checks(instance, schema, path='$'):",
        "    # Validateur JSON Schema (OpenAPI 3.0) minimal, stdlib uniquement : type,",
        "    # required, properties, items, enum, allOf, nullable. Ne leve JAMAIS :",
        "    # chaque champ produit une entree {check, expected, actual, passed},",
        "    # pour que le rapport liste TOUTES les violations, pas juste la premiere.",
        "    checks = []",
        "    if not isinstance(schema, dict) or not schema:",
        "        return checks",
        "    if instance is None:",
        "        if schema.get('nullable') or ('type' not in schema and 'properties' not in schema):",
        "            return checks",
        "    if 'allOf' in schema:",
        "        for sub_schema in schema['allOf']:",
        "            checks.extend(collect_schema_checks(instance, sub_schema, path))",
        "        return checks",
        "    schema_type = schema.get('type')",
        "    if schema_type == 'object' or (schema_type is None and 'properties' in schema):",
        "        is_object = isinstance(instance, dict)",
        "        checks.append({",
        "            'check': path, 'expected': 'object',",
        "            'actual': type(instance).__name__, 'passed': is_object,",
        "        })",
        "        if not is_object:",
        "            return checks",
        "        for field_name in schema.get('required') or []:",
        "            present = field_name in instance",
        "            checks.append({",
        "                'check': f'{path}.{field_name}', 'expected': 'present',",
        "                'actual': 'present' if present else 'missing', 'passed': present,",
        "            })",
        "        for name, sub_schema in (schema.get('properties') or {}).items():",
        "            if name in instance:",
        "                checks.extend(collect_schema_checks(instance[name], sub_schema, f'{path}.{name}'))",
        "        return checks",
        "    if schema_type == 'array':",
        "        is_array = isinstance(instance, list)",
        "        checks.append({",
        "            'check': path, 'expected': 'array',",
        "            'actual': type(instance).__name__, 'passed': is_array,",
        "        })",
        "        if not is_array:",
        "            return checks",
        "        items_schema = schema.get('items')",
        "        if items_schema:",
        "            for index, item in enumerate(instance[:20]):",
        "                checks.extend(collect_schema_checks(item, items_schema, f'{path}[{index}]'))",
        "        return checks",
        "    if schema_type in ('string', 'integer', 'number', 'boolean'):",
        "        if schema_type == 'string':",
        "            passed = isinstance(instance, str)",
        "        elif schema_type == 'integer':",
        "            passed = isinstance(instance, int) and not isinstance(instance, bool)",
        "        elif schema_type == 'number':",
        "            passed = isinstance(instance, (int, float)) and not isinstance(instance, bool)",
        "        else:",
        "            passed = isinstance(instance, bool)",
        "        checks.append({",
        "            'check': path, 'expected': schema_type,",
        "            'actual': type(instance).__name__, 'passed': passed,",
        "        })",
        "    enum_values = schema.get('enum')",
        "    if enum_values is not None:",
        "        checks.append({",
        "            'check': f'{path} (enum)', 'expected': enum_values,",
        "            'actual': instance, 'passed': instance in enum_values,",
        "        })",
        "    return checks",
        "",
        "",
        "def format_checks(checks):",
        "    failed = [c for c in checks if not c.get('passed')]",
        "    if not failed:",
        "        return 'OK'",
        "    return ' | '.join(",
        "        f\"{c.get('check')}: attendu {c.get('expected')!r}, obtenu {c.get('actual')!r}\"",
        "        for c in failed",
        "    )",
        "",
        "",
        "def test_unknown_route_returns_client_error():",
        "    status, _ = request_api('GET', '/__api_test_agent_unknown_route__')",
        "    assert status in {400, 404, 405}",
        "",
    ]


def build_file_header(base_url: str, auth_headers: dict[str, str] | None = None) -> str:
    return "\n".join(build_header_lines(base_url, auth_headers))

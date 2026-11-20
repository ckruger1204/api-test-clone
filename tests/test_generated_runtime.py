"""Exécute réellement le code embarqué dans build_file_header() (request_api,
parse_json_body, assert_schema) : ce code est écrit comme des chaînes Python
dans model_client.py, donc invisible pour ruff/un éditeur — ces tests sont la
seule façon de détecter une coquille de syntaxe ou de logique à l'intérieur."""

import json
import os
import tempfile

import pytest

from api_test_agent.generation.model_client import build_file_header

# Chemin bidon, dans un dossier qui n'existe pas : request_api()/log_call()
# doit échouer en silence (except OSError) plutôt que planter les tests qui
# ne portent pas sur la journalisation elle-même.
_NO_SUCH_FILE = os.path.join(tempfile.gettempdir(), "api_test_agent_unit_test_no_such_dir", "test_generated_api.py")


def _load_namespace(file_path: str = _NO_SUCH_FILE):
    code = build_file_header("http://localhost:5000")
    namespace: dict = {"__file__": file_path}
    exec(compile(code, "<generated_test_header>", "exec"), namespace)  # noqa: S102
    return namespace


def test_generated_header_compiles_and_exposes_helpers():
    ns = _load_namespace()
    assert callable(ns["request_api"])
    assert callable(ns["parse_json_body"])
    assert callable(ns["collect_schema_checks"])
    assert callable(ns["log_assertions"])
    assert callable(ns["format_checks"])


def test_collect_schema_checks_all_pass_for_valid_object():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"](
        {"name": "x"},
        {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
    )
    assert checks and all(c["passed"] for c in checks)


def test_collect_schema_checks_reports_missing_required_field():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"]({}, {"type": "object", "required": ["name"]})
    failed = [c for c in checks if not c["passed"]]
    assert any(c["check"] == "$.name" for c in failed)


def test_collect_schema_checks_reports_wrong_scalar_type():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"](
        {"age": "not-an-int"}, {"type": "object", "properties": {"age": {"type": "integer"}}}
    )
    age_check = next(c for c in checks if c["check"] == "$.age")
    assert age_check["passed"] is False
    assert age_check["expected"] == "integer"


def test_collect_schema_checks_rejects_bool_as_integer():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"](
        {"age": True}, {"type": "object", "properties": {"age": {"type": "integer"}}}
    )
    age_check = next(c for c in checks if c["check"] == "$.age")
    assert age_check["passed"] is False


def test_collect_schema_checks_validates_array_items():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"](
        {"tags": ["ok", 123]},
        {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}},
    )
    item_check = next(c for c in checks if c["check"] == "$.tags[1]")
    assert item_check["passed"] is False


def test_collect_schema_checks_returns_multiple_failures_not_just_the_first():
    ns = _load_namespace()
    schema = {
        "type": "object",
        "required": ["title", "content"],
        "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
    }
    checks = ns["collect_schema_checks"]({"title": 123, "content": 456}, schema)
    failed_paths = {c["check"] for c in checks if not c["passed"]}
    # Les deux champs sont du mauvais type : les deux doivent apparaître,
    # pas seulement le premier rencontré (contrairement à un assert classique).
    assert failed_paths == {"$.title", "$.content"}


def test_collect_schema_checks_allows_nullable_none():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"](None, {"type": "string", "nullable": True})
    assert checks == []


def test_collect_schema_checks_rejects_none_when_not_nullable():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"](None, {"type": "string"})
    assert checks and checks[0]["passed"] is False


def test_collect_schema_checks_reports_enum_violation():
    ns = _load_namespace()
    checks = ns["collect_schema_checks"]("unknown", {"type": "string", "enum": ["recent", "oldest"]})
    enum_check = next(c for c in checks if "(enum)" in c["check"])
    assert enum_check["passed"] is False


def test_collect_schema_checks_merges_all_of():
    ns = _load_namespace()
    schema = {
        "allOf": [
            {"type": "object", "required": ["id"]},
            {"type": "object", "properties": {"id": {"type": "integer"}}},
        ]
    }
    checks = ns["collect_schema_checks"]({}, schema)
    assert any(c["check"] == "$.id" and not c["passed"] for c in checks)


def test_format_checks_returns_ok_when_all_passed():
    ns = _load_namespace()
    assert ns["format_checks"]([{"check": "x", "passed": True}]) == "OK"


def test_format_checks_lists_only_failed_checks():
    ns = _load_namespace()
    checks = [
        {"check": "status_code", "expected": [200], "actual": 404, "passed": False},
        {"check": "$.title", "expected": "string", "actual": "NoneType", "passed": True},
    ]
    message = ns["format_checks"](checks)
    assert "status_code" in message
    assert "$.title" not in message


def test_log_assertions_writes_kind_assertions_entry(tmp_path):
    ns = _load_namespace(str(tmp_path / "test_generated_api.py"))
    ns["log_assertions"]([{"check": "status_code", "passed": True}])

    log_path = tmp_path / "request_log.jsonl"
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["kind"] == "assertions"
    assert entry["checks"] == [{"check": "status_code", "passed": True}]


def test_log_call_writes_kind_request_entry(tmp_path, monkeypatch):
    ns = _load_namespace(str(tmp_path / "test_generated_api.py"))

    class _FakeResponse:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(ns["urllib"].request, "urlopen", lambda req, timeout: _FakeResponse())
    ns["request_api"]("GET", "/health")

    log_path = tmp_path / "request_log.jsonl"
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["kind"] == "request"


def test_parse_json_body_returns_parsed_value():
    ns = _load_namespace()
    assert ns["parse_json_body"]('{"ok": true}') == {"ok": True}


def test_parse_json_body_raises_assertion_error_on_invalid_json():
    ns = _load_namespace()
    with pytest.raises(AssertionError, match="non JSON"):
        ns["parse_json_body"]("this is not json")


def test_request_api_attaches_auth_headers_only_when_requested(monkeypatch):
    ns = _load_namespace()
    ns["AUTH_HEADERS"] = {"Authorization": "Bearer abc123"}

    captured = {}

    class _FakeResponse:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    def _fake_urlopen(req, timeout):
        captured["headers"] = dict(req.headers)
        return _FakeResponse()

    monkeypatch.setattr(ns["urllib"].request, "urlopen", _fake_urlopen)

    ns["request_api"]("GET", "/public")
    assert "Authorization" not in captured["headers"]

    ns["request_api"]("GET", "/protected", auth=True)
    assert captured["headers"]["Authorization"] == "Bearer abc123"


def test_request_api_logs_call_with_secrets_redacted(tmp_path, monkeypatch):
    ns = _load_namespace(str(tmp_path / "test_generated_api.py"))
    ns["AUTH_HEADERS"] = {"Authorization": "Bearer realsecrettoken"}

    class _FakeResponse:
        status = 201

        def read(self):
            return b'{"access_token": "abc", "user": {"username": "alice"}}'

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(ns["urllib"].request, "urlopen", lambda req, timeout: _FakeResponse())

    ns["request_api"](
        "POST", "/api/auth/login", body={"username": "alice", "password": "secret123"}, auth=True
    )

    log_path = tmp_path / "request_log.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])

    assert entry["method"] == "POST"
    assert entry["path"] == "/api/auth/login"
    assert entry["status"] == 201
    # Le vrai token (AUTH_HEADERS) ne doit jamais apparaître, même partiellement.
    assert "realsecrettoken" not in log_path.read_text(encoding="utf-8")
    assert entry["request_headers"]["Authorization"] == "***redacted***"
    assert entry["request_body"] == {"username": "alice", "password": "***redacted***"}
    assert entry["response_body"]["access_token"] == "***redacted***"
    assert entry["response_body"]["user"]["username"] == "alice"


def test_request_api_logs_entry_even_when_connection_fails(tmp_path, monkeypatch):
    ns = _load_namespace(str(tmp_path / "test_generated_api.py"))

    def _fake_urlopen(req, timeout):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(ns["urllib"].request, "urlopen", _fake_urlopen)

    with pytest.raises(ConnectionRefusedError):
        ns["request_api"]("GET", "/down")

    log_path = tmp_path / "request_log.jsonl"
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["status"] is None
    assert "ConnectionRefusedError" in entry["response_body"]


def test_redact_masks_sensitive_keys_recursively():
    ns = _load_namespace()
    value = {
        "username": "alice",
        "password": "secret",
        "nested": {"access_token": "xyz", "ok": True},
        "items": [{"api_key": "k"}, {"name": "safe"}],
    }

    redacted = ns["redact"](value)

    assert redacted["username"] == "alice"
    assert redacted["password"] == "***redacted***"
    assert redacted["nested"]["access_token"] == "***redacted***"
    assert redacted["nested"]["ok"] is True
    assert redacted["items"][0]["api_key"] == "***redacted***"
    assert redacted["items"][1]["name"] == "safe"

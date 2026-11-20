import pytest

from api_test_agent.generation.auth import AuthConfigError, resolve_auth_headers


def test_resolve_auth_headers_returns_empty_when_no_config():
    assert resolve_auth_headers(None) == {}
    assert resolve_auth_headers({}) == {}
    assert resolve_auth_headers({"type": "none"}) == {}


def test_resolve_auth_headers_bearer_with_literal_token():
    headers = resolve_auth_headers({"type": "bearer", "token": "abc123"})
    assert headers == {"Authorization": "Bearer abc123"}


def test_resolve_auth_headers_bearer_resolves_env_var(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "from-env")
    headers = resolve_auth_headers({"type": "bearer", "token": "${MY_TOKEN}"})
    assert headers == {"Authorization": "Bearer from-env"}


def test_resolve_auth_headers_bearer_missing_env_var_raises(monkeypatch):
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    with pytest.raises(AuthConfigError):
        resolve_auth_headers({"type": "bearer", "token": "${MISSING_TOKEN}"})


def test_resolve_auth_headers_bearer_without_token_raises():
    with pytest.raises(AuthConfigError):
        resolve_auth_headers({"type": "bearer"})


def test_resolve_auth_headers_api_key_with_custom_header():
    headers = resolve_auth_headers({"type": "api_key", "header": "X-Api-Key", "value": "secret"})
    assert headers == {"X-Api-Key": "secret"}


def test_resolve_auth_headers_api_key_defaults_header_name():
    headers = resolve_auth_headers({"type": "api_key", "value": "secret"})
    assert headers == {"X-API-Key": "secret"}


def test_resolve_auth_headers_basic_encodes_credentials():
    headers = resolve_auth_headers({"type": "basic", "username": "alice", "password": "wonderland"})
    assert headers == {"Authorization": "Basic YWxpY2U6d29uZGVybGFuZA=="}


def test_resolve_auth_headers_unknown_type_raises():
    with pytest.raises(AuthConfigError):
        resolve_auth_headers({"type": "oauth2"})

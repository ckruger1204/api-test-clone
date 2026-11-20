from api_test_agent.generation.negative_scenarios import build_deterministic_scenarios

CATEGORY_INPUT_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "minLength": 2},
        "description": {"type": "string", "nullable": True},
    },
}

ARTICLE_INPUT_SCHEMA = {
    "type": "object",
    "required": ["title", "content"],
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
    },
}


def test_no_scenarios_for_public_endpoint_without_body():
    endpoint = {
        "operation_id": "listCategories",
        "method": "GET",
        "path": "/api/categories",
        "requires_auth": False,
        "has_request_body": False,
        "request_body_schema": None,
        "response_codes": ["200"],
        "response_schemas": {},
    }

    assert build_deterministic_scenarios(endpoint) == []


def test_protected_endpoint_gets_token_absent_and_invalid_scenarios():
    endpoint = {
        "operation_id": "deleteArticle",
        "method": "DELETE",
        "path": "/api/articles/{articleId}",
        "requires_auth": True,
        "has_request_body": False,
        "request_body_schema": None,
        "response_codes": ["204", "401", "403", "404"],
        "response_schemas": {},
    }

    scenarios = build_deterministic_scenarios(endpoint)
    names = {s.scenario for s in scenarios}

    assert {"token_absent", "token_invalide"} <= names
    for scenario in scenarios:
        assert scenario.path == "/api/articles/1"
        assert scenario.expected_status == [401]
        assert scenario.requires_auth is False  # ne doit jamais porter le vrai token

    token_absent = next(s for s in scenarios if s.scenario == "token_absent")
    token_invalide = next(s for s in scenarios if s.scenario == "token_invalide")
    assert token_absent.extra_headers is None
    assert token_invalide.extra_headers == {"Authorization": "Bearer invalid.token.value"}


def test_token_scenarios_use_declared_response_schema_for_401():
    endpoint = {
        "operation_id": "deleteArticle",
        "method": "DELETE",
        "path": "/api/articles/{articleId}",
        "requires_auth": True,
        "has_request_body": False,
        "request_body_schema": None,
        "response_codes": ["204", "401"],
        "response_schemas": {"401": {"type": "object", "properties": {"error": {"type": "object"}}}},
    }

    scenarios = build_deterministic_scenarios(endpoint)

    for scenario in scenarios:
        assert scenario.response_schemas == {401: {"type": "object", "properties": {"error": {"type": "object"}}}}


def test_endpoint_with_body_gets_missing_and_invalid_type_scenarios_per_required_field():
    endpoint = {
        "operation_id": "createCategory",
        "method": "POST",
        "path": "/api/categories",
        "requires_auth": True,
        "has_request_body": True,
        "request_body_schema": CATEGORY_INPUT_SCHEMA,
        "response_codes": ["201", "400", "401"],
        "response_schemas": {},
    }

    scenarios = build_deterministic_scenarios(endpoint)
    names = {s.scenario for s in scenarios}

    assert "champ_name_manquant" in names
    assert "champ_name_type_invalide" in names

    missing = next(s for s in scenarios if s.scenario == "champ_name_manquant")
    assert "name" not in missing.body
    assert missing.expected_status == [400]  # seul 400 est documenté pour cet endpoint
    assert missing.requires_auth is True  # ce n'est pas l'auth qui est testée ici

    wrong_type = next(s for s in scenarios if s.scenario == "champ_name_type_invalide")
    assert wrong_type.body["name"] == 12345


def test_missing_field_scenarios_use_only_declared_body_error_codes():
    endpoint = {
        "operation_id": "createArticle",
        "method": "POST",
        "path": "/api/articles",
        "requires_auth": True,
        "has_request_body": True,
        "request_body_schema": ARTICLE_INPUT_SCHEMA,
        "response_codes": ["201", "400", "401"],  # 422 non documenté
        "response_schemas": {},
    }

    scenarios = build_deterministic_scenarios(endpoint)
    missing_scenarios = [s for s in scenarios if s.scenario.endswith("_manquant")]

    assert missing_scenarios
    for scenario in missing_scenarios:
        assert scenario.expected_status == [400]


def test_missing_field_scenarios_fall_back_to_both_codes_when_neither_declared():
    endpoint = {
        "operation_id": "createCategory",
        "method": "POST",
        "path": "/api/categories",
        "requires_auth": False,
        "has_request_body": True,
        "request_body_schema": CATEGORY_INPUT_SCHEMA,
        "response_codes": ["201"],  # ni 400 ni 422 documentés
        "response_schemas": {},
    }

    scenarios = build_deterministic_scenarios(endpoint)
    missing = next(s for s in scenarios if s.scenario == "champ_name_manquant")

    assert missing.expected_status == [400, 422]


def test_endpoint_without_operation_id_is_skipped():
    endpoint = {
        "operation_id": None,
        "method": "POST",
        "path": "/x",
        "requires_auth": True,
        "has_request_body": True,
        "request_body_schema": CATEGORY_INPUT_SCHEMA,
        "response_codes": [],
        "response_schemas": {},
    }

    assert build_deterministic_scenarios(endpoint) == []


def test_path_param_is_substituted_with_concrete_value():
    endpoint = {
        "operation_id": "getComment",
        "method": "PUT",
        "path": "/api/comments/{commentId}",
        "requires_auth": True,
        "has_request_body": False,
        "request_body_schema": None,
        "response_codes": ["200", "401"],
        "response_schemas": {},
    }

    scenarios = build_deterministic_scenarios(endpoint)

    assert all("{" not in s.path for s in scenarios)

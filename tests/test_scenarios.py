import pytest

from api_test_agent.generation.scenarios import (
    Scenario,
    ScenarioParseError,
    assign_test_names,
    parse_scenario_response,
    render_scenario_lines,
    validate_scenario,
)

ENDPOINT = {
    "operation_id": "getArticle",
    "method": "GET",
    "path": "/api/articles/{id}",
    "response_codes": ["200", "404"],
    "has_request_body": False,
}


def test_parse_scenario_response_accepts_plain_json():
    data = parse_scenario_response('[{"operation_id": "getArticle"}]')
    assert data == [{"operation_id": "getArticle"}]


def test_parse_scenario_response_strips_markdown_fence():
    text = '```json\n[{"operation_id": "getArticle"}]\n```'
    data = parse_scenario_response(text)
    assert data == [{"operation_id": "getArticle"}]


def test_parse_scenario_response_rejects_invalid_json():
    with pytest.raises(ScenarioParseError):
        parse_scenario_response("this is not json")


def test_parse_scenario_response_rejects_non_list():
    with pytest.raises(ScenarioParseError):
        parse_scenario_response('{"operation_id": "getArticle"}')


def test_validate_scenario_accepts_well_formed_scenario():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
    }

    scenario, error = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert error is None
    assert scenario == Scenario(
        operation_id="getArticle",
        scenario="nominal",
        method="GET",
        path="/api/articles/1",
        body=None,
        expected_status=[200],
        description=scenario.description,  # généré par défaut, voir test dédié
    )


def test_validate_scenario_generates_default_description_when_absent():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
    }

    scenario, _ = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert scenario.description == "Scénario « nominal » pour getArticle (GET /api/articles/1)."


def test_validate_scenario_keeps_model_provided_description():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
        "description": "Vérifie la récupération d'un article existant.",
    }

    scenario, _ = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert scenario.description == "Vérifie la récupération d'un article existant."


def test_validate_scenario_sets_requires_auth_from_endpoint_not_from_model():
    protected_endpoint = {**ENDPOINT, "requires_auth": True}
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
        "requires_auth": False,  # une éventuelle valeur du modèle doit être ignorée
    }

    scenario, error = validate_scenario(raw, {"getArticle": protected_endpoint})

    assert error is None
    assert scenario.requires_auth is True


CATEGORY_INPUT_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string", "minLength": 2}},
}


def test_validate_scenario_fills_missing_nominal_body_from_schema():
    endpoint = {
        "operation_id": "createCategory",
        "method": "POST",
        "path": "/api/categories",
        "has_request_body": True,
        "request_body_schema": CATEGORY_INPUT_SCHEMA,
    }
    raw = {
        "operation_id": "createCategory",
        "scenario": "nominal",
        "method": "POST",
        "path": "/api/categories",
        "body": None,
        "expected_status": [201],
    }

    scenario, error = validate_scenario(raw, {"createCategory": endpoint})

    assert error is None
    assert scenario.body == {"name": "texte_test"}


def test_validate_scenario_fills_missing_malformed_body_with_schema_violation():
    endpoint = {
        "operation_id": "createCategory",
        "method": "POST",
        "path": "/api/categories",
        "has_request_body": True,
        "request_body_schema": CATEGORY_INPUT_SCHEMA,
    }
    raw = {
        "operation_id": "createCategory",
        "scenario": "body_malforme",
        "method": "POST",
        "path": "/api/categories",
        "body": None,
        "expected_status": [400, 422],
    }

    scenario, error = validate_scenario(raw, {"createCategory": endpoint})

    assert error is None
    assert scenario.body == {}  # 'name' (le seul champ requis) a été retiré


def test_validate_scenario_keeps_model_provided_body_untouched():
    endpoint = {
        "operation_id": "createCategory",
        "method": "POST",
        "path": "/api/categories",
        "has_request_body": True,
        "request_body_schema": CATEGORY_INPUT_SCHEMA,
    }
    raw = {
        "operation_id": "createCategory",
        "scenario": "nominal",
        "method": "POST",
        "path": "/api/categories",
        "body": {"name": "Technology"},
        "expected_status": [201],
    }

    scenario, error = validate_scenario(raw, {"createCategory": endpoint})

    assert error is None
    assert scenario.body == {"name": "Technology"}


def test_validate_scenario_attaches_response_schema_for_expected_status():
    endpoint = {
        **ENDPOINT,
        "response_schemas": {
            "200": {"type": "object", "properties": {"id": {"type": "integer"}}},
            "404": {"type": "object", "properties": {"message": {"type": "string"}}},
        },
    }
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
    }

    scenario, error = validate_scenario(raw, {"getArticle": endpoint})

    assert error is None
    assert scenario.response_schemas == {200: {"type": "object", "properties": {"id": {"type": "integer"}}}}


def test_validate_scenario_only_keeps_schemas_for_expected_codes():
    endpoint = {
        **ENDPOINT,
        "response_schemas": {
            "200": {"type": "object"},
            "404": {"type": "object", "properties": {"message": {"type": "string"}}},
        },
    }
    raw = {
        "operation_id": "getArticle",
        "scenario": "id_introuvable",
        "method": "GET",
        "path": "/api/articles/999999999",
        "body": None,
        "expected_status": [404],
    }

    scenario, error = validate_scenario(raw, {"getArticle": endpoint})

    assert error is None
    assert list(scenario.response_schemas.keys()) == [404]


def test_validate_scenario_no_response_schemas_when_endpoint_has_none():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
    }

    scenario, error = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert error is None
    assert scenario.response_schemas == {}


def test_validate_scenario_rejects_unknown_operation_id():
    raw = {
        "operation_id": "doesNotExist",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200],
    }

    scenario, error = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert scenario is None
    assert error is not None


def test_validate_scenario_rejects_path_not_matching_endpoint_pattern():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/other/1",
        "body": None,
        "expected_status": [200],
    }

    scenario, error = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert scenario is None
    assert error is not None


def test_validate_scenario_filters_out_of_range_status_codes():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [200, 999, "not-an-int"],
    }

    scenario, error = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert error is None
    assert scenario.expected_status == [200]


def test_validate_scenario_rejects_empty_expected_status():
    raw = {
        "operation_id": "getArticle",
        "scenario": "nominal",
        "method": "GET",
        "path": "/api/articles/1",
        "body": None,
        "expected_status": [],
    }

    scenario, error = validate_scenario(raw, {"getArticle": ENDPOINT})

    assert scenario is None
    assert error is not None


def test_assign_test_names_appends_numeric_suffix_on_duplicates():
    s1 = Scenario("getArticle", "nominal", "GET", "/api/articles/1", None, [200])
    s2 = Scenario("getArticle", "nominal", "GET", "/api/articles/2", None, [200])

    named = assign_test_names([s1, s2])

    assert [name for name, _ in named] == [
        "test_getarticle_nominal",
        "test_getarticle_nominal_2",
    ]


def test_render_scenario_lines_uses_raw_body_for_string_body():
    scenario = Scenario(
        "createArticle", "body_malforme", "POST", "/api/articles", "{not-valid-json", [400, 422]
    )

    code = "\n".join(render_scenario_lines("test_createarticle_body_malforme", scenario))

    assert "raw_body='{not-valid-json'" in code
    assert "'expected': [400, 422]" in code
    assert "'passed': status in {400, 422}" in code
    assert "log_assertions(checks)" in code
    assert "assert all(c['passed'] for c in checks), format_checks(checks)" in code


def test_render_scenario_lines_uses_body_kwarg_for_dict_body():
    scenario = Scenario(
        "createArticle", "nominal", "POST", "/api/articles", {"title": "x"}, [201]
    )

    code = "\n".join(render_scenario_lines("test_createarticle_nominal", scenario))

    assert "body={'title': 'x'}" in code
    assert "'expected': [201]" in code
    assert "'passed': status in {201}" in code


def test_render_scenario_lines_omits_auth_kwarg_when_not_required():
    scenario = Scenario("getArticle", "nominal", "GET", "/api/articles/1", None, [200])

    code = "\n".join(render_scenario_lines("test_getarticle_nominal", scenario))

    assert "auth=" not in code


def test_render_scenario_lines_emits_schema_assertion_when_response_schema_known():
    scenario = Scenario(
        "getArticle",
        "nominal",
        "GET",
        "/api/articles/1",
        None,
        [200],
        response_schemas={200: {"type": "object", "properties": {"id": {"type": "integer"}}}},
    )

    code = "\n".join(render_scenario_lines("test_getarticle_nominal", scenario))

    assert "status, body_text = request_api('GET', '/api/articles/1')" in code
    assert "schema = {200: {'type': 'object', 'properties': {'id': {'type': 'integer'}}}}.get(status)" in code
    assert (
        "checks.extend(collect_schema_checks(parse_json_body(body_text), schema, 'test_getarticle_nominal'))"
        in code
    )


def test_render_scenario_lines_omits_schema_assertion_when_no_response_schema():
    scenario = Scenario("getArticle", "nominal", "GET", "/api/articles/1", None, [200])

    code = "\n".join(render_scenario_lines("test_getarticle_nominal", scenario))

    assert "collect_schema_checks" not in code


def test_render_scenario_lines_passes_auth_true_when_required():
    scenario = Scenario(
        "createArticle", "nominal", "POST", "/api/articles", {"title": "x"}, [201], requires_auth=True
    )

    code = "\n".join(render_scenario_lines("test_createarticle_nominal", scenario))

    assert "body={'title': 'x'}, auth=True" in code


def test_render_scenario_lines_includes_extra_headers_without_auth():
    scenario = Scenario(
        "deleteArticle",
        "token_invalide",
        "DELETE",
        "/api/articles/1",
        None,
        [401],
        requires_auth=False,
        extra_headers={"Authorization": "Bearer invalid.token.value"},
    )

    code = "\n".join(render_scenario_lines("test_deletearticle_token_invalide", scenario))

    assert "headers={'Authorization': 'Bearer invalid.token.value'}" in code
    assert "auth=True" not in code

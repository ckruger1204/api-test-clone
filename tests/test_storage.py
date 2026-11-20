import json
from pathlib import Path

import pytest

from api_test_agent.generation.scenarios import Scenario
from api_test_agent.generation.storage import (
    SCENARIOS_FILENAME,
    TEST_FILE_NAME,
    SuiteNotFoundError,
    load_suite,
    render_suite_file,
    resolve_tests_dir,
    save_scenarios,
)

NOMINAL_SCENARIO = Scenario(
    operation_id="getArticle",
    scenario="nominal",
    method="GET",
    path="/api/articles/1",
    body=None,
    expected_status=[200],
    description="Vérifie la récupération d'un article existant.",
)

PROTECTED_SCENARIO = Scenario(
    operation_id="createArticle",
    scenario="nominal",
    method="POST",
    path="/api/articles",
    body={"title": "x"},
    expected_status=[201],
    requires_auth=True,
    description="Vérifie la création d'un article.",
)


def test_resolve_tests_dir_defaults_to_generated_tests_at_project_root(tmp_path: Path):
    assert resolve_tests_dir({}, tmp_path) == tmp_path / "generated_tests"


def test_resolve_tests_dir_honors_relative_config_value(tmp_path: Path):
    assert resolve_tests_dir({"tests_dir": "custom/tests"}, tmp_path) == tmp_path / "custom" / "tests"


def test_resolve_tests_dir_honors_absolute_config_value(tmp_path: Path):
    absolute = tmp_path / "elsewhere"
    assert resolve_tests_dir({"tests_dir": str(absolute)}, tmp_path) == absolute


def test_save_scenarios_writes_json_round_trippable(tmp_path: Path):
    scenarios_path = save_scenarios(
        tmp_path, [NOMINAL_SCENARIO, PROTECTED_SCENARIO], {"base_url": "http://localhost:5000"}
    )

    assert scenarios_path == tmp_path / SCENARIOS_FILENAME
    payload = json.loads(scenarios_path.read_text(encoding="utf-8"))

    assert payload["metadata"] == {"base_url": "http://localhost:5000"}
    assert [s["operation_id"] for s in payload["scenarios"]] == ["getArticle", "createArticle"]


def test_render_suite_file_produces_runnable_python(tmp_path: Path):
    file_path = render_suite_file(
        tmp_path, [NOMINAL_SCENARIO], base_url="http://localhost:5000", auth_headers=None
    )

    assert file_path == tmp_path / TEST_FILE_NAME
    code = file_path.read_text(encoding="utf-8")
    assert "def test_getarticle_nominal" in code
    compile(code, str(file_path), "exec")  # vérifie que c'est du Python valide


def test_load_suite_re_renders_py_from_edited_scenarios_json(tmp_path: Path):
    save_scenarios(tmp_path, [NOMINAL_SCENARIO], {"base_url": "http://localhost:5000"})

    # Édition manuelle de scenarios.json, comme le ferait un utilisateur.
    scenarios_path = tmp_path / SCENARIOS_FILENAME
    payload = json.loads(scenarios_path.read_text(encoding="utf-8"))
    payload["scenarios"][0]["path"] = "/api/articles/999"
    scenarios_path.write_text(json.dumps(payload), encoding="utf-8")

    suite = load_suite(tmp_path)

    assert suite.scenarios[0].path == "/api/articles/999"
    assert "'/api/articles/999'" in suite.file_path.read_text(encoding="utf-8")


def test_load_suite_falls_back_to_raw_py_file_without_scenarios_json(tmp_path: Path):
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_text("def test_hand_written():\n    assert True\n", encoding="utf-8")

    suite = load_suite(tmp_path)

    assert suite.file_path == file_path
    assert suite.scenarios is None
    assert suite.scenarios_path is None


def test_load_suite_raises_clear_error_when_nothing_exists(tmp_path: Path):
    with pytest.raises(SuiteNotFoundError):
        load_suite(tmp_path)


def test_save_and_load_cycle_never_persists_real_auth_secret(tmp_path: Path):
    save_scenarios(tmp_path, [PROTECTED_SCENARIO], {"base_url": "http://localhost:5000"})
    render_suite_file(
        tmp_path,
        [PROTECTED_SCENARIO],
        base_url="http://localhost:5000",
        auth_headers={"Authorization": "Bearer realsecrettoken123"},
    )

    scenarios_text = (tmp_path / SCENARIOS_FILENAME).read_text(encoding="utf-8")
    assert "realsecrettoken123" not in scenarios_text

    # Chargé à nouveau sans fournir le secret : la suite reste utilisable,
    # auth_headers n'est jamais lu depuis scenarios.json (il n'y est pas).
    suite = load_suite(tmp_path, auth_headers=None)
    assert suite.scenarios[0].requires_auth is True

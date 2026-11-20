import json
import subprocess
from pathlib import Path

import pytest

from api_test_agent.execution.runner import (
    EXIT_COLLECTION_ERROR,
    EXIT_MISSING_TEST_FILE,
    EXIT_PYTEST_NOT_FOUND,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    REQUEST_LOG_FILENAME,
    _derive_endpoint,
    _extract_test_name,
    _parse_junit_xml,
    _read_execution_log,
    run_pytest,
)

ALL_OUTCOMES_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="1" skipped="1" tests="4" time="0.1">
    <testcase classname="test_generated_api" name="test_health_check_nominal" time="0.01" />
    <testcase classname="test_generated_api" name="test_create_article_body_malforme" time="0.02">
      <failure message="assert 500 in {400, 422}">AssertionError: assert 500 in {400, 422}
more traceback lines</failure>
    </testcase>
    <testcase classname="test_generated_api" name="test_delete_article_id_introuvable" time="0.03">
      <error message="ConnectionRefusedError">Traceback (most recent call last):
ConnectionRefusedError: [Errno 111] Connection refused</error>
    </testcase>
    <testcase classname="test_generated_api" name="test_skip_me_nominal" time="0.0">
      <skipped message="not relevant here" />
    </testcase>
  </testsuite>
</testsuites>
"""

COLLECTION_ERROR_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="0" skipped="0" tests="0" time="0.01">
    <testcase classname="" name="test_generated_api" time="0.0">
      <error message="collection failure">SyntaxError: invalid syntax</error>
    </testcase>
  </testsuite>
</testsuites>
"""

SUCCESS_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="1" time="0.01">
    <testcase classname="test_generated_api" name="test_health_check_nominal" time="0.01" />
  </testsuite>
</testsuites>
"""


def _fake_subprocess_run(
    junit_xml: str, returncode: int, stdout: str = "", stderr: str = "", request_log_lines: list[dict] | None = None
):
    def _run(command, **kwargs):
        junit_arg = next(part for part in command if part.startswith("--junitxml="))
        junit_file = Path(junit_arg.split("=", 1)[1])
        junit_file.write_text(junit_xml, encoding="utf-8")
        if request_log_lines is not None:
            request_log_path = junit_file.parent / REQUEST_LOG_FILENAME
            request_log_path.write_text(
                "\n".join(json.dumps(line) for line in request_log_lines), encoding="utf-8"
            )
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    return _run


def test_run_pytest_missing_test_file_returns_distinct_outcome(tmp_path: Path):
    result = run_pytest(tmp_path / "does_not_exist.py", output_dir=tmp_path)

    assert result.outcome == "missing_test_file"
    assert result.exit_code == EXIT_MISSING_TEST_FILE
    assert result.tests == []


def test_parse_junit_xml_covers_passed_failed_error_skipped(tmp_path: Path):
    xml_path = tmp_path / "results.xml"
    xml_path.write_text(ALL_OUTCOMES_XML, encoding="utf-8")

    tests, totals = _parse_junit_xml(xml_path)

    outcomes = {t.name: t.outcome for t in tests}
    assert outcomes == {
        "test_health_check_nominal": "passed",
        "test_create_article_body_malforme": "failed",
        "test_delete_article_id_introuvable": "error",
        "test_skip_me_nominal": "skipped",
    }

    by_name = {t.name: t for t in tests}
    assert by_name["test_create_article_body_malforme"].message == "assert 500 in {400, 422}"
    assert by_name["test_create_article_body_malforme"].endpoint == "create_article"
    assert by_name["test_delete_article_id_introuvable"].endpoint == "delete_article"
    assert totals["tests"] == 4
    # Aucun journal de requêtes fourni : chaque test garde une liste vide,
    # jamais None (voir TestResult.requests).
    assert all(t.requests == [] for t in tests)


@pytest.mark.parametrize(
    ("pytest_current_test", "expected_name"),
    [
        ("tests/test_generated_api.py::test_health_check_nominal (call)", "test_health_check_nominal"),
        ("tests/test_generated_api.py::test_health_check_nominal (setup)", "test_health_check_nominal"),
        ("", None),
        ("malformed-without-double-colon", None),
    ],
)
def test_extract_test_name(pytest_current_test: str, expected_name: str | None):
    assert _extract_test_name(pytest_current_test) == expected_name


def test_read_execution_log_groups_request_entries_by_test_name(tmp_path: Path):
    log_path = tmp_path / REQUEST_LOG_FILENAME
    log_path.write_text(
        "\n".join(
            [
                json.dumps({"kind": "request", "test": "tests/test_generated_api.py::test_a (call)", "status": 200}),
                json.dumps({"kind": "request", "test": "tests/test_generated_api.py::test_a (call)", "status": 201}),
                json.dumps({"kind": "request", "test": "tests/test_generated_api.py::test_b (call)", "status": 404}),
                "not even json",
            ]
        ),
        encoding="utf-8",
    )

    requests_by_test, assertions_by_test = _read_execution_log(log_path)

    assert [entry["status"] for entry in requests_by_test["test_a"]] == [200, 201]
    assert [entry["status"] for entry in requests_by_test["test_b"]] == [404]
    assert assertions_by_test == {}


def test_read_execution_log_separates_assertions_entries(tmp_path: Path):
    log_path = tmp_path / REQUEST_LOG_FILENAME
    log_path.write_text(
        "\n".join(
            [
                json.dumps({"kind": "request", "test": "tests/test_generated_api.py::test_a (call)", "status": 200}),
                json.dumps(
                    {
                        "kind": "assertions",
                        "test": "tests/test_generated_api.py::test_a (call)",
                        "checks": [{"check": "status_code", "passed": True}],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    requests_by_test, assertions_by_test = _read_execution_log(log_path)

    assert len(requests_by_test["test_a"]) == 1
    assert assertions_by_test["test_a"][0]["checks"] == [{"check": "status_code", "passed": True}]


def test_read_execution_log_returns_empty_dicts_when_file_missing(tmp_path: Path):
    assert _read_execution_log(tmp_path / "does_not_exist.jsonl") == ({}, {})


def test_parse_junit_xml_attaches_matching_request_log_entries(tmp_path: Path):
    xml_path = tmp_path / "results.xml"
    xml_path.write_text(SUCCESS_XML, encoding="utf-8")
    request_log = {
        "test_health_check_nominal": [
            {"method": "GET", "path": "/health", "status": 200, "response_body": {"status": "ok"}}
        ]
    }

    tests, _ = _parse_junit_xml(xml_path, request_log)

    assert tests[0].requests == request_log["test_health_check_nominal"]


def test_parse_junit_xml_prefers_real_endpoint_from_logged_request(tmp_path: Path):
    xml_path = tmp_path / "results.xml"
    xml_path.write_text(SUCCESS_XML, encoding="utf-8")
    requests_by_test = {
        "test_health_check_nominal": [{"method": "GET", "path": "/health", "status": 200}]
    }

    tests, _ = _parse_junit_xml(xml_path, requests_by_test)

    # Sans journal, le nom du test aurait donné "health_check" (heuristique) ;
    # avec le journal, c'est la vraie méthode/chemin appelés qui prévaut.
    assert tests[0].endpoint == "GET /health"


def test_parse_junit_xml_attaches_matching_assertions(tmp_path: Path):
    xml_path = tmp_path / "results.xml"
    xml_path.write_text(SUCCESS_XML, encoding="utf-8")
    assertions_by_test = {
        "test_health_check_nominal": [{"checks": [{"check": "status_code", "passed": True}]}]
    }

    tests, _ = _parse_junit_xml(xml_path, None, assertions_by_test)

    assert tests[0].assertions == [{"check": "status_code", "passed": True}]


def test_run_pytest_success_writes_results_json(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "test_generated_api.py"
    test_file.write_text("def test_x(): pass\n", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_run(SUCCESS_XML, returncode=0))

    result = run_pytest(test_file, output_dir=tmp_path)

    assert result.outcome == "success"
    assert result.exit_code == EXIT_SUCCESS
    assert result.passed == 1


def test_run_pytest_reads_request_log_from_output_dir_even_when_test_file_lives_elsewhere(tmp_path: Path):
    """Régression : output_dir (tests_dir/runs/<horodatage>/) peut différer du
    dossier du fichier de test (tests_dir/) — request_api() doit journaliser
    dans output_dir (via API_TEST_AGENT_REQUEST_LOG, voir generation/model_client.py
    :build_header_lines), pas dans le dossier du fichier de test lui-même.
    Exécute un VRAI sous-processus pytest (pas de subprocess.run monkeypatché)
    pour vérifier la propagation de la variable d'environnement de bout en bout."""
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    test_file = suite_dir / "test_generated_api.py"
    test_file.write_text(
        "import json\n"
        "import os\n"
        "\n"
        "def test_writes_to_env_configured_path():\n"
        "    log_path = os.environ['API_TEST_AGENT_REQUEST_LOG']\n"
        "    with open(log_path, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps({'kind': 'request', "
        "'test': os.environ.get('PYTEST_CURRENT_TEST', ''), 'status': 200}) + '\\n')\n"
        "    assert True\n",
        encoding="utf-8",
    )

    run_dir = tmp_path / "runs" / "20260101-000000"

    result = run_pytest(test_file, output_dir=run_dir)

    assert result.outcome == "success"
    assert (run_dir / REQUEST_LOG_FILENAME).exists()
    assert not (suite_dir / REQUEST_LOG_FILENAME).exists()
    assert result.tests[0].requests and result.tests[0].requests[0]["status"] == 200


def test_run_pytest_attaches_request_log_to_matching_test_in_results_json(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "test_generated_api.py"
    test_file.write_text("def test_x(): pass\n", encoding="utf-8")
    request_log_lines = [
        {
            "test": "test_generated_api.py::test_health_check_nominal (call)",
            "method": "GET",
            "path": "/health",
            "request_headers": {"Accept": "application/json"},
            "request_body": None,
            "status": 200,
            "response_body": {"status": "ok"},
        }
    ]
    monkeypatch.setattr(
        subprocess, "run", _fake_subprocess_run(SUCCESS_XML, returncode=0, request_log_lines=request_log_lines)
    )

    result = run_pytest(test_file, output_dir=tmp_path)

    assert result.tests[0].requests == request_log_lines
    payload = json.loads(result.results_json_path.read_text(encoding="utf-8"))
    assert payload["tests"][0]["requests"] == request_log_lines


def test_run_pytest_deletes_stale_request_log_before_running(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "test_generated_api.py"
    test_file.write_text("def test_x(): pass\n", encoding="utf-8")
    (tmp_path / REQUEST_LOG_FILENAME).write_text(
        json.dumps({"test": "test_generated_api.py::test_health_check_nominal (call)", "status": 500}),
        encoding="utf-8",
    )
    # Le run courant ne journalise rien (pas de request_log_lines) : le
    # fichier d'un run précédent ne doit pas polluer ce résultat.
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_run(SUCCESS_XML, returncode=0))

    result = run_pytest(test_file, output_dir=tmp_path)

    assert result.tests[0].requests == []

    payload = json.loads(result.results_json_path.read_text(encoding="utf-8"))
    assert payload["outcome"] == "success"
    assert payload["totals"]["passed"] == 1
    assert len(payload["tests"]) == 1
    assert result.log_path.exists()


def test_run_pytest_detects_collection_error(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "test_generated_api.py"
    test_file.write_text("def broken(:\n", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_run(COLLECTION_ERROR_XML, returncode=2))

    result = run_pytest(test_file, output_dir=tmp_path)

    assert result.outcome == "collection_error"
    assert result.exit_code == EXIT_COLLECTION_ERROR
    assert result.message is not None


def test_run_pytest_detects_pytest_not_found(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "test_generated_api.py"
    test_file.write_text("def test_x(): pass\n", encoding="utf-8")

    def _run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "No module named pytest")

    monkeypatch.setattr(subprocess, "run", _run)

    result = run_pytest(test_file, output_dir=tmp_path)

    assert result.outcome == "pytest_not_found"
    assert result.exit_code == EXIT_PYTEST_NOT_FOUND


def test_run_pytest_detects_timeout(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "test_generated_api.py"
    test_file.write_text("def test_x(): pass\n", encoding="utf-8")

    def _run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(subprocess, "run", _run)

    result = run_pytest(test_file, output_dir=tmp_path, run_timeout=5)

    assert result.outcome == "timeout"
    assert result.exit_code == EXIT_TIMEOUT


@pytest.mark.parametrize(
    ("test_name", "expected_endpoint"),
    [
        ("test_getarticle_nominal", "getarticle"),
        ("test_getarticle_id_introuvable", "getarticle"),
        ("test_createarticle_body_malforme", "createarticle"),
        ("test_getarticle_nominal_2", "getarticle"),
        ("test_unknown_route_returns_client_error", None),
    ],
)
def test_derive_endpoint(test_name: str, expected_endpoint: str | None):
    assert _derive_endpoint(test_name) == expected_endpoint

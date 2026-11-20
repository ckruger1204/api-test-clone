from pathlib import Path

from api_test_agent.generation.scenarios import Scenario
from api_test_agent.pipeline.context import RunContext
from api_test_agent.reporting.report_builder import build_detailed_report

NOMINAL = Scenario(
    operation_id="getArticle",
    scenario="nominal",
    method="GET",
    path="/api/articles/1",
    body=None,
    expected_status=[200],
    description="Vérifie la récupération d'un article existant.",
)

TOKEN_ABSENT = Scenario(
    operation_id="createArticle",
    scenario="token_absent",
    method="POST",
    path="/api/articles",
    body={"title": "x"},
    expected_status=[401],
    description="Vérifie le rejet sans jeton.",
)


def _ctx(**overrides) -> RunContext:
    ctx = RunContext(workdir=Path("."))
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


def test_build_detailed_report_joins_scenario_metadata_onto_result():
    ctx = _ctx(
        mode="generate",
        scenarios=[NOMINAL],
        results=[
            {
                "name": "test_getarticle_nominal",
                "outcome": "passed",
                "duration_s": 0.05,
                "message": None,
                "endpoint": "GET /api/articles/1",
                "requests": [{"method": "GET", "path": "/api/articles/1", "status": 200}],
                "assertions": [{"check": "status_code", "passed": True}],
            }
        ],
    )

    report = build_detailed_report(ctx)

    assert len(report["tests"]) == 1
    row = report["tests"][0]
    assert row["description"] == "Vérifie la récupération d'un article existant."
    assert row["method"] == "GET"
    assert row["path"] == "/api/articles/1"
    assert row["expected_status"] == [200]
    assert row["outcome"] == "passed"
    assert row["assertions"] == [{"check": "status_code", "passed": True}]


def test_build_detailed_report_marks_scenario_without_result_as_not_executed():
    ctx = _ctx(mode="generate", scenarios=[NOMINAL, TOKEN_ABSENT], results=[])

    report = build_detailed_report(ctx)

    names = {row["name"]: row["outcome"] for row in report["tests"]}
    assert names == {
        "test_getarticle_nominal": "not_executed",
        "test_createarticle_token_absent": "not_executed",
    }
    assert report["summary"]["not_executed"] == 2
    assert report["summary"]["total"] == 2


def test_build_detailed_report_handles_result_without_matching_scenario():
    """Cas du fichier .py sans scenarios.json (chargement "brut", voir
    generation/storage.py) : pas de scénario à joindre, mais le résultat
    reste exploitable (endpoint reconstruit depuis la requête journalisée)."""
    ctx = _ctx(
        mode="load",
        scenarios=None,
        results=[
            {
                "name": "test_unknown_route_returns_client_error",
                "outcome": "passed",
                "duration_s": 0.01,
                "message": None,
                "endpoint": "GET /__api_test_agent_unknown_route__",
                "requests": [],
                "assertions": [],
            }
        ],
    )

    report = build_detailed_report(ctx)

    row = report["tests"][0]
    assert row["description"] is None
    assert row["method"] == "GET"
    assert row["path"] == "/__api_test_agent_unknown_route__"


def test_build_detailed_report_summary_counts_all_buckets():
    ctx = _ctx(
        mode="generate",
        scenarios=[NOMINAL],
        results=[
            {"name": "a", "outcome": "passed", "duration_s": 0.0, "message": None, "endpoint": None},
            {"name": "b", "outcome": "failed", "duration_s": 0.0, "message": "boom", "endpoint": None},
            {"name": "c", "outcome": "error", "duration_s": 0.0, "message": "crash", "endpoint": None},
            {"name": "d", "outcome": "skipped", "duration_s": 0.0, "message": None, "endpoint": None},
        ],
    )

    report = build_detailed_report(ctx)

    # NOMINAL (test_getarticle_nominal) n'a pas de résultat -> not_executed en plus.
    assert report["summary"] == {
        "passed": 1,
        "failed": 1,
        "error": 1,
        "skipped": 1,
        "not_executed": 1,
        "total": 5,
    }


def test_build_detailed_report_includes_mode_and_dirs():
    ctx = _ctx(
        mode="view",
        scenarios=None,
        results=[],
        tests_dir=Path("generated_tests"),
        run_dir=Path("generated_tests/runs/20260115-000000"),
    )

    report = build_detailed_report(ctx)

    assert report["mode"] == "view"
    assert report["tests_dir"] == str(Path("generated_tests"))
    assert report["run_dir"] == str(Path("generated_tests/runs/20260115-000000"))

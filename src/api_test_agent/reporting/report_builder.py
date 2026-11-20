from __future__ import annotations

from typing import Any

from ..generation.scenarios import assign_test_names
from ..pipeline.context import RunContext

OUTCOME_BUCKETS = ("passed", "failed", "error", "skipped", "not_executed")


def build_detailed_report(ctx: RunContext) -> dict[str, Any]:
    """Joint les faits bruts d'exécution (ctx.results, remplis par
    ExecutionStage/ViewStage — status/requêtes/assertions) avec les scénarios
    connus (ctx.scenarios, remplis par GenerationStage ou LoadStage) par nom de
    test, pour que chaque ligne du rapport porte à la fois ce qui était PRÉVU
    (description, statut attendu) et ce qui a été OBSERVÉ (requêtes, réponses,
    détail des assertions). Les scénarios sans résultat correspondant
    deviennent des lignes "not_executed"."""
    scenario_by_name: dict[str, Any] = {}
    if ctx.scenarios:
        scenario_by_name = dict(assign_test_names(ctx.scenarios))

    results_by_name = {result.get("name"): result for result in ctx.results if result.get("name")}

    rows: list[dict[str, Any]] = [
        _row_from_result(name, result, scenario_by_name.get(name))
        for name, result in results_by_name.items()
    ]

    for name, scenario in scenario_by_name.items():
        if name not in results_by_name:
            rows.append(_row_not_executed(name, scenario))

    rows.sort(key=lambda row: row["name"])

    return {
        "mode": ctx.mode,
        "tests_dir": str(ctx.tests_dir) if ctx.tests_dir else None,
        "run_dir": str(ctx.run_dir) if ctx.run_dir else None,
        "summary": _build_summary(rows),
        "tests": rows,
    }


def _row_from_result(name: str, result: dict[str, Any], scenario: Any | None) -> dict[str, Any]:
    method, path = _method_and_path(result, scenario)
    return {
        "name": name,
        "description": scenario.description if scenario else None,
        "method": method,
        "path": path,
        "endpoint": result.get("endpoint"),
        "expected_status": sorted(set(scenario.expected_status)) if scenario else None,
        "outcome": result.get("outcome"),
        "duration_s": result.get("duration_s"),
        "message": result.get("message"),
        "requests": result.get("requests") or [],
        "assertions": result.get("assertions") or [],
    }


def _row_not_executed(name: str, scenario: Any) -> dict[str, Any]:
    return {
        "name": name,
        "description": scenario.description,
        "method": scenario.method,
        "path": scenario.path,
        "endpoint": f"{scenario.method} {scenario.path}",
        "expected_status": sorted(set(scenario.expected_status)),
        "outcome": "not_executed",
        "duration_s": None,
        "message": "Scénario prévu mais jamais exécuté (voir la collecte des tests).",
        "requests": [],
        "assertions": [],
    }


def _method_and_path(result: dict[str, Any], scenario: Any | None) -> tuple[str | None, str | None]:
    if scenario is not None:
        return scenario.method, scenario.path
    endpoint = result.get("endpoint") or ""
    parts = endpoint.split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {bucket: 0 for bucket in OUTCOME_BUCKETS}
    for row in rows:
        outcome = row.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    counts["total"] = len(rows)
    return counts

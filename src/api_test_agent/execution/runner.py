from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RUN_TIMEOUT = 300
REQUEST_LOG_FILENAME = "request_log.jsonl"

# Codes de sortie distincts par type d'incident d'exécution (différents du code
# brut renvoyé par pytest, qui ne distingue pas ces cas).
EXIT_SUCCESS = 0
EXIT_TEST_FAILURES = 1
EXIT_MISSING_TEST_FILE = 10
EXIT_PYTEST_NOT_FOUND = 11
EXIT_TIMEOUT = 12
EXIT_COLLECTION_ERROR = 13

# Suffixes de scénario connus (voir testing/prompts.py) utilisés pour déduire
# l'endpoint à partir d'un nom test_<operation_id>_<scenario> ; au-delà de ces
# cas connus, la déduction reste une approximation best-effort.
KNOWN_SCENARIO_SUFFIXES = ("nominal", "id_introuvable", "body_malforme")


@dataclass(frozen=True)
class TestResult:
    name: str
    outcome: str  # passed | failed | error | skipped
    duration_s: float
    message: str | None
    endpoint: str | None
    # Une entrée par appel request_api() journalisé pendant ce test (voir
    # generation/model_client.py:log_call) — requêtes envoyées et réponses
    # reçues, secrets déjà masqués à la source. Vide si le test n'en a fait
    # aucun, ou si le journal n'a pas pu être lu.
    requests: list[dict] = field(default_factory=list)
    # Détail de chaque vérification exécutée (status_code + un check par champ
    # du schéma de réponse, voir generation/model_client.py:collect_schema_checks
    # et log_assertions) — {check, expected, actual, passed}. Vide si le test
    # n'a journalisé aucune assertion (ex: test_unknown_route_returns_client_error,
    # qui n'utilise pas ce mécanisme).
    assertions: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    outcome: str  # success | test_failures | missing_test_file | pytest_not_found | timeout | collection_error
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_s: float
    tests: list[TestResult]
    command: list[str]
    message: str | None
    results_json_path: Path | None
    log_path: Path | None


def run_pytest(
    file_path: Path,
    output_dir: Path,
    run_timeout: int = DEFAULT_RUN_TIMEOUT,
) -> ExecutionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    junit_path = output_dir / "results.xml"
    log_path = output_dir / "pytest_output.log"
    results_json_path = output_dir / "results.json"
    request_log_path = output_dir / REQUEST_LOG_FILENAME
    started_at = datetime.now(timezone.utc)

    # Un journal d'un run précédent ne doit jamais être confondu avec celui du
    # run courant (request_api() journalise en mode ajout, voir model_client.py).
    request_log_path.unlink(missing_ok=True)

    if not file_path.exists():
        return _finalize(
            outcome="missing_test_file",
            exit_code=EXIT_MISSING_TEST_FILE,
            message=f"Fichier de tests introuvable : {file_path}",
            command=[],
            duration_s=0.0,
            tests=[],
            log_path=None,
            results_json_path=results_json_path,
            started_at=started_at,
        )

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(file_path),
        "-rA",
        "--tb=short",
        f"--junitxml={junit_path}",
    ]

    # Le fichier de test vit dans tests_dir, mais output_dir (où runner.py lit
    # request_log.jsonl ensuite) est désormais tests_dir/runs/<horodatage>/ :
    # ce ne sont plus forcément le même dossier (voir execution/run_history.py).
    # On impose donc explicitement où request_api() doit écrire son journal,
    # plutôt que de laisser le fichier généré déduire ce chemin de __file__.
    env = {**os.environ, "API_TEST_AGENT_REQUEST_LOG": str(request_log_path)}

    started = time.monotonic()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=run_timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        log_path.write_text(_format_log(command, exc.stdout or "", exc.stderr or ""), encoding="utf-8")
        return _finalize(
            outcome="timeout",
            exit_code=EXIT_TIMEOUT,
            message=f"Timeout dépassé ({run_timeout}s) pendant l'exécution des tests.",
            command=command,
            duration_s=duration,
            tests=[],
            log_path=log_path,
            results_json_path=results_json_path,
            started_at=started_at,
        )

    duration = time.monotonic() - started
    log_path.write_text(_format_log(command, completed.stdout, completed.stderr), encoding="utf-8")

    if not junit_path.exists():
        if "No module named" in completed.stderr and "pytest" in completed.stderr:
            return _finalize(
                outcome="pytest_not_found",
                exit_code=EXIT_PYTEST_NOT_FOUND,
                message="pytest est introuvable dans l'environnement Python utilisé.",
                command=command,
                duration_s=duration,
                tests=[],
                log_path=log_path,
                results_json_path=results_json_path,
                started_at=started_at,
            )
        return _finalize(
            outcome="collection_error",
            exit_code=EXIT_COLLECTION_ERROR,
            message="pytest n'a produit aucun rapport (voir pytest_output.log).",
            command=command,
            duration_s=duration,
            tests=[],
            log_path=log_path,
            results_json_path=results_json_path,
            started_at=started_at,
        )

    requests_by_test, assertions_by_test = _read_execution_log(request_log_path)
    tests, totals = _parse_junit_xml(junit_path, requests_by_test, assertions_by_test)
    passed = sum(1 for t in tests if t.outcome == "passed")
    failed = sum(1 for t in tests if t.outcome == "failed")
    errors = sum(1 for t in tests if t.outcome == "error")
    skipped = sum(1 for t in tests if t.outcome == "skipped")

    is_collection_error = errors > 0 and (
        totals["tests"] == 0 or any(t.outcome == "error" and not t.name.startswith("test_") for t in tests)
    )

    if is_collection_error:
        outcome = "collection_error"
        exit_code = EXIT_COLLECTION_ERROR
        message = "La collecte des tests a échoué (voir les erreurs listées)."
    elif failed or errors:
        outcome = "test_failures"
        exit_code = EXIT_TEST_FAILURES
        message = None
    else:
        outcome = "success"
        exit_code = EXIT_SUCCESS
        message = None

    return _finalize(
        outcome=outcome,
        exit_code=exit_code,
        message=message,
        command=command,
        duration_s=duration,
        tests=tests,
        log_path=log_path,
        results_json_path=results_json_path,
        started_at=started_at,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
    )


def _finalize(
    *,
    outcome: str,
    exit_code: int,
    message: str | None,
    command: list[str],
    duration_s: float,
    tests: list[TestResult],
    log_path: Path | None,
    results_json_path: Path | None,
    started_at: datetime,
    passed: int = 0,
    failed: int = 0,
    errors: int = 0,
    skipped: int = 0,
) -> ExecutionResult:
    result = ExecutionResult(
        exit_code=exit_code,
        outcome=outcome,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        duration_s=duration_s,
        tests=tests,
        command=command,
        message=message,
        results_json_path=results_json_path,
        log_path=log_path,
    )
    if results_json_path is not None:
        _write_results_json(results_json_path, result, started_at)
    return result


def _write_results_json(path: Path, result: ExecutionResult, started_at: datetime) -> None:
    payload = {
        "date": started_at.isoformat(),
        "command": result.command,
        "exit_code": result.exit_code,
        "outcome": result.outcome,
        "duration_s": result.duration_s,
        "totals": {
            "passed": result.passed,
            "failed": result.failed,
            "errors": result.errors,
            "skipped": result.skipped,
        },
        "message": result.message,
        "tests": [asdict(t) for t in result.tests],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _format_log(command: list[str], stdout: str, stderr: str) -> str:
    return f"$ {' '.join(command)}\n\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"


def _read_execution_log(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Lit request_log.jsonl (une ligne JSON par appel request_api() ou par
    log_assertions(), voir generation/model_client.py) et regroupe les entrées
    par nom de test court (champ `test`, valeur de la variable d'environnement
    PYTEST_CURRENT_TEST au moment de l'appel), séparées par leur `kind` :
    "request" (requête/réponse) vs "assertions" (détail des vérifications)."""
    requests_by_test: dict[str, list[dict]] = {}
    assertions_by_test: dict[str, list[dict]] = {}

    if not path.exists():
        return requests_by_test, assertions_by_test

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        test_name = _extract_test_name(entry.get("test", ""))
        if not test_name:
            continue
        if entry.get("kind") == "assertions":
            assertions_by_test.setdefault(test_name, []).append(entry)
        else:
            requests_by_test.setdefault(test_name, []).append(entry)

    return requests_by_test, assertions_by_test


def _flatten_checks(assertion_entries: list[dict]) -> list[dict]:
    checks: list[dict] = []
    for entry in assertion_entries:
        checks.extend(entry.get("checks") or [])
    return checks


def _endpoint_from_requests(requests: list[dict]) -> str | None:
    """Méthode + chemin réellement appelés, d'après la première requête
    journalisée — plus fiable que de les déduire du nom du test."""
    if not requests:
        return None
    method = requests[0].get("method")
    path = requests[0].get("path")
    return f"{method} {path}" if method and path else None


def _extract_test_name(pytest_current_test: str) -> str | None:
    match = re.search(r"::([^\s(]+)", pytest_current_test or "")
    return match.group(1) if match else None


def _parse_junit_xml(
    xml_path: Path,
    requests_by_test: dict[str, list[dict]] | None = None,
    assertions_by_test: dict[str, list[dict]] | None = None,
) -> tuple[list[TestResult], dict]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    if suite is None:
        return [], {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}

    totals = {
        "tests": int(suite.get("tests", 0)),
        "failures": int(suite.get("failures", 0)),
        "errors": int(suite.get("errors", 0)),
        "skipped": int(suite.get("skipped", 0)),
    }

    requests_by_test = requests_by_test or {}
    assertions_by_test = assertions_by_test or {}
    tests: list[TestResult] = []
    for case in suite.findall("testcase"):
        name = case.get("name", "")
        duration = float(case.get("time", 0.0) or 0.0)
        failure = case.find("failure")
        error = case.find("error")
        skipped_el = case.find("skipped")

        if failure is not None:
            outcome, message = "failed", _first_line(failure.get("message") or failure.text or "")
        elif error is not None:
            outcome, message = "error", _first_line(error.get("message") or error.text or "")
        elif skipped_el is not None:
            outcome, message = "skipped", _first_line(skipped_el.get("message") or "")
        else:
            outcome, message = "passed", None

        test_requests = requests_by_test.get(name, [])

        tests.append(
            TestResult(
                name=name,
                outcome=outcome,
                duration_s=duration,
                message=message or None,
                endpoint=_endpoint_from_requests(test_requests) or _derive_endpoint(name),
                requests=test_requests,
                assertions=_flatten_checks(assertions_by_test.get(name, [])),
            )
        )

    return tests, totals


def _derive_endpoint(test_name: str) -> str | None:
    """Déduit l'endpoint depuis test_<operation_id>_<scenario> : best-effort,
    fiable seulement pour les scénarios connus de testing/prompts.py."""
    if test_name == "test_unknown_route_returns_client_error" or not test_name.startswith("test_"):
        return None

    remainder = test_name[len("test_"):]
    remainder = re.sub(r"_\d+$", "", remainder)  # suffixe de déduplication (_2, _3, ...)

    for suffix in KNOWN_SCENARIO_SUFFIXES:
        if remainder.endswith(f"_{suffix}"):
            endpoint = remainder[: -(len(suffix) + 1)]
            return endpoint or None

    if "_" in remainder:
        return remainder.rsplit("_", 1)[0]
    return None


def _first_line(text: str) -> str:
    text = text.strip()
    return text.splitlines()[0] if text else ""

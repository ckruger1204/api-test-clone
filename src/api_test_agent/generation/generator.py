from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model_client import GenerationRequest, build_header_lines
from .negative_scenarios import build_deterministic_scenarios
from .prompts import build_batch_prompt
from .scenarios import (
    Scenario,
    ScenarioParseError,
    assign_test_names,
    endpoint_key,
    parse_scenario_response,
    render_scenario_lines,
    validate_scenario,
)

DEFAULT_BATCH_SIZE = 4


@dataclass(frozen=True)
class GeneratedTestArtifact:
    file_path: Path
    test_count: int
    endpoints_total: int
    endpoints_covered: int
    uncovered_endpoints: list[str]
    batch_count: int
    failed_batch_count: int
    duration_seconds: float
    raw_responses_path: Path
    # Liste structurée des scénarios retenus (modèle + déterministes), dans
    # l'ordre de rendu — utilisée par generation/storage.py pour persister
    # scenarios.json à côté du fichier .py rendu.
    scenarios: list[Scenario] = field(default_factory=list)


def generate_test_file(
    contract_payload: dict[str, Any],
    output_dir: Path,
    model_client: Any,
    batch_size: int = DEFAULT_BATCH_SIZE,
    auth_headers: dict[str, str] | None = None,
) -> GeneratedTestArtifact:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_url = contract_payload.get("base_url", "http://localhost:8000")
    endpoints = contract_payload.get("endpoints", [])

    started = time.monotonic()
    batches = [endpoints[i : i + batch_size] for i in range(0, len(endpoints), batch_size)]

    all_lines = build_header_lines(base_url, auth_headers)
    failed_batch_count = 0
    covered_operation_ids: set[str] = set()
    raw_batches: list[dict[str, Any]] = []

    # Scénarios négatifs garantis par le code (absence/invalidité de token,
    # champ requis manquant/mauvais type) : générés pour tous les endpoints
    # concernés, indépendamment du succès du modèle sur leur lot — ils ne
    # comptent pas pour endpoints_covered/uncovered_endpoints, qui restent le
    # reflet de ce que le modèle a lui-même produit (voir plus bas).
    all_scenarios: list[Scenario] = []
    for endpoint in endpoints:
        all_scenarios.extend(build_deterministic_scenarios(endpoint))

    for batch_index, batch in enumerate(batches, start=1):
        endpoints_desc = ", ".join(f"{e.get('method', 'GET')} {e.get('path', '/')}" for e in batch)
        print(f"[generation] lot {batch_index}/{len(batches)} ({len(batch)} endpoint(s)) — appel au modèle...")

        batch_started = time.monotonic()
        scenarios, failed, raw_attempts = _request_batch_scenarios(model_client, batch)
        batch_duration = time.monotonic() - batch_started

        raw_batches.append(
            {
                "batch_index": batch_index,
                "endpoints": endpoints_desc,
                "raw_responses": raw_attempts,
            }
        )
        if failed:
            failed_batch_count += 1
            print(
                f"[generation] lot {batch_index}/{len(batches)} échoué en {batch_duration:.1f}s — "
                f"le modèle n'a pas produit de scénarios JSON valides (après un réessai) "
                f"pour [{endpoints_desc}] — aucun test généré pour ces endpoints."
            )
        else:
            print(
                f"[generation] lot {batch_index}/{len(batches)} terminé en {batch_duration:.1f}s : "
                f"{len(scenarios)} scénario(s) valide(s)."
            )
        all_scenarios.extend(scenarios)
        covered_operation_ids.update(scenario.operation_id for scenario in scenarios)

    for test_name, scenario in assign_test_names(all_scenarios):
        all_lines.extend(render_scenario_lines(test_name, scenario))
        all_lines.append("")

    code = "\n".join(all_lines).strip() + "\n"
    file_path = output_dir / "test_generated_api.py"
    file_path.write_text(code, encoding="utf-8")

    raw_responses_path = output_dir / "qwen_raw_responses.json"
    raw_responses_path.write_text(json.dumps(raw_batches, indent=2, ensure_ascii=False), encoding="utf-8")

    test_count = sum(1 for line in code.splitlines() if line.strip().startswith("def test_"))

    uncovered = [
        endpoint_key(endpoint)
        for endpoint in endpoints
        if endpoint.get("operation_id") not in covered_operation_ids
    ]

    return GeneratedTestArtifact(
        file_path=file_path,
        test_count=test_count,
        endpoints_total=len(endpoints),
        endpoints_covered=len(endpoints) - len(uncovered),
        uncovered_endpoints=uncovered,
        batch_count=len(batches),
        failed_batch_count=failed_batch_count,
        duration_seconds=time.monotonic() - started,
        raw_responses_path=raw_responses_path,
        scenarios=all_scenarios,
    )


def _request_batch_scenarios(
    model_client: Any, batch: list[dict[str, Any]]
) -> tuple[list[Scenario], bool, list[str]]:
    """Demande à Qwen les scénarios JSON d'un lot ; réessaie une fois si la
    réponse n'est pas un JSON exploitable ou ne contient aucun scénario valide.
    Si le deuxième essai échoue aussi, le lot est marqué comme échoué (aucun
    repli déterministe). Renvoie aussi la/les réponses brutes du modèle, pour
    diagnostic (voir qwen_raw_responses.json)."""
    prompt = build_batch_prompt(batch)
    batch_payload = {"endpoints": batch}
    endpoints_by_operation_id = {
        endpoint["operation_id"]: endpoint for endpoint in batch if endpoint.get("operation_id")
    }

    raw_attempts: list[str] = []

    for _attempt in range(2):
        response = model_client.generate(GenerationRequest(prompt=prompt, contract_payload=batch_payload))
        raw_attempts.append(response)

        try:
            raw_scenarios = parse_scenario_response(response)
        except ScenarioParseError as exc:
            # print(f"AVERTISSEMENT: {exc}")
            continue

        valid_scenarios: list[Scenario] = []
        for raw in raw_scenarios:
            scenario, error = validate_scenario(raw, endpoints_by_operation_id)
            if error:
                # print(f"AVERTISSEMENT: {error}")
                continue
            valid_scenarios.append(scenario)

        if valid_scenarios:
            return valid_scenarios, False, raw_attempts

    return [], True, raw_attempts

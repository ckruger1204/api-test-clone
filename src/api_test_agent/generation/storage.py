from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_client import build_header_lines
from .scenarios import (
    Scenario,
    assign_test_names,
    render_scenario_lines,
    scenario_from_dict,
    scenario_to_dict,
)

SCENARIOS_FILENAME = "scenarios.json"
TEST_FILE_NAME = "test_generated_api.py"
DEFAULT_TESTS_DIR_NAME = "generated_tests"


class SuiteNotFoundError(FileNotFoundError):
    """Ni scenarios.json ni test_generated_api.py trouvés dans tests_dir."""


@dataclass(frozen=True)
class SavedSuite:
    tests_dir: Path
    file_path: Path
    scenarios_path: Path | None
    # None si la suite a été chargée depuis un .py écrit à la main, sans
    # scenarios.json — exécutable, mais sans description/statut attendu
    # disponibles pour le rapport détaillé (voir reporting/report_builder.py).
    scenarios: list[Scenario] | None
    metadata: dict[str, Any]


def resolve_tests_dir(config: dict[str, Any], project_root: Path) -> Path:
    """Résout la clé `tests_dir` de config.json (défaut : generated_tests/ à la
    racine du projet, visible et versionnable) — même logique de résolution de
    chemin relatif que openapi_spec_path dans cli/main.py."""
    raw = config.get("tests_dir")
    if raw is None:
        return project_root / DEFAULT_TESTS_DIR_NAME
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def save_scenarios(tests_dir: Path, scenarios: list[Scenario], metadata: dict[str, Any]) -> Path:
    """Écrit scenarios.json à côté du fichier .py déjà produit par
    generate_test_file() pour ce même tests_dir — ne touche jamais au fichier
    .py : au moment de cet appel (mode "generate"), il est déjà cohérent avec
    `scenarios`. metadata ne doit jamais contenir de secret (voir
    generation/auth.py) : seul base_url/title/version/stats de génération."""
    tests_dir.mkdir(parents=True, exist_ok=True)
    scenarios_path = tests_dir / SCENARIOS_FILENAME
    payload = {"metadata": metadata, "scenarios": [scenario_to_dict(s) for s in scenarios]}
    scenarios_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return scenarios_path


def render_suite_file(
    tests_dir: Path,
    scenarios: list[Scenario],
    base_url: str,
    auth_headers: dict[str, str] | None,
) -> Path:
    """(Re)génère test_generated_api.py à partir d'une liste de scénarios, avec
    les mêmes fonctions de rendu que generate_test_file() (aucune logique de
    rendu dupliquée) — pour qu'un scenarios.json édité à la main produise
    toujours un fichier de test cohérent avec son contenu."""
    lines = build_header_lines(base_url, auth_headers)
    for test_name, scenario in assign_test_names(scenarios):
        lines.extend(render_scenario_lines(test_name, scenario))
        lines.append("")
    code = "\n".join(lines).strip() + "\n"

    tests_dir.mkdir(parents=True, exist_ok=True)
    file_path = tests_dir / TEST_FILE_NAME
    file_path.write_text(code, encoding="utf-8")
    return file_path


def load_suite(tests_dir: Path, auth_headers: dict[str, str] | None = None) -> SavedSuite:
    """Charge une suite depuis tests_dir, sans jamais appeler le modèle.

    Si scenarios.json existe, il est la source de vérité : test_generated_api.py
    est systématiquement régénéré à partir de son contenu (voir
    render_suite_file), pour qu'une édition manuelle de scenarios.json soit
    toujours reflétée au prochain chargement. Sinon, si seul le .py existe
    (suite écrite à la main), il est chargé tel quel pour exécution directe."""
    scenarios_path = tests_dir / SCENARIOS_FILENAME
    file_path = tests_dir / TEST_FILE_NAME

    if scenarios_path.exists():
        payload = json.loads(scenarios_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata") or {}
        scenarios = [scenario_from_dict(raw) for raw in payload.get("scenarios") or []]
        base_url = metadata.get("base_url") or "http://localhost:8000"
        rendered_path = render_suite_file(tests_dir, scenarios, base_url, auth_headers)
        return SavedSuite(
            tests_dir=tests_dir,
            file_path=rendered_path,
            scenarios_path=scenarios_path,
            scenarios=scenarios,
            metadata=metadata,
        )

    if file_path.exists():
        return SavedSuite(
            tests_dir=tests_dir,
            file_path=file_path,
            scenarios_path=None,
            scenarios=None,
            metadata={},
        )

    raise SuiteNotFoundError(
        f"Aucune suite de tests trouvée dans {tests_dir} "
        f"(ni {SCENARIOS_FILENAME}, ni {TEST_FILE_NAME})."
    )

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class RunContext:
    # --- Entrées (issues #29, #30) ---
    spec_path: Path | None = None          # #30 : si None → auto-détection
    target_url: str | None = None
    model_options: dict[str, Any] = field(default_factory=dict)
    auth_config: dict[str, Any] | None = None  # section `auth` de config.json (voir generation/auth.py)
    workdir: Path = field(default_factory=Path.cwd)
    quiet: bool = False

    # --- Persistance / modes (sauvegarde, chargement, consultation) ---
    tests_dir: Path | None = None           # dossier de la suite (voir generation/storage.py)
    mode: str = "generate"                  # "generate" | "load" | "view" (pipeline/defaults.py:build_stages)
    run_id: str | None = None               # run ciblé en mode "view" ; None = le plus récent

    # --- Sorties produites par les étapes ---
    spec: dict | None = None                # #30 : spec OpenAPI chargée
    model_payload: dict | None = None       # #31 : payload prêt pour Qwen
    raw_model_output: str | None = None     # #32 : réponse brute du modèle
    generated_tests: list[Path] = field(default_factory=list)  # #32
    # Liste structurée des Scenario (generation.scenarios.Scenario), remplie
    # par GenerationStage (mode "generate") ou LoadStage (mode "load"/"view") —
    # typé Any pour ne pas faire dépendre pipeline/ du package generation/.
    scenarios: list[Any] | None = None
    generation_stats: dict | None = None    # #32 : endpoints_total/covered, uncovered_endpoints, batch_count, failed_batch_count
    results: list[dict] = field(default_factory=list)          # #33
    execution_stats: dict | None = None     # #33 : outcome, exit_code, message, results_json_path, log_path
    run_dir: Path | None = None             # dossier du run courant (ou consulté), voir execution/run_history.py
    summary: dict | None = None             # #34
    report: dict | None = None              # rapport détaillé joint scénarios+résultats, voir reporting/report_builder.py

    # --- État / diagnostic ---
    exit_code: int = 0
    errors: list[str] = field(default_factory=list)
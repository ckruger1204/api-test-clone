from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

RUNS_DIRNAME = "runs"
# Horodatage triable lexicographiquement -> le tri par nom suffit pour
# retrouver le run le plus récent, pas besoin d'index séparé.
_RUN_ID_FORMAT = "%Y%m%d-%H%M%S"


def new_run_dir(tests_dir: Path) -> Path:
    """Crée et renvoie un nouveau dossier tests_dir/runs/<horodatage>/, unique
    par appel (suffixe numérique en cas de collision dans la même seconde)."""
    runs_root = tests_dir / RUNS_DIRNAME
    runs_root.mkdir(parents=True, exist_ok=True)

    base_id = datetime.now(timezone.utc).strftime(_RUN_ID_FORMAT)
    run_dir = runs_root / base_id
    suffix = 2
    while run_dir.exists():
        run_dir = runs_root / f"{base_id}-{suffix}"
        suffix += 1

    run_dir.mkdir(parents=True)
    return run_dir


def list_runs(tests_dir: Path) -> list[Path]:
    """Dossiers de runs existants, du plus récent au plus ancien."""
    runs_root = tests_dir / RUNS_DIRNAME
    if not runs_root.is_dir():
        return []
    return sorted((p for p in runs_root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)


def latest_run(tests_dir: Path) -> Path | None:
    runs = list_runs(tests_dir)
    return runs[0] if runs else None


def find_run(tests_dir: Path, run_id: str) -> Path | None:
    """Résout un run_id explicite (nom de dossier sous runs/) vers son chemin."""
    candidate = tests_dir / RUNS_DIRNAME / run_id
    return candidate if candidate.is_dir() else None

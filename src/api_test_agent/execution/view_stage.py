import json

from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from .run_history import find_run, latest_run
from loguru import logger


class ViewStage(Stage):
    """Pointe ctx.run_dir/ctx.results vers un run déjà exécuté, sans jamais
    appeler pytest — pour "consulter les résultats d'exécutions précédentes"
    (mode "view", voir pipeline/defaults.py). Remplace ExecutionStage dans ce
    mode : ReportingStage s'exécute ensuite normalement sur ces données."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("view stage running...")

        if not ctx.tests_dir:
            raise ValueError("ctx.tests_dir is required (see cli/main.py:resolve_tests_dir).")

        run_dir = find_run(ctx.tests_dir, ctx.run_id) if ctx.run_id else latest_run(ctx.tests_dir)
        if run_dir is None:
            target = ctx.run_id or "le run le plus récent"
            raise ValueError(f"Aucun run trouvé pour {target} dans {ctx.tests_dir}.")

        results_json_path = run_dir / "results.json"
        if not results_json_path.is_file():
            raise ValueError(f"results.json introuvable dans {run_dir}.")

        payload = json.loads(results_json_path.read_text(encoding="utf-8"))

        ctx.run_dir = run_dir
        ctx.results = payload.get("tests", [])
        ctx.execution_stats = {
            "outcome": payload.get("outcome"),
            "exit_code": payload.get("exit_code"),
            "message": payload.get("message"),
            "results_json_path": str(results_json_path),
            "log_path": None,
            "run_dir": str(run_dir),
            "viewed": True,
        }

        logger.success(f"view stage completed ✅ (run {run_dir.name})")

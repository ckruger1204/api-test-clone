from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from .auth import resolve_auth_headers
from .storage import SuiteNotFoundError, load_suite
from loguru import logger


class LoadStage(Stage):
    """Charge une suite de tests déjà sauvegardée dans ctx.tests_dir, sans
    jamais appeler le modèle — remplace Discovery/Analysis/Generation pour les
    modes "load" et "view" (voir pipeline/defaults.py).

    En mode "load", la suite est le but de l'étape : son absence est une
    erreur bloquante (rien à exécuter). En mode "view", elle n'apporte qu'un
    contexte best-effort (description, statut attendu) pour enrichir un
    historique de runs qui peut survivre même si la suite a été déplacée ou
    supprimée depuis — son absence ne doit donc pas empêcher la consultation."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("load stage running...")

        if not ctx.tests_dir:
            raise ValueError("ctx.tests_dir is required (see cli/main.py:resolve_tests_dir).")

        auth_headers = resolve_auth_headers(ctx.auth_config)
        try:
            suite = load_suite(ctx.tests_dir, auth_headers=auth_headers)
        except SuiteNotFoundError:
            if ctx.mode == "view":
                logger.info(f"Aucune suite dans {ctx.tests_dir} : consultation sans contexte de scénarios.")
                ctx.scenarios = None
                ctx.generation_stats = {"source": "loaded", "test_count": None}
                return
            raise

        ctx.generated_tests = [suite.file_path]
        ctx.scenarios = suite.scenarios

        endpoints_total = suite.metadata.get("endpoints_total", 0)
        ctx.generation_stats = {
            "source": "loaded",
            "test_count": len(suite.scenarios) if suite.scenarios is not None else None,
            "endpoints_total": endpoints_total,
            "endpoints_covered": suite.metadata.get("endpoints_covered", endpoints_total),
            "uncovered_endpoints": suite.metadata.get("uncovered_endpoints", []),
            "batch_count": suite.metadata.get("batch_count", 0),
            "failed_batch_count": suite.metadata.get("failed_batch_count", 0),
            "raw_responses_path": None,
            "scenarios_path": str(suite.scenarios_path) if suite.scenarios_path else None,
        }

        logger.success(f"load stage completed ✅ (suite chargée depuis {ctx.tests_dir})")

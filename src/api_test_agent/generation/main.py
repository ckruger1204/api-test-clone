
from datetime import datetime, timezone

from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from .auth import resolve_auth_headers
from .generator import generate_test_file
from .model_client import HTTPModelClient
from .storage import save_scenarios
from loguru import logger

class GenerationStage(Stage):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("generation stage running...")

        if not ctx.model_payload:
            raise ValueError(
                "No contract payload available: the analysis stage must run first."
            )

        if not ctx.tests_dir:
            raise ValueError("ctx.tests_dir is required (see cli/main.py:resolve_tests_dir).")

        base_url = ctx.model_options.get("base_url")
        api_key = ctx.model_options.get("api_key")
        if not base_url or not api_key:
            raise ValueError(
                "model_options.base_url and model_options.api_key are required to call the model."
            )

        model_client = HTTPModelClient(
            base_url=base_url,
            model_name=ctx.model_options.get("model", "qwen2.5-coder"),
            api_key=api_key,
            timeout=int(ctx.model_options.get("timeout", 600)),
        )

        auth_headers = resolve_auth_headers(ctx.auth_config)

        artifact = generate_test_file(
            contract_payload=ctx.model_payload,
            output_dir=ctx.tests_dir,
            model_client=model_client,
            batch_size=int(ctx.model_options.get("batch_size", 4)),
            auth_headers=auth_headers,
        )

        # metadata ne doit jamais contenir de secret : seules des informations
        # publiques (base_url, titre, stats de génération) sont persistées dans
        # scenarios.json, lisible/versionnable par l'utilisateur.
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_url": ctx.model_payload.get("base_url"),
            "title": ctx.model_payload.get("title"),
            "version": ctx.model_payload.get("version"),
            "endpoints_total": artifact.endpoints_total,
            "endpoints_covered": artifact.endpoints_covered,
            "uncovered_endpoints": artifact.uncovered_endpoints,
            "batch_count": artifact.batch_count,
            "failed_batch_count": artifact.failed_batch_count,
        }
        scenarios_path = save_scenarios(ctx.tests_dir, artifact.scenarios, metadata)

        ctx.generated_tests = [artifact.file_path]
        ctx.scenarios = artifact.scenarios
        ctx.raw_model_output = str(artifact.raw_responses_path)
        ctx.generation_stats = {
            "source": "llm",
            "test_count": artifact.test_count,
            "endpoints_total": artifact.endpoints_total,
            "endpoints_covered": artifact.endpoints_covered,
            "uncovered_endpoints": artifact.uncovered_endpoints,
            "batch_count": artifact.batch_count,
            "failed_batch_count": artifact.failed_batch_count,
            "raw_responses_path": str(artifact.raw_responses_path),
            "scenarios_path": str(scenarios_path),
        }

        logger.success("generation stage completed ✅")

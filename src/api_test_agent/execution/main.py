
import dataclasses

from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from .run_history import new_run_dir
from .runner import run_pytest
from loguru import logger

class ExecutionStage(Stage):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("execution stage running...")

        if not ctx.generated_tests:
            raise ValueError(
                "No generated test file available: the generation stage must run first."
            )

        file_path = ctx.generated_tests[0]
        run_timeout = int(ctx.model_options.get("run_timeout", 300))

        run_dir = new_run_dir(ctx.tests_dir) if ctx.tests_dir else file_path.parent
        execution = run_pytest(file_path, output_dir=run_dir, run_timeout=run_timeout)

        ctx.run_dir = run_dir
        ctx.results = [dataclasses.asdict(test) for test in execution.tests]
        ctx.execution_stats = {
            "outcome": execution.outcome,
            "exit_code": execution.exit_code,
            "message": execution.message,
            "results_json_path": str(execution.results_json_path) if execution.results_json_path else None,
            "log_path": str(execution.log_path) if execution.log_path else None,
            "run_dir": str(run_dir),
        }

        logger.success("execution stage completed ✅")

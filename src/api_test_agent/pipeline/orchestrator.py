from .context import RunContext
from .stage import Stage
from ..exit_codes import ExitCode

class Orchestrator:
    def __init__(self, stages: list[Stage]):
        self.stages = stages

    def run(self, ctx: RunContext) -> RunContext:
        for stage in self.stages:
            if ctx.exit_code != ExitCode.OK:
                break
            try:
                stage.run(ctx)
            except Exception as e:
                ctx.errors.append(f"[{stage.name}] {e}")
                ctx.exit_code = ExitCode.INTERNAL
        return ctx
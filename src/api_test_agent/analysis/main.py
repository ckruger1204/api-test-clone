
from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from .contract import extract_contract_payload
from loguru import logger

class AnalysisStage(Stage):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("analysis stage running...")
        error = ""

        if ctx.spec is None:
            error = "No OpenAPI specification available: the discovery stage must run first."
            logger.error(error)
            raise ValueError(error)

        ctx.model_payload = extract_contract_payload(
            ctx.spec, base_url=ctx.target_url
        )

        if not ctx.model_payload.get("endpoints"):
            error = "The OpenAPI specification does not declare any usable endpoint."
            logger.error(error)
            raise ValueError(error)

        logger.success("analysis stage completed ✅")

# temporaire tant que tous le modules existent pas
from .context import RunContext

class NoopStage:
    def __init__(self, name: str): self.name = name
    def run(self, ctx: RunContext) -> None: ...
from typing import Protocol
from .context import RunContext

class Stage(Protocol):
    name: str
    def run(self, ctx: RunContext) -> None: ...
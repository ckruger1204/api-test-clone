
from pathlib import Path
from typing import Any

import json
import yaml

from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from loguru import logger
class DiscoveryStage(Stage):
    name: str

    SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("discovery stage running...")

        if not ctx.spec_path:
            raise ValueError(
                "The OpenAPI specification path is required."
            )

        path = Path(ctx.spec_path)

        if not path.exists():
            raise FileNotFoundError(
                f"OpenAPI specification file not found: '{path}'."
            )

        if not path.is_file():
            raise IsADirectoryError(
                f"Expected an OpenAPI specification file, "
                f"but got a directory or non-file path: '{path}'."
            )

        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Unsupported OpenAPI specification extension "
                f"'{extension or '<none>'}' for '{path}'. "
                f"Supported extensions: {supported}."
            )

        try:
            with path.open("r", encoding="utf-8") as handle:
                if extension == ".json":
                    spec: Any = json.load(handle)
                else:
                    spec = yaml.safe_load(handle)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ValueError(
                f"Failed to parse OpenAPI specification '{path}': {exc}"
            ) from exc

        if not isinstance(spec, dict):
            raise ValueError(
                f"Invalid OpenAPI specification '{path}': "
                "the document must contain a YAML or JSON object."
            )

        ctx.spec = spec

        try:
            ctx.target_url = _extract_server_url(spec)
        except Exception as exc:
            raise ValueError(
                f"API url is required to execute test, it's missing in openapi document: {exc}"
            ) from exc   

        logger.success("discovery stage completed ✅")

def _extract_server_url(spec: dict[str, Any]) -> str | None:
    servers = spec.get("servers")
    if not isinstance(servers, list):
        return None
    for server in servers:
        if isinstance(server, dict) and isinstance(server.get("url"), str) and server["url"].strip():
            return server["url"]
    return None

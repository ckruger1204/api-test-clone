import json
import sys
from pathlib import Path

from ..pipeline.context import RunContext
from ..pipeline.orchestrator import Orchestrator
from ..pipeline.defaults import MODES, build_stages
from ..generation.storage import resolve_tests_dir
from ..exit_codes import ExitCode
from loguru import logger


def load_config() -> tuple[dict, Path]:
    # Find the project root containing pyproject.toml
    current = Path(__file__).resolve()
    project_root = next(
        (
            parent
            for parent in current.parents
            if (parent / "pyproject.toml").is_file()
        ),
        None,
    )

    if project_root is None:
        raise FileNotFoundError(
            "Could not find project root (pyproject.toml)."
        )

    config_path = project_root / "config.json"

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    return config, project_root


def main() -> int:
    try:
        config, project_root = load_config()

        mode = config.get("mode", "generate")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)} (got {mode!r}).")

        run_id = config.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("run_id must be a string.")

        tests_dir = resolve_tests_dir(config, project_root)

        spec_path = None
        if mode == "generate":
            # La spec OpenAPI et le modèle ne sont requis que pour générer :
            # "load"/"view" repartent d'une suite déjà sauvegardée, sans LLM.
            spec_value = config.get("openapi_spec_path")

            if not isinstance(spec_value, str) or not spec_value.strip():
                raise ValueError(
                    "openapi_spec_path is required in config.json when mode is 'generate'."
                )

            spec_path = Path(spec_value)

            if not spec_path.is_absolute():
                spec_path = project_root / spec_path

        # Validate model options
        model_options = config.get("model_options", {})

        if not isinstance(model_options, dict):
            raise ValueError("model_options must be a JSON object.")

        auth_config = config.get("auth")
        if auth_config is not None and not isinstance(auth_config, dict):
            raise ValueError("auth must be a JSON object.")

        ctx = RunContext(
            spec_path=spec_path,
            target_url=config.get("api_url"),
            model_options=model_options,
            auth_config=auth_config,
            tests_dir=tests_dir,
            mode=mode,
            run_id=run_id,
            quiet=config.get("quiet", False),
        )

        Orchestrator(build_stages(mode)).run(ctx)

        if ctx.errors:
            for error in ctx.errors:
                print(error, file=sys.stderr)

        return ctx.exit_code

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Configuration error: {e}", file=sys.stderr)
        return ExitCode.USAGE


if __name__ == "__main__":
    sys.exit(main())

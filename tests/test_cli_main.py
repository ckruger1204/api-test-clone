import importlib
from pathlib import Path

from api_test_agent.exit_codes import ExitCode

# `api_test_agent/cli/__init__.py` fait `from .main import main`, ce qui
# réécrit l'attribut `main` du package cli (nom identique à son sous-module
# `main`) pour pointer vers la FONCTION plutôt que le module — un
# `import api_test_agent.cli.main as cli_main` suivrait alors cet attribut et
# récupérerait la fonction, pas le module. importlib contourne le problème en
# passant par sys.modules.
cli_main = importlib.import_module("api_test_agent.cli.main")


class _FakeOrchestrator:
    """Capture le contexte et les stages sans jamais les exécuter — ces tests
    portent sur la résolution de config (mode, tests_dir, validation), pas sur
    le pipeline lui-même (déjà couvert par tests/test_pipeline_defaults.py et
    les tests dédiés à chaque stage)."""

    captured_ctx = None
    captured_stages = None

    def __init__(self, stages):
        _FakeOrchestrator.captured_stages = stages

    def run(self, ctx):
        _FakeOrchestrator.captured_ctx = ctx
        ctx.exit_code = ExitCode.OK
        return ctx


def _patch_config(monkeypatch, config: dict, project_root: Path):
    monkeypatch.setattr(cli_main, "load_config", lambda: (config, project_root))
    monkeypatch.setattr(cli_main, "Orchestrator", _FakeOrchestrator)


def test_main_rejects_unknown_mode(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "delete-everything"}, tmp_path)

    assert cli_main.main() == ExitCode.USAGE


def test_main_requires_openapi_spec_path_in_generate_mode(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "generate"}, tmp_path)

    assert cli_main.main() == ExitCode.USAGE


def test_main_does_not_require_openapi_spec_path_in_load_mode(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "load"}, tmp_path)

    assert cli_main.main() == ExitCode.OK
    assert _FakeOrchestrator.captured_ctx.spec_path is None
    assert _FakeOrchestrator.captured_ctx.mode == "load"


def test_main_resolves_default_tests_dir_under_project_root(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "view"}, tmp_path)

    cli_main.main()

    assert _FakeOrchestrator.captured_ctx.tests_dir == tmp_path / "generated_tests"


def test_main_honors_custom_tests_dir(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "view", "tests_dir": "my_suite"}, tmp_path)

    cli_main.main()

    assert _FakeOrchestrator.captured_ctx.tests_dir == tmp_path / "my_suite"


def test_main_passes_run_id_through_to_context(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "view", "run_id": "20260115-142301"}, tmp_path)

    cli_main.main()

    assert _FakeOrchestrator.captured_ctx.run_id == "20260115-142301"


def test_main_rejects_non_string_run_id(monkeypatch, tmp_path: Path):
    _patch_config(monkeypatch, {"mode": "view", "run_id": 123}, tmp_path)

    assert cli_main.main() == ExitCode.USAGE


def test_main_generate_mode_resolves_absolute_spec_path(monkeypatch, tmp_path: Path):
    config = {
        "mode": "generate",
        "openapi_spec_path": "api/openapi.yaml",
        "model_options": {"base_url": "http://localhost:11434", "api_key": "x"},
    }
    _patch_config(monkeypatch, config, tmp_path)

    cli_main.main()

    assert _FakeOrchestrator.captured_ctx.spec_path == tmp_path / "api" / "openapi.yaml"

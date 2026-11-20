from pathlib import Path

import pytest

from api_test_agent.generation.load_stage import LoadStage
from api_test_agent.generation.scenarios import Scenario
from api_test_agent.generation.storage import save_scenarios
from api_test_agent.pipeline.context import RunContext

SCENARIO = Scenario(
    operation_id="getArticle",
    scenario="nominal",
    method="GET",
    path="/api/articles/1",
    body=None,
    expected_status=[200],
)


def test_load_stage_populates_context_from_saved_suite(tmp_path: Path):
    save_scenarios(tmp_path, [SCENARIO], {"base_url": "http://localhost:5000", "endpoints_total": 1})

    ctx = RunContext(tests_dir=tmp_path, mode="load")
    LoadStage("load").run(ctx)

    assert ctx.generated_tests == [tmp_path / "test_generated_api.py"]
    assert ctx.scenarios == [SCENARIO]
    assert ctx.generation_stats["source"] == "loaded"
    assert ctx.generation_stats["endpoints_total"] == 1


def test_load_stage_raises_when_tests_dir_missing():
    ctx = RunContext(tests_dir=None, mode="load")
    with pytest.raises(ValueError, match="tests_dir"):
        LoadStage("load").run(ctx)


def test_load_stage_raises_in_load_mode_when_suite_absent(tmp_path: Path):
    ctx = RunContext(tests_dir=tmp_path, mode="load")
    with pytest.raises(FileNotFoundError):
        LoadStage("load").run(ctx)


def test_load_stage_is_tolerant_in_view_mode_when_suite_absent(tmp_path: Path):
    ctx = RunContext(tests_dir=tmp_path, mode="view")
    LoadStage("load").run(ctx)  # ne doit pas lever

    assert ctx.scenarios is None

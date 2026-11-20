import json
from pathlib import Path

import pytest

from api_test_agent.execution.view_stage import ViewStage
from api_test_agent.pipeline.context import RunContext


def _write_run(tests_dir: Path, run_id: str, outcome: str = "success") -> Path:
    run_dir = tests_dir / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "results.json").write_text(
        json.dumps({"outcome": outcome, "exit_code": 0, "message": None, "tests": [{"name": "test_x"}]}),
        encoding="utf-8",
    )
    return run_dir


def test_view_stage_loads_latest_run_by_default(tmp_path: Path):
    _write_run(tmp_path, "20260101-000000")
    latest = _write_run(tmp_path, "20260102-000000")

    ctx = RunContext(tests_dir=tmp_path, mode="view")
    ViewStage("view").run(ctx)

    assert ctx.run_dir == latest
    assert ctx.results == [{"name": "test_x"}]
    assert ctx.execution_stats["outcome"] == "success"
    assert ctx.execution_stats["viewed"] is True


def test_view_stage_loads_specific_run_id(tmp_path: Path):
    older = _write_run(tmp_path, "20260101-000000")
    _write_run(tmp_path, "20260102-000000")

    ctx = RunContext(tests_dir=tmp_path, mode="view", run_id="20260101-000000")
    ViewStage("view").run(ctx)

    assert ctx.run_dir == older


def test_view_stage_raises_when_no_run_exists(tmp_path: Path):
    ctx = RunContext(tests_dir=tmp_path, mode="view")
    with pytest.raises(ValueError, match="Aucun run"):
        ViewStage("view").run(ctx)


def test_view_stage_raises_when_requested_run_id_unknown(tmp_path: Path):
    _write_run(tmp_path, "20260101-000000")

    ctx = RunContext(tests_dir=tmp_path, mode="view", run_id="does-not-exist")
    with pytest.raises(ValueError, match="does-not-exist"):
        ViewStage("view").run(ctx)


def test_view_stage_raises_when_tests_dir_missing():
    ctx = RunContext(tests_dir=None, mode="view")
    with pytest.raises(ValueError, match="tests_dir"):
        ViewStage("view").run(ctx)

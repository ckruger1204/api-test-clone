from pathlib import Path

from api_test_agent.execution.run_history import (
    find_run,
    latest_run,
    list_runs,
    new_run_dir,
)


def test_new_run_dir_creates_unique_directory_under_runs(tmp_path: Path):
    run_dir = new_run_dir(tmp_path)

    assert run_dir.exists()
    assert run_dir.parent == tmp_path / "runs"


def test_new_run_dir_avoids_collision_within_same_second(tmp_path: Path, monkeypatch):
    import api_test_agent.execution.run_history as run_history_module

    class _FixedDatetime:
        @staticmethod
        def now(tz=None):
            import datetime as real_datetime

            return real_datetime.datetime(2026, 1, 15, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(run_history_module, "datetime", _FixedDatetime)

    first = new_run_dir(tmp_path)
    second = new_run_dir(tmp_path)

    assert first != second
    assert first.exists() and second.exists()


def test_list_runs_sorted_most_recent_first(tmp_path: Path):
    (tmp_path / "runs" / "20260101-000000").mkdir(parents=True)
    (tmp_path / "runs" / "20260103-000000").mkdir(parents=True)
    (tmp_path / "runs" / "20260102-000000").mkdir(parents=True)

    runs = list_runs(tmp_path)

    assert [p.name for p in runs] == ["20260103-000000", "20260102-000000", "20260101-000000"]


def test_list_runs_empty_when_no_runs_directory(tmp_path: Path):
    assert list_runs(tmp_path) == []


def test_latest_run_returns_none_when_empty(tmp_path: Path):
    assert latest_run(tmp_path) is None


def test_latest_run_returns_most_recent(tmp_path: Path):
    (tmp_path / "runs" / "20260101-000000").mkdir(parents=True)
    newest = tmp_path / "runs" / "20260105-000000"
    newest.mkdir(parents=True)

    assert latest_run(tmp_path) == newest


def test_find_run_returns_none_for_unknown_id(tmp_path: Path):
    assert find_run(tmp_path, "does-not-exist") is None


def test_find_run_returns_path_for_known_id(tmp_path: Path):
    run_dir = tmp_path / "runs" / "20260101-000000"
    run_dir.mkdir(parents=True)

    assert find_run(tmp_path, "20260101-000000") == run_dir

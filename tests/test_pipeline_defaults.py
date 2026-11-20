import pytest

from api_test_agent.pipeline.defaults import build_stages, default_stages


def test_build_stages_generate_matches_full_pipeline():
    names = [stage.name for stage in build_stages("generate")]
    assert names == ["discovery", "analysis", "generation", "execution", "reporting"]


def test_build_stages_load_skips_discovery_analysis_generation():
    names = [stage.name for stage in build_stages("load")]
    assert names == ["load", "execution", "reporting"]


def test_build_stages_view_skips_execution():
    names = [stage.name for stage in build_stages("view")]
    assert names == ["load", "view", "reporting"]


def test_build_stages_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Mode inconnu"):
        build_stages("delete-everything")


def test_default_stages_is_equivalent_to_generate_mode():
    assert [s.name for s in default_stages()] == [s.name for s in build_stages("generate")]

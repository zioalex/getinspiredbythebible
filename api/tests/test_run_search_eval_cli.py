"""Unit tests for search-eval CLI argument validation (BITB-104)."""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_search_eval.py"
_SPEC = importlib.util.spec_from_file_location("run_search_eval", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
run_search_eval = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_search_eval)


def _parse(raw):
    return run_search_eval._parse_topic_boost_factors(
        raw,
        ["topic_boosted"],
        {"topic_boosted": type("Config", (), {"use_topic_boost": True})()},
    )


def test_topic_boost_factor_accepts_distinct_finite_values():
    assert _parse("0,0.2,1.5") == ([0.0, 0.2, 1.5], None)


@pytest.mark.parametrize("raw", ["", ",", " , "])
def test_topic_boost_factor_rejects_an_empty_sweep(raw):
    factors, error = _parse(raw)
    assert factors is None
    assert "at least one" in error


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
def test_topic_boost_factor_rejects_non_finite_values(raw):
    factors, error = _parse(raw)
    assert factors is None
    assert "finite" in error


@pytest.mark.parametrize("raw", ["0.2,0.2", "0.1,1e-1"])
def test_topic_boost_factor_rejects_duplicate_values(raw):
    factors, error = _parse(raw)
    assert factors is None
    assert "duplicates" in error

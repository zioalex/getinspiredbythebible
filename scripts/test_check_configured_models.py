"""Tests for scripts/check_configured_models.py (BITB-304). HTTP is always mocked."""

import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import check_configured_models as ccm  # noqa: E402

OPENROUTER_REFS, CLAUDE_REFS = ccm.collect_models()
OPENROUTER_IDS = {m for m, _ in OPENROUTER_REFS}
CLAUDE_ID = CLAUDE_REFS[0][0]


def test_collect_models_reads_every_source():
    sources = {s for _, s in OPENROUTER_REFS}
    assert any("openrouter_model" in s and "config.py" in s for s in sources)
    assert any("openrouter_fallback_models" in s and "config.py" in s for s in sources)
    assert any("llama_guard.py MODEL" in s for s in sources)
    assert any("SECONDARY_MODEL" in s for s in sources)
    assert any("variables.tf" in s for s in sources)
    assert CLAUDE_REFS and CLAUDE_REFS[0][1].endswith("DEFAULT_CLAUDE_MODEL")


def test_claude_default_is_not_an_ollama_name():
    assert CLAUDE_ID.startswith("claude-")


@pytest.fixture
def patch_http(monkeypatch):
    def _install(openrouter_ids=None, anthropic_ids=None, error=None):
        calls = {"anthropic": 0}

        def fake_openrouter():
            if error:
                raise error
            return set(openrouter_ids)

        def fake_anthropic(key):
            calls["anthropic"] += 1
            return set(anthropic_ids)

        monkeypatch.setattr(ccm, "fetch_openrouter_ids", fake_openrouter)
        monkeypatch.setattr(ccm, "fetch_anthropic_ids", fake_anthropic)
        return calls

    return _install


def test_all_present_exits_0(patch_http, capsys):
    patch_http(OPENROUTER_IDS, {CLAUDE_ID})
    assert ccm.run(env={"ANTHROPIC_API_KEY": "k"}) == 0
    assert "OK" in capsys.readouterr().out


def test_one_missing_exits_1_and_names_it(patch_http, capsys):
    gone = "google/gemma-4-31b-it"
    patch_http(OPENROUTER_IDS - {gone}, {CLAUDE_ID})
    assert ccm.run(env={"ANTHROPIC_API_KEY": "k"}) == 1
    err = capsys.readouterr().err
    assert f"MISSING: {gone}" in err
    assert "api/config.py" in err


def test_missing_claude_default_exits_1(patch_http, capsys):
    patch_http(OPENROUTER_IDS, set())
    assert ccm.run(env={"ANTHROPIC_API_KEY": "k"}) == 1
    assert f"MISSING: {CLAUDE_ID}" in capsys.readouterr().err


def test_network_error_exits_2_not_1(patch_http, capsys):
    patch_http(error=ccm.ProbeError("boom"))
    assert ccm.run(env={}) == 2
    assert "MISSING" not in capsys.readouterr().err


def test_anthropic_skipped_without_key(patch_http, capsys):
    calls = patch_http(OPENROUTER_IDS, set())
    assert ccm.run(env={}) == 0
    assert calls["anthropic"] == 0
    assert "skipped" in capsys.readouterr().out


def test_openrouter_prefix_is_tolerated():
    refs = [("openrouter/vendor/model", "x")]
    assert ccm.find_missing(refs, {"vendor/model"}, openrouter=True) == []
    assert ccm.find_missing(refs, {"other"}, openrouter=True) == refs


def test_http_error_becomes_probe_error(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(ccm.urllib.request, "urlopen", boom)
    with pytest.raises(ccm.ProbeError):
        ccm._get_json("https://example.invalid")


def test_anthropic_pagination(monkeypatch):
    pages = iter(
        [
            {"data": [{"id": "a"}], "has_more": True, "last_id": "a"},
            {"data": [{"id": "b"}], "has_more": False, "last_id": "b"},
        ]
    )
    urls = []

    def fake_get(url, headers=None):
        urls.append(url)
        assert headers["x-api-key"] == "k"
        assert headers["anthropic-version"] == "2023-06-01"
        return next(pages)

    monkeypatch.setattr(ccm, "_get_json", fake_get)
    assert ccm.fetch_anthropic_ids("k") == {"a", "b"}
    assert "after_id=a" in urls[1]

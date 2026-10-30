"""Tests for scripts/check_crisis_resources.py (BITB-255)."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import check_crisis_resources as cc  # noqa: E402

TODAY = date(2026, 10, 29)


def _registry(verified_on="2026-10-01", verified_by="tester", source="https://a.example"):
    entry = {"number": "112", "source_url": source, "verified_on": verified_on}
    entry["verified_by"] = verified_by
    line = {"id": "x-1", "source_url": "https://b.example", "verified_on": verified_on}
    line["verified_by"] = verified_by
    return {"emergency": {"IT": entry}, "lines": {"IT": [line]}}


def test_fresh_entries_pass():
    entries = cc.collect_entries(_registry())
    assert cc.check_verification(entries, TODAY) == []


def test_null_verified_on_fails_and_names_the_entry():
    problems = cc.check_verification(cc.collect_entries(_registry(None, None)), TODAY)
    assert len(problems) == 2
    assert "emergency[IT]" in problems[0] and "never verified" in problems[0]
    assert "lines[IT][x-1]" in problems[1]


def test_age_boundary_is_180_days():
    ok = cc.check_verification(cc.collect_entries(_registry("2026-05-02")), TODAY)  # 180 days
    old = cc.check_verification(cc.collect_entries(_registry("2026-05-01")), TODAY)  # 181 days
    assert ok == []
    assert len(old) == 2 and "181 days" in old[0]


def test_custom_max_age():
    entries = cc.collect_entries(_registry("2026-09-01"))
    assert cc.check_verification(entries, TODAY, max_age_days=30)


@pytest.mark.parametrize("bad", ["yesterday", "2026-13-40"])
def test_malformed_date_fails(bad):
    problems = cc.check_verification(cc.collect_entries(_registry(bad)), TODAY)
    assert problems and "not an ISO date" in problems[0]


def test_future_date_fails():
    problems = cc.check_verification(cc.collect_entries(_registry("2027-01-01")), TODAY)
    assert problems and "future" in problems[0]


def test_missing_verifier_fails():
    problems = cc.check_verification(cc.collect_entries(_registry(verified_by=None)), TODAY)
    assert problems and "verified_by" in problems[0]


def _fetcher(table):
    def fetch(url, method, timeout):
        outcome = table[(url, method)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return fetch


def test_url_ok_on_head():
    alive, detail = cc.url_is_alive("https://a", 1, _fetcher({("https://a", "HEAD"): 200}))
    assert alive and detail == "HEAD 200"


def test_url_redirect_counts_as_alive():
    alive, _ = cc.url_is_alive("https://a", 1, _fetcher({("https://a", "HEAD"): 301}))
    assert alive


def test_head_405_falls_back_to_get():
    fetch = _fetcher({("https://a", "HEAD"): 405, ("https://a", "GET"): 200})
    assert cc.url_is_alive("https://a", 1, fetch) == (True, "GET 200")


def test_head_network_error_falls_back_to_get():
    fetch = _fetcher({("https://a", "HEAD"): OSError("boom"), ("https://a", "GET"): 200})
    assert cc.url_is_alive("https://a", 1, fetch)[0] is True


def test_dead_url_fails_on_both():
    fetch = _fetcher({("https://a", "HEAD"): 404, ("https://a", "GET"): 404})
    alive, detail = cc.url_is_alive("https://a", 1, fetch)
    assert not alive and detail == "GET 404"


def test_check_urls_reports_each_dead_url_once_with_all_users():
    registry = _registry(source="https://dead.example")
    registry["lines"]["IT"][0]["source_url"] = "https://dead.example"
    fetch = _fetcher({("https://dead.example", "HEAD"): 500, ("https://dead.example", "GET"): 503})
    problems = cc.check_urls(cc.collect_entries(registry), fetch=fetch)
    assert len(problems) == 1
    assert "emergency[IT]" in problems[0] and "lines[IT][x-1]" in problems[0]


def test_missing_source_url_is_a_problem():
    registry = _registry()
    del registry["emergency"]["IT"]["source_url"]
    problems = cc.check_urls(cc.collect_entries(registry), fetch=_fetcher({}))
    assert any("emergency[IT]: missing source_url" in p for p in problems)


def test_main_exit_codes(tmp_path, capsys):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(_registry(None, None)), encoding="utf-8")
    assert cc.main(["--registry", str(path), "--skip-urls", "--today", "2026-10-29"]) == 1
    assert "FAILED" in capsys.readouterr().out
    path.write_text(json.dumps(_registry()), encoding="utf-8")
    assert cc.main(["--registry", str(path), "--skip-urls", "--today", "2026-10-29"]) == 0


def test_shipped_registry_loads_and_every_entry_is_collected():
    registry = json.loads(cc.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    entries = cc.collect_entries(registry)
    n_lines = sum(len(v) for v in registry["lines"].values())
    assert len(entries) == len(registry["emergency"]) + n_lines
    # Dates-only run must not raise on the shipped file (it is red until verified).
    assert isinstance(cc.check_verification(entries, TODAY), list)

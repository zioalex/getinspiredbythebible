"""BITB-372: cost guard on alert and web-test cadence.

Nov 2026 Cost Management showed each PT5M log-search rule billing ~$1.38/month versus
~$0.46 at PT15M, and Standard Web Test Execution ~$29/month for 2 tests x 3 geos every
5 minutes. These tests keep the cadence deliberate: only two rules may evaluate every 5
minutes and a single preflight web test runs from one location every 15 minutes.
"""

import re
from pathlib import Path

import pytest

from tests.test_monitoring_alert_lookback import _RULE_TYPE, _rule_blocks
from tests.test_webtests_enabled_guard import _WEBTEST_TYPE, _resource_blocks

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MONITORING_TF = _REPO_ROOT / "deployment" / "monitoring.tf"
_MAIN_TF = _REPO_ROOT / "deployment" / "main.tf"
_MODULE = _REPO_ROOT / "deployment"

_PT5M_ALLOWED = {"rate_limiter_fail_closed", "backend_asgi_exceptions"}

_RULES = _rule_blocks(_MONITORING_TF.read_text())
_WEBTESTS = _resource_blocks(_MAIN_TF.read_text(), _WEBTEST_TYPE)


def test_only_security_and_crash_rules_evaluate_every_5_minutes() -> None:
    pt5m = {
        name
        for name, body in _RULES.items()
        if re.search(r'^\s*evaluation_frequency\s*=\s*"PT5M"', body, re.MULTILINE)
    }
    assert pt5m == _PT5M_ALLOWED, (
        f"{_RULE_TYPE} rules at PT5M must be exactly {sorted(_PT5M_ALLOWED)}; got "
        f"{sorted(pt5m)}. Each PT5M rule costs ~3x a PT15M one (BITB-372); use PT15M "
        "unless there is a real 5-minute paging need."
    )


def test_5xx_rule_uses_sliding_zero_filled_series() -> None:
    """15-minute evaluations over a 30-minute window keep sliding sustained-breach semantics."""
    body = _RULES["backend_5xx_rate"]
    assert re.search(r'^\s*evaluation_frequency\s*=\s*"PT15M"', body, re.MULTILINE)
    assert re.search(r'^\s*window_duration\s*=\s*"PT45M"', body, re.MULTILINE)
    assert re.search(r"number_of_evaluation_periods\s*=\s*1\b", body)
    assert "make-series" in body and "default=0" in body  # empty bins count as 0, not missing
    assert "prev(total, 1)" in body or "prev1" in body
    assert "prev(" in body
    assert "AlertSummary" in body


def test_only_preflight_webtest_exists() -> None:
    assert set(_WEBTESTS) == {"backend_preflight"}, (
        "Standard web tests bill per location per run (~$29/month in Nov 2026, BITB-372); "
        "do not add another without a cost review"
    )


def test_preflight_webtest_is_one_location_every_15_minutes() -> None:
    body = _WEBTESTS["backend_preflight"]
    assert re.search(r"^\s*frequency\s*=\s*900\b", body, re.MULTILINE)
    geo = re.search(r"geo_locations\s*=\s*\[(.*?)\]", body, re.DOTALL)
    assert geo, "geo_locations not set"
    assert len(re.findall(r'"[^"]+"', geo.group(1))) == 1


def test_preflight_alert_matches_single_location() -> None:
    text = _MONITORING_TF.read_text()
    match = re.search(
        r'resource "azurerm_monitor_metric_alert" "backend_preflight_availability" \{(.*?)\n\}',
        text,
        re.DOTALL,
    )
    assert match
    body = match.group(1)
    assert re.search(r"failed_location_count\s*=\s*1\b", body)
    assert 'window_size = "PT30M"' in body


_FILE_INCLUDE = re.compile(r'\$\{file\("\$\{path\.module\}/([^"]+)"\)\}')
_AGO = re.compile(r"\bago\((\d+)([mhd])\)")
_UNITS = {"m": 1, "h": 60, "d": 1440}


def _resolved(body: str) -> str:
    """Expand ${file(...)} includes and drop // comments (they may mention ago(N))."""
    text = _FILE_INCLUDE.sub(lambda m: (_MODULE / m.group(1)).read_text(), body)
    return re.sub(r"//[^\n]*", "", text)


def _minutes(value: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", value)
    assert m
    d, h, mi = (int(g or 0) for g in m.groups())
    return d * 1440 + h * 60 + mi


@pytest.mark.parametrize("name", sorted(_RULES))
def test_query_look_back_matches_window_duration(name: str) -> None:
    """The longest ago(N) in the fully resolved query (shared .kql includes expanded) must equal
    window_duration. A shorter one silently blinds the rule to part of its window; this is how
    backend-error-filter.kql's hard-coded ago(10m) capped the PT15M backend_errors rule
    (BITB-372). Rules with no ago() rely on window_duration alone."""
    body = _RULES[name]
    agos = [int(n) * _UNITS[u] for n, u in _AGO.findall(_resolved(body))]
    if not agos:
        pytest.skip("no ago() in query; window_duration governs")
    window = _minutes(
        re.search(r'^\s*window_duration\s*=\s*"([^"]+)"', body, re.MULTILINE).group(1)
    )
    assert (
        max(agos) == window
    ), f"{name}: longest ago() is {max(agos)}m but window_duration is {window}m"


def test_shared_error_filter_has_no_time_window() -> None:
    kql = (_MODULE / "azure-monitor" / "queries" / "backend-error-filter.kql").read_text()
    code = "\n".join(line for line in kql.splitlines() if not line.lstrip().startswith("//"))
    assert "ago(" not in code, "each consumer of the shared filter must set its own window"
    workflow = (_REPO_ROOT / ".github" / "workflows" / "prod-monitor.yml").read_text()
    assert "TimeGenerated > ago(10m)" in workflow  # log-scan keeps its 10-minute window

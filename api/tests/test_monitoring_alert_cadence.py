"""BITB-370: cost guard on alert and web-test cadence.

Nov 2026 Cost Management showed each PT5M log-search rule billing ~$1.38/month versus
~$0.46 at PT15M, and Standard Web Test Execution ~$29/month for 2 tests x 3 geos every
5 minutes. These tests keep the cadence deliberate: only two rules may evaluate every 5
minutes and a single preflight web test runs from one location every 15 minutes.
"""

import re
from pathlib import Path

from tests.test_monitoring_alert_lookback import _RULE_TYPE, _rule_blocks
from tests.test_webtests_enabled_guard import _WEBTEST_TYPE, _resource_blocks

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MONITORING_TF = _REPO_ROOT / "deployment" / "monitoring.tf"
_MAIN_TF = _REPO_ROOT / "deployment" / "main.tf"

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
        f"{sorted(pt5m)}. Each PT5M rule costs ~3x a PT15M one (BITB-370); use PT15M "
        "unless there is a real 5-minute paging need."
    )


def test_5xx_rule_is_single_evaluation_sustained_bins() -> None:
    body = _RULES["backend_5xx_rate"]
    assert 'window_duration      = "PT15M"' in body
    assert re.search(r"number_of_evaluation_periods\s*=\s*1\b", body)
    assert "breached_bins >= 3" in body


def test_only_preflight_webtest_exists() -> None:
    assert set(_WEBTESTS) == {"backend_preflight"}, (
        "Standard web tests bill per location per run (~$29/month in Nov 2026, BITB-370); "
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
    assert 'window_size = "PT15M"' in body

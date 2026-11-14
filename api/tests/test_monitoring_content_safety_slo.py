"""Guards the BITB-290 keyword-fallback-share SLO: denominator metric, burn-rate alerts, workbook.

`content_safety_fallback_rate` (any sustained fallback pages) was replaced by two multi-window
burn-rate rules over fallback_total / checks_total. `terraform validate` cannot see KQL or
workbook JSON, so these tests pin the contract textually.
"""

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from tests.test_monitoring_alert_lookback import _iso8601_duration, _rule_blocks

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MONITORING_TF = _REPO_ROOT / "deployment" / "monitoring.tf"
_VARIABLES_TF = _REPO_ROOT / "deployment" / "variables.tf"
_WORKBOOK = _REPO_ROOT / "deployment" / "azure-monitor" / "workbook-performance-dashboard.json"
_METRICS_PY = _REPO_ROOT / "api" / "utils" / "metrics.py"

_RULES = _rule_blocks(_MONITORING_TF.read_text())

# name -> (severity, evaluation_frequency, long window, short window, burn factor)
_BURN_RULES = {
    "content_safety_fallback_burn_fast": (2, "PT5M", "1h", "5m", "14.4"),
    "content_safety_fallback_burn_slow": (3, "PT15M", "6h", "30m", "6"),
}


def _attr(body: str, key: str) -> str:
    match = re.search(rf'^\s*{key}\s*=\s*"?([^"\n]+)"?\s*$', body, re.MULTILINE)
    assert match, f"{key} not set"
    return match.group(1)


def test_any_fallback_rule_removed_and_burn_rules_exist() -> None:
    assert "content_safety_fallback_rate" not in _RULES
    for name in _BURN_RULES:
        assert name in _RULES


@pytest.mark.parametrize("name", sorted(_BURN_RULES))
def test_burn_rule_query_uses_both_metrics_and_slo_variable(name: str) -> None:
    body = _RULES[name]
    assert '"content_safety.fallback_total"' in body
    assert '"content_safety.checks_total"' in body
    assert "${var.content_safety_fallback_slo_target}" in body
    assert "todouble(" in body  # real-valued division, not integer division


@pytest.mark.parametrize("name", sorted(_BURN_RULES))
def test_burn_rule_windows_severity_and_burn(name: str) -> None:
    severity, freq, long_w, short_w, burn = _BURN_RULES[name]
    body = _RULES[name]
    assert int(_attr(body, "severity")) == severity
    assert _attr(body, "evaluation_frequency") == freq
    assert f"let burn = {burn};" in body
    assert f"ago({long_w})" in body and f"ago({short_w})" in body
    # window_duration equals the long window (and stays inside the 48h look-back cap)
    long_td = {"1h": timedelta(hours=1), "6h": timedelta(hours=6)}[long_w]
    assert _iso8601_duration(_attr(body, "window_duration")) == long_td


def test_burn_rule_description_documents_replacement() -> None:
    for name in _BURN_RULES:
        desc = _attr(_RULES[name], "description")
        assert "BITB-223" in desc and "BITB-290" in desc
        assert "docs/HOW-TO-ENABLE-CONTENT-SAFETY.md" in desc


def test_slo_variable_declared_with_default() -> None:
    text = _VARIABLES_TF.read_text()
    block = re.search(r'variable "content_safety_fallback_slo_target" \{(.*?)\n\}', text, re.DOTALL)
    assert block, "variable content_safety_fallback_slo_target missing"
    assert re.search(r"default\s*=\s*0\.005\b", block.group(1))
    assert "validation" in block.group(1)


def test_checks_counter_defined_in_metrics() -> None:
    text = _METRICS_PY.read_text()
    assert 'name="content_safety.checks_total"' in text
    assert "content_safety_checks_counter = meter.create_counter(" in text


def _workbook_queries() -> list[str]:
    queries: list[str] = []

    def walk(items: list) -> None:
        for item in items:
            content = item.get("content", {})
            if item.get("type") == 3:
                queries.append(content["query"])
            if item.get("type") == 12:
                walk(content.get("items", []))

    walk(json.loads(_WORKBOOK.read_text())["items"])
    return queries


def test_workbook_has_share_tile() -> None:
    assert any(
        "content_safety.checks_total" in q and "content_safety.fallback_total" in q
        for q in _workbook_queries()
    )


def test_workbook_has_fallback_breakdown_tile() -> None:
    assert any(
        "content_safety.fallback_total" in q
        and all(
            f'customDimensions["{d}"]' in q
            for d in ("stage", "reason", "failure_class", "failover")
        )
        for q in _workbook_queries()
    )


def test_workbook_has_failover_outcome_tile() -> None:
    assert any(
        "content_safety.failover_total" in q and 'customDimensions["outcome"]' in q
        for q in _workbook_queries()
    )

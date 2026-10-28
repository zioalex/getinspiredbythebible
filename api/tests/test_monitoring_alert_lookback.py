"""Guards Azure's 48h look-back cap on scheduled-query alert rules.

BITB-223 demoted `verse_grounding_paraphrase_brackets` to a P1D window but kept its
2-of-3 `failing_periods` gate. Azure computes look-back as
`window_duration x number_of_evaluation_periods` (24h x 3 = 72h) and rejects anything
over 48h with `400 InvalidRequestContent: Query look back cannot exceed 48 hours`.
`terraform validate`/`plan` can't see this — it only failed at `apply` on main. These
tests parse every `azurerm_monitor_scheduled_query_rules_alert_v2` block in
`deployment/monitoring.tf` and assert the product stays within the cap.
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MONITORING_TF = _REPO_ROOT / "deployment" / "monitoring.tf"

_MAX_LOOKBACK = timedelta(hours=48)
_RULE_TYPE = "azurerm_monitor_scheduled_query_rules_alert_v2"


def _iso8601_duration(value: str) -> timedelta:
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", value)
    assert match and value not in ("P", "PT"), f"unsupported ISO 8601 duration: {value!r}"
    days, hours, minutes = (int(g or 0) for g in match.groups())
    return timedelta(days=days, hours=hours, minutes=minutes)


def _rule_blocks(text: str) -> dict[str, str]:
    """Return {resource name: block body} for every scheduled-query rule."""
    blocks: dict[str, str] = {}
    for header in re.finditer(rf'^resource\s+"{_RULE_TYPE}"\s+"(\w+)"\s*\{{', text, re.MULTILINE):
        depth, pos = 1, header.end()
        while depth:
            char = text[pos]
            depth += {"{": 1, "}": -1}.get(char, 0)
            pos += 1
        blocks[header.group(1)] = text[header.end() : pos - 1]
    return blocks


def _lookback(body: str) -> timedelta:
    window = re.search(r'^\s*window_duration\s*=\s*"([^"]+)"', body, re.MULTILINE)
    assert window, "window_duration not set"
    periods = re.search(r"^\s*number_of_evaluation_periods\s*=\s*(\d+)", body, re.MULTILINE)
    # Without a failing_periods block Azure evaluates a single period.
    return _iso8601_duration(window.group(1)) * (int(periods.group(1)) if periods else 1)


_RULES = _rule_blocks(_MONITORING_TF.read_text())


def test_rules_are_found() -> None:
    assert "verse_grounding_paraphrase_brackets" in _RULES
    assert len(_RULES) >= 10


@pytest.mark.parametrize("name", sorted(_RULES))
def test_lookback_within_azure_cap(name: str) -> None:
    lookback = _lookback(_RULES[name])
    assert lookback <= _MAX_LOOKBACK, (
        f"{name}: window_duration x number_of_evaluation_periods = {lookback} exceeds "
        f"Azure's {_MAX_LOOKBACK} look-back cap (apply fails with 400 InvalidRequestContent)"
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('window_duration = "P1D"\nnumber_of_evaluation_periods = 3', timedelta(hours=72)),
        ('window_duration = "P1D"\nnumber_of_evaluation_periods = 2', timedelta(hours=48)),
        ('window_duration = "PT5M"\nnumber_of_evaluation_periods = 6', timedelta(minutes=30)),
        ('window_duration = "PT1H"', timedelta(hours=1)),
    ],
)
def test_lookback_computation(body: str, expected: timedelta) -> None:
    assert _lookback(body) == expected

"""BITB-233: PostgreSQL server-log parameters are an explicit, recorded decision.

Option A: log_connections and log_checkpoints are off, log_min_duration_statement is kept,
and no diagnostic setting ships the server logs anywhere.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAIN_TF = _REPO_ROOT / "deployment" / "main.tf"
_README = _REPO_ROOT / "deployment" / "README.md"
_CONFIG_TYPE = "azurerm_postgresql_flexible_server_configuration"


def _resource_blocks(text: str, resource_type: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for header in re.finditer(
        rf'^resource\s+"{resource_type}"\s+"(\w+)"\s*\{{', text, re.MULTILINE
    ):
        depth, pos = 1, header.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[pos], 0)
            pos += 1
        blocks[header.group(1)] = text[header.end() : pos - 1]
    return blocks


def _value(resource: str) -> str:
    blocks = _resource_blocks(_MAIN_TF.read_text(), _CONFIG_TYPE)
    assert resource in blocks, f"{_CONFIG_TYPE}.{resource} missing from main.tf (BITB-233)"
    match = re.search(r'^\s*value\s*=\s*"([^"]*)"', blocks[resource], re.MULTILINE)
    assert match, f"{resource} has no literal value"
    return match.group(1)


def test_log_connections_off():
    assert _value("log_connections") == "off"


def test_log_checkpoints_off():
    assert _value("log_checkpoints") == "off"


def test_slow_query_log_kept_with_positive_threshold():
    value = _value("log_min_duration_statement")
    assert value.isdigit() and int(value) > 0


def test_no_postgres_diagnostic_setting():
    offenders = []
    for tf in sorted(_MAIN_TF.parent.glob("*.tf")):
        blocks = _resource_blocks(tf.read_text(), "azurerm_monitor_diagnostic_setting")
        offenders += [f"{tf.name}:{n}" for n, b in blocks.items() if "postgresql_flexible_server" in b]
    assert not offenders, (
        f"Diagnostic setting(s) {offenders} target the PostgreSQL server. That is BITB-233 "
        "Option B: update this test deliberately, together with a written cost estimate."
    )


def test_readme_records_decision():
    text = _README.read_text()
    assert "BITB-233" in text
    for param in ("log_connections", "log_checkpoints", "log_min_duration_statement"):
        assert param in text, f"deployment/README.md must record the {param} decision (BITB-233)"

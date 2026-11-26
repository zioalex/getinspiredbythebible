"""BITB-232: PostgreSQL storage auto-grow early warning + provisioned-size tripwire."""

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "monitor" / "check_db_storage_size.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "prod-deploy-drift.yml"
_MONITORING_TF = _REPO_ROOT / "deployment" / "monitoring.tf"
_ALERT_TYPE = "azurerm_monitor_metric_alert"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_db_storage_size", _SCRIPT)
    assert spec and spec.loader, f"cannot load {_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_script()


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


_BLOCKS = _resource_blocks(_MONITORING_TF.read_text(), _ALERT_TYPE)
_WORKFLOW_YAML = yaml.safe_load(_WORKFLOW.read_text())


def _attr(body: str, name: str) -> str:
    match = re.search(rf"^\s*{name}\s*=\s*(.+?)\s*$", body, re.MULTILINE)
    assert match, f"{name} not found"
    return match.group(1)


# --- monitoring.tf: pre-grow alert -------------------------------------------------------


def test_pregrow_alert_defined() -> None:
    assert "db_storage_pregrow" in _BLOCKS and "db_storage" in _BLOCKS


def test_pregrow_alert_criteria() -> None:
    body = _BLOCKS["db_storage_pregrow"]
    assert _attr(body, "metric_name") == '"storage_percent"'
    assert _attr(body, "aggregation") == '"Average"'
    assert _attr(body, "operator") == '"GreaterThan"'
    assert _attr(body, "window_size") == '"PT15M"'
    assert _attr(body, "frequency").startswith('"PT15M"')
    assert _attr(body, "severity") == "3"
    assert _attr(body, "name") == '"${local.name_prefix}-db-storage-pregrow"'


def test_pregrow_threshold_between_p95_and_full_alert() -> None:
    pregrow = float(_attr(_BLOCKS["db_storage_pregrow"], "threshold"))
    full = float(_attr(_BLOCKS["db_storage"], "threshold"))
    assert pregrow == 70
    assert 63.6 < pregrow < full


def test_pregrow_uses_same_wiring_as_db_storage() -> None:
    pre, full = _BLOCKS["db_storage_pregrow"], _BLOCKS["db_storage"]
    assert "azurerm_monitor_action_group.ops_email[0].id" in pre
    for attr in ("count", "scopes"):
        assert _attr(pre, attr) == _attr(full, attr)
    assert int(_attr(pre, "severity")) > int(_attr(full, "severity"))


def test_pregrow_description_documents_rationale() -> None:
    desc = _attr(_BLOCKS["db_storage_pregrow"], "description")
    assert "BITB-232" in desc and "auto-grow" in desc and ">70%" in desc


# --- evaluate() --------------------------------------------------------------------------


def _s(name: str = "db", size: object = 64) -> dict:
    return {"name": name, "storage": {"storageSizeGb": size}}


def test_evaluate_healthy() -> None:
    assert guard.evaluate([_s()], 64) == []


def test_evaluate_grown() -> None:
    problems = guard.evaluate([_s(size=128)], 64)
    assert len(problems) == 1
    assert "server db: provisioned 128 GB, expected 64 GB" in problems[0]
    assert "auto-grow fired" in problems[0]


def test_evaluate_unexpected_smaller() -> None:
    problems = guard.evaluate([_s(size=32)], 64)
    assert len(problems) == 1 and "provisioned 32 GB, expected 64 GB" in problems[0]


def test_evaluate_multiple_servers() -> None:
    problems = guard.evaluate([_s("a", 64), _s("b", 128), _s("c", 256)], 64)
    assert len(problems) == 2
    assert "server b" in problems[0] and "server c" in problems[1]


@pytest.mark.parametrize(
    "server",
    [
        {"name": "db"},
        {"name": "db", "storage": None},
        {"name": "db", "storage": {}},
        _s(size=None),
        _s(size="64"),
        _s(size=True),
    ],
)
def test_evaluate_missing_or_bad_size(server: dict) -> None:
    problems = guard.evaluate([server], 64)
    assert len(problems) == 1 and "missing or non-numeric" in problems[0]


def test_evaluate_zero_servers() -> None:
    problems = guard.evaluate([], 64)
    assert len(problems) == 1 and "no PostgreSQL flexible servers" in problems[0]


# --- main() ------------------------------------------------------------------------------


def _fake_az(servers: list[dict], rc: int = 0):
    def run(cmd, **kwargs):
        assert kwargs.get("check") is False
        assert cmd[:4] == ["az", "postgres", "flexible-server", "list"]
        return subprocess.CompletedProcess(cmd, rc, json.dumps(servers), "boom" if rc else "")

    return run


def _main(monkeypatch, tmp_path, servers, rc=0, expected="64", rg="rg"):
    monkeypatch.setattr(guard.subprocess, "run", _fake_az(servers, rc))
    monkeypatch.delenv("EXPECTED_DB_STORAGE_GB", raising=False)
    detail = tmp_path / "detail.txt"
    argv = ["--detail-out", str(detail)]
    if rg:
        argv += ["--resource-group", rg]
    if expected is not None:
        argv += ["--expected-gb", expected]
    code = guard.main(argv)
    return code, (detail.read_text() if detail.exists() else "")


def test_main_healthy(monkeypatch, tmp_path) -> None:
    code, detail = _main(monkeypatch, tmp_path, [_s()])
    assert code == 0 and detail == ""


def test_main_grown(monkeypatch, tmp_path) -> None:
    code, detail = _main(monkeypatch, tmp_path, [_s(size=128)])
    assert code == 1
    assert "provisioned 128 GB, expected 64 GB" in detail
    assert "BITB-229" in detail and "EXPECTED_DB_STORAGE_GB" in detail


def test_main_az_failure(monkeypatch, tmp_path) -> None:
    code, detail = _main(monkeypatch, tmp_path, [], rc=1)
    assert code == 1 and "could not verify PostgreSQL storage size" in detail


def test_main_zero_servers(monkeypatch, tmp_path) -> None:
    code, detail = _main(monkeypatch, tmp_path, [])
    assert code == 1 and "no PostgreSQL flexible servers" in detail


@pytest.mark.parametrize("expected", [None, "", "abc", "0", "-5"])
def test_main_missing_or_bad_expected(monkeypatch, tmp_path, expected) -> None:
    code, detail = _main(monkeypatch, tmp_path, [_s()], expected=expected)
    assert code == 1 and "could not verify" in detail


def test_main_missing_resource_group(monkeypatch, tmp_path) -> None:
    code, detail = _main(monkeypatch, tmp_path, [_s()], rg="")
    assert code == 1 and "no resource group" in detail


def test_main_expected_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(guard.subprocess, "run", _fake_az([_s()]))
    monkeypatch.setenv("EXPECTED_DB_STORAGE_GB", "64")
    assert guard.main(["--resource-group", "rg"]) == 0


# --- workflow ----------------------------------------------------------------------------


def test_workflow_expected_size_is_integer() -> None:
    value = _WORKFLOW_YAML["env"]["EXPECTED_DB_STORAGE_GB"]
    assert str(value).isdigit() and int(value) > 0


def test_workflow_job_runs_script_and_notifies() -> None:
    steps = _WORKFLOW_YAML["jobs"]["db-storage-size"]["steps"]
    assert any("check_db_storage_size.py" in s.get("run", "") for s in steps)
    last = steps[-1]
    assert last["uses"] == "./.github/actions/notify-telegram"
    assert last["if"] == "always()"
    assert last["with"]["job_name"] == "db-storage-size"
    assert last["with"]["force_alert"] == "${{ github.event.inputs.force_alert }}"

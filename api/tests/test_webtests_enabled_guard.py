"""BITB-224: availability web tests must be pinned enabled and watched.

`azurerm_application_insights_standard_web_test.enabled` defaults to false; main.tf never
set it, so both tests sat disabled in production. These tests pin the Terraform fix, the
guard script's logic, and the scheduled workflow job that runs it.
"""

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAIN_TF = _REPO_ROOT / "deployment" / "main.tf"
_TFVARS = _REPO_ROOT / "deployment" / "terraform.tfvars"
_SCRIPT = _REPO_ROOT / "scripts" / "monitor" / "check_webtests_enabled.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "prod-deploy-drift.yml"
_WEBTEST_TYPE = "azurerm_application_insights_standard_web_test"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_webtests_enabled", _SCRIPT)
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


def _tfvar(name: str) -> str:
    match = re.search(rf'^\s*{name}\s*=\s*"([^"]+)"', _TFVARS.read_text(), re.MULTILINE)
    assert match, f"{name} not set in {_TFVARS}"
    return match.group(1)


_BLOCKS = _resource_blocks(_MAIN_TF.read_text(), _WEBTEST_TYPE)
_WORKFLOW_YAML = yaml.safe_load(_WORKFLOW.read_text())


# --- Terraform -------------------------------------------------------------------------


def test_webtest_blocks_found() -> None:
    assert {"backend_availability", "backend_preflight"} <= set(_BLOCKS)


@pytest.mark.parametrize("name", ["backend_availability", "backend_preflight"])
@pytest.mark.parametrize("attr", ["enabled", "retry_enabled"])
def test_webtest_pins_attribute_true(name: str, attr: str) -> None:
    assert re.search(
        rf"^\s*{attr}\s*=\s*true\b", _BLOCKS[name], re.MULTILINE
    ), f"{name} must set {attr} = true (provider default for enabled is false, BITB-224)"


def test_expected_webtests_env_matches_terraform_names() -> None:
    suffixes = []
    for name in ("backend_availability", "backend_preflight"):
        match = re.search(
            r'^\s*name\s*=\s*"\$\{local\.name_prefix\}-(\w+)"', _BLOCKS[name], re.MULTILINE
        )
        assert match, f"{name}: name not derived from local.name_prefix"
        suffixes.append(match.group(1))
    prefix = _tfvar("project_name")
    expected = sorted(f"{prefix}-{s}" for s in suffixes)
    actual = sorted(_WORKFLOW_YAML["env"]["EXPECTED_WEBTESTS"].split(","))
    assert actual == expected


# --- evaluate() ------------------------------------------------------------------------


def _t(name: str, enabled: object = True, key: bool = True) -> dict:
    return {"name": name, "properties": {"Enabled": enabled} if key else {}}


def test_evaluate_all_enabled() -> None:
    assert guard.evaluate([_t("a"), _t("b")], ["a", "b"]) == []


def test_evaluate_disabled_flagged() -> None:
    problems = guard.evaluate([_t("a", False), _t("b")], ["a", "b"])
    assert problems == ["a: Enabled=False — synthetic availability monitoring is OFF"]


@pytest.mark.parametrize("test", [_t("a", key=False), _t("a", None), {"name": "a"}])
def test_evaluate_missing_or_none_flagged(test: dict) -> None:
    problems = guard.evaluate([test], ["a"])
    assert len(problems) == 1 and problems[0].startswith("a: Enabled=None")


def test_evaluate_expected_missing() -> None:
    assert guard.evaluate([_t("a")], ["a", "b"]) == ["b: web test not found"]


def test_evaluate_unexpected_disabled_flagged() -> None:
    problems = guard.evaluate([_t("a"), _t("extra", False)], ["a"])
    assert len(problems) == 1 and problems[0].startswith("extra: Enabled=False")


def test_evaluate_string_true_is_not_enabled() -> None:
    problems = guard.evaluate([_t("a", "true")], ["a"])
    assert len(problems) == 1 and "Enabled=true" in problems[0]


# --- main() ----------------------------------------------------------------------------


def _fake_az(tests: dict[str, dict], list_rc: int = 0):
    def run(cmd, **kwargs):
        assert kwargs.get("check") is False
        if cmd[1] == "resource" and cmd[2] == "list":
            out = json.dumps(list(tests))
            return subprocess.CompletedProcess(cmd, list_rc, out, "boom" if list_rc else "")
        resource_id = cmd[cmd.index("--ids") + 1]
        return subprocess.CompletedProcess(cmd, 0, json.dumps(tests[resource_id]), "")

    return run


def _main(monkeypatch, tmp_path, tests, rc=0):
    monkeypatch.setattr(guard.subprocess, "run", _fake_az(tests, rc))
    detail = tmp_path / "detail.txt"
    code = guard.main(
        [
            "--resource-group",
            "rg",
            "--expected",
            "x-availability,x-preflight",
            "--detail-out",
            str(detail),
        ]
    )
    return code, (detail.read_text() if detail.exists() else "")


def test_main_all_enabled(monkeypatch, tmp_path) -> None:
    tests = {"/id/1": _t("x-availability"), "/id/2": _t("x-preflight")}
    code, detail = _main(monkeypatch, tmp_path, tests)
    assert code == 0 and detail == ""


def test_main_one_disabled(monkeypatch, tmp_path) -> None:
    tests = {"/id/1": _t("x-availability", False), "/id/2": _t("x-preflight")}
    code, detail = _main(monkeypatch, tmp_path, tests)
    assert code == 1
    assert "x-availability" in detail
    assert "az resource update --ids" in detail and "properties.Enabled=true" in detail


def test_main_az_failure(monkeypatch, tmp_path) -> None:
    code, detail = _main(monkeypatch, tmp_path, {}, rc=1)
    assert code == 1 and "could not verify web-test state" in detail


# --- workflow --------------------------------------------------------------------------


def test_workflow_jobs_present() -> None:
    assert {"deploy-drift", "webtests-enabled"} <= set(_WORKFLOW_YAML["jobs"])


def test_workflow_cron_unchanged() -> None:
    assert _WORKFLOW_YAML["on"]["schedule"] == [{"cron": "*/15 * * * *"}]


def test_workflow_job_runs_script_and_notifies() -> None:
    steps = _WORKFLOW_YAML["jobs"]["webtests-enabled"]["steps"]
    assert any("check_webtests_enabled.py" in s.get("run", "") for s in steps)
    last = steps[-1]
    assert last["uses"] == "./.github/actions/notify-telegram"
    assert last["if"] == "always()"
    assert last["with"]["job_name"] == "webtests-enabled"

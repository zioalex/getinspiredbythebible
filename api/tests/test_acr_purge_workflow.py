"""BITB-370: the weekly ACR purge workflow must be safe (protect deployed images) and bounded."""

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "acr-purge.yml"
_DEPLOY = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"

_DOC = yaml.safe_load(_WORKFLOW.read_text())  # `on` is quoted in the file, so the key is "on"
_STEPS = _DOC["jobs"]["purge"]["steps"]


def _index(name_fragment: str) -> int:
    for i, step in enumerate(_STEPS):
        if name_fragment in step.get("name", ""):
            return i
    raise AssertionError(f"no step containing {name_fragment!r}")


def test_weekly_schedule_present() -> None:
    crons = [entry["cron"] for entry in _DOC["on"]["schedule"]]
    assert len(crons) == 1
    minute, _hour, dom, month, dow = crons[0].split()
    assert dow != "*" and dom == "*" and month == "*"  # weekly
    assert minute != "0" and not minute.startswith("*")  # off the hour (spread load)


def test_dispatch_dry_run_defaults_to_true() -> None:
    dry = _DOC["on"]["workflow_dispatch"]["inputs"]["dry_run"]
    assert dry["type"] == "boolean"
    assert dry["default"] is True


def test_least_privilege_and_bounded() -> None:
    assert _DOC["permissions"] == {"contents": "read"}
    assert _DOC["concurrency"]["cancel-in-progress"] is False
    assert _DOC["jobs"]["purge"]["timeout-minutes"] <= 60


def test_purge_command_flags() -> None:
    run = _STEPS[_index("Purge")]["run"]
    assert "az acr run" in run and "acr purge" in run
    assert "--untagged" in run
    assert "--ago" in run
    keep = re.search(r"--keep (\d+)", run)
    assert keep and int(keep.group(1)) >= 5
    assert "bible-backend" in run and "bible-frontend" in run
    assert "--dry-run" in run  # dry_run input is wired to acr purge's --dry-run


def test_deployed_images_locked_before_purge() -> None:
    protect = _index("Lock currently deployed images")
    assert protect < _index("Purge")
    run = _STEPS[protect]["run"]
    assert "az containerapp show" in run
    assert "--delete-enabled false" in run and "--write-enabled false" in run
    assert "exit 1" in run  # fail closed when the deployed image cannot be read


def test_unlock_always_runs_after_purge() -> None:
    unlock = _index("Unlock deployed images")
    assert unlock > _index("Purge")
    assert "always()" in _STEPS[unlock]["if"]
    run = _STEPS[unlock]["run"]
    assert "--delete-enabled true" in run and "--write-enabled true" in run


def test_acr_name_matches_deploy_workflow() -> None:
    deploy = yaml.safe_load(_DEPLOY.read_text())
    assert _DOC["env"]["ACR_NAME"] == deploy["env"]["ACR_NAME"]
    assert _DOC["env"]["RESOURCE_GROUP"] == deploy["env"]["RESOURCE_GROUP"]
    assert _DOC["env"]["BACKEND_APP_NAME"] == deploy["env"]["BACKEND_APP_NAME"]
    assert _DOC["env"]["FRONTEND_APP_NAME"] == deploy["env"]["FRONTEND_APP_NAME"]


def test_usage_reported_before_and_after() -> None:
    assert "az acr show-usage" in _STEPS[_index("usage before")]["run"]
    assert "az acr show-usage" in _STEPS[_index("usage after")]["run"]

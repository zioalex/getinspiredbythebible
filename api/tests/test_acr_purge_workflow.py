"""BITB-372: the weekly ACR purge workflow must be safe (protect deployed images) and bounded."""

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
    assert _DOC["jobs"]["purge"]["timeout-minutes"] <= 120


def test_purge_command_flags() -> None:
    run = _STEPS[_index("Purge")]["run"]
    assert "az acr run" in run and "acr purge" in run
    assert "--untagged" in run
    assert "--ago" in run
    keep = re.search(r"--keep (\d+)", run)
    assert keep and int(keep.group(1)) >= 5
    assert "bible-backend" in run and "bible-frontend" in run
    assert "--dry-run" in run  # dry_run input is wired to acr purge's --dry-run
    assert re.search(r"--ago 14d\b", run)
    assert re.search(r"--timeout \d+", run)
    # dry_run comes from github.event.inputs.dry_run (empty on a schedule run => real purge)
    # and only the literal 'true' enables --dry-run; an inverted test would dry-run schedules.
    step = _STEPS[_index("Purge")]
    assert step["env"]["DRY_RUN_INPUT"] == "${{ github.event.inputs.dry_run }}"
    assert re.search(r'if \[ "\$DRY_RUN_INPUT" == "true" \]; then\s+DRY="--dry-run"', run)
    assert "!=" not in re.search(r"if \[ \"\$DRY_RUN_INPUT.*", run).group(0)


def test_deployed_images_locked_before_purge() -> None:
    protect = _index("Lock currently deployed images")
    assert protect < _index("Purge")
    run = _STEPS[protect]["run"]
    assert "az containerapp show" in run
    assert "--delete-enabled false" in run and "--write-enabled false" in run
    assert "exit 1" in run  # fail closed when the deployed image cannot be read


def test_prior_lock_state_recorded_then_restored() -> None:
    protect = _STEPS[_index("Lock currently deployed images")]["run"]
    assert "changeableAttributes.writeEnabled" in protect
    assert "changeableAttributes.deleteEnabled" in protect
    assert protect.index("az acr repository show") < protect.index("--write-enabled false")
    unlock = _STEPS[_index("Unlock deployed images")]["run"]
    # restores the recorded values rather than forcing true
    assert '--write-enabled "$write_prev"' in unlock and '--delete-enabled "$delete_prev"' in unlock


def test_unlock_always_runs_after_purge_with_guard() -> None:
    unlock = _index("Unlock deployed images")
    assert unlock > _index("Purge")
    cond = _STEPS[unlock]["if"]
    assert "always()" in cond and "steps.protect.outcome" in cond


def test_step_order_protect_purge_unlock_verify() -> None:
    order = [
        _index("Lock currently deployed images"),
        _index("Purge"),
        _index("Unlock deployed images"),
        _index("Verify deployed images still exist"),
    ]
    assert order == sorted(order) and len(set(order)) == 4
    assert "show-tags" in _STEPS[order[3]]["run"] and "exit 1" in _STEPS[order[3]]["run"]


def test_telegram_step_supplies_required_action_inputs() -> None:
    action = yaml.safe_load(
        (_REPO_ROOT / ".github" / "actions" / "notify-telegram" / "action.yml").read_text()
    )
    required = {k for k, v in action["inputs"].items() if v.get("required")}
    step = _STEPS[_index("Notify Telegram")]
    assert step["uses"] == "./.github/actions/notify-telegram"
    assert step["if"] == "always()"
    assert required <= set(step["with"]), required - set(step["with"])


def test_acr_name_matches_deploy_workflow() -> None:
    deploy = yaml.safe_load(_DEPLOY.read_text())
    assert _DOC["env"]["ACR_NAME"] == deploy["env"]["ACR_NAME"]
    assert _DOC["env"]["RESOURCE_GROUP"] == deploy["env"]["RESOURCE_GROUP"]
    assert _DOC["env"]["BACKEND_APP_NAME"] == deploy["env"]["BACKEND_APP_NAME"]
    assert _DOC["env"]["FRONTEND_APP_NAME"] == deploy["env"]["FRONTEND_APP_NAME"]


def test_usage_reported_before_and_after() -> None:
    assert "az acr show-usage" in _STEPS[_index("usage before")]["run"]
    assert "az acr show-usage" in _STEPS[_index("usage after")]["run"]


# Registry-name flag per `az acr` subcommand, as accepted by the real Azure CLI. The 2026-11-27
# first live run failed because `az acr show-usage --registry X` was used (show-usage only takes
# --name/-n; only `az acr run` takes --registry/-r).
_REGISTRY_FLAG = {
    "show-usage": ("--name", "-n"),
    "repository show": ("--name", "-n"),
    "repository update": ("--name", "-n"),
    "repository show-tags": ("--name", "-n"),
    "run": ("--registry", "-r"),
}


def _az_acr_invocations() -> list[tuple[str, str]]:
    """Every `az acr <subcommand> ...` in the steps' run scripts as (subcommand, rest)."""
    scripts = "\n".join(step.get("run", "") for step in _STEPS)
    code = "\n".join(ln for ln in scripts.splitlines() if not ln.lstrip().startswith("#"))
    text = re.sub(r"\\\n\s*", " ", code)  # join `\` line continuations
    found = []
    for match in re.finditer(r"\baz acr ((?:repository )?[a-z-]+)([^\n|;&)]*)", text):
        found.append((match.group(1), match.group(2)))
    return found


def test_az_acr_registry_flags_match_cli() -> None:
    invocations = _az_acr_invocations()
    assert {sub for sub, _ in invocations} <= set(_REGISTRY_FLAG), invocations
    for sub, rest in invocations:
        ok_flags = _REGISTRY_FLAG[sub]
        wrong = {"--name", "-n", "--registry", "-r"} - set(ok_flags)
        used = set(re.findall(r"(?<!\S)(--name|-n|--registry|-r)(?=[\s=])", rest))
        assert used & set(ok_flags), f"az acr {sub} must pass the registry via {ok_flags}: {rest!r}"
        assert not used & wrong, f"az acr {sub} does not accept {used & wrong}: {rest!r}"


def test_usage_before_never_blocks_the_purge() -> None:
    assert "|| true" in _STEPS[_index("usage before")]["run"]

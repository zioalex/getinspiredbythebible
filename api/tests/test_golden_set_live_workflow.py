"""Guards for `.github/workflows/golden-set-live.yml` (BITB-177).

The workflow runs the `interpretation` golden set against production once a week through the
server-to-server probe bypass. These tests pin the properties that must not regress silently:
it is a measurement and never a PR gate, it holds read-only permissions, the probe secret reaches
the script through `env` only, the run is skipped (not failed) when the secret is absent, and the
run JSON is uploaded as an artifact.

Style follows `test_search_eval_workflow_credentials.py`.
"""

import ast
import re
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "golden-set-live.yml"
_JOB = "golden-set-live"


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _load_workflow() -> dict:
    return yaml.safe_load(_workflow_text())


def _steps() -> list[dict]:
    return _load_workflow()["jobs"][_JOB]["steps"]


def _step(step_id: str) -> dict:
    for step in _steps():
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"no step with id {step_id!r}")


def _triggers(workflow: dict) -> dict:
    # PyYAML (YAML 1.1) reads an unquoted `on:` as the boolean True; the file quotes it.
    return workflow.get("on", workflow.get(True))


def test_triggers_are_exactly_schedule_and_workflow_dispatch():
    triggers = _triggers(_load_workflow())
    assert set(triggers) == {"schedule", "workflow_dispatch"}, (
        f"triggers are {sorted(triggers)}; the live run must never fire on pull_request or push "
        "(it spends production requests and is a measurement, not a merge gate)"
    )
    assert len(triggers["schedule"]) == 1
    assert triggers["schedule"][0]["cron"] == "37 3 * * 1"


def test_manual_inputs_are_category_tags_and_fail_under_with_safe_defaults():
    inputs = _triggers(_load_workflow())["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"category", "tags", "fail_under"}
    assert inputs["category"]["default"] == "interpretation"
    assert inputs["tags"]["default"] == ""
    assert str(inputs["fail_under"]["default"]) == "0"


def test_permissions_are_contents_read_only():
    workflow = _load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"][_JOB], "the job must not widen the permissions"


def test_runs_never_overlap_and_have_a_timeout():
    workflow = _load_workflow()
    assert workflow["concurrency"]["group"] == "golden-set-live"
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert workflow["jobs"][_JOB]["timeout-minutes"] == 45


def test_probe_secret_reaches_the_script_through_env_only():
    run_step = _step("run")
    env = run_step["env"]
    assert env["GOLDEN_SET_PROBE_SECRET"] == "${{ secrets.MONITOR_PROBE_SECRET }}"
    assert "${{" not in run_step["run"], (
        "the run step interpolates an expression into its script; secrets and workflow inputs "
        "must reach the script through `env:` only (script injection, ACTIONS_SECURITY.md)"
    )
    assert "MONITOR_PROBE_SECRET" not in run_step["run"]


def test_no_expression_is_interpolated_into_any_run_line():
    offenders = [
        step.get("name", step.get("id"))
        for step in _steps()
        if "run" in step and "${{" in step["run"]
    ]
    assert not offenders, f"steps interpolate an expression inside run: {offenders}"


def test_workflow_inputs_are_passed_via_env():
    env = _step("run")["env"]
    assert env["INPUT_CATEGORY"] == "${{ github.event.inputs.category }}"
    assert env["INPUT_TAGS"] == "${{ github.event.inputs.tags }}"
    assert env["INPUT_FAIL_UNDER"] == "${{ github.event.inputs.fail_under }}"
    script = _step("run")["run"]
    # quoted, so a tag list with spaces or shell metacharacters stays one argument
    assert '--category "${INPUT_CATEGORY:-interpretation}"' in script
    assert '--fail-under "${INPUT_FAIL_UNDER:-0}"' in script
    assert '--tags "$INPUT_TAGS"' in script


def test_secret_is_never_echoed_or_put_on_the_command_line():
    text = _workflow_text()
    script = _step("run")["run"]
    assert "GOLDEN_SET_PROBE_SECRET" not in script, "the script must not touch the secret at all"
    assert "--probe-secret" not in text
    assert not re.search(r"echo[^\n]*\$\{?GOLDEN_SET_PROBE_SECRET", text)
    assert not re.search(r"X-Monitor-Probe-Secret", script)


def test_run_step_is_skipped_when_the_secret_is_empty():
    guard = _step("guard")
    assert guard["env"]["HAS_PROBE_SECRET"] == "${{ secrets.MONITOR_PROBE_SECRET != '' }}"
    assert "has_probe_secret=${HAS_PROBE_SECRET}" in guard["run"]
    assert "::notice::" in guard["run"], "the skip must be visible, not silent"
    assert "exit 1" not in guard["run"], "a missing secret skips the run; it does not fail it"
    assert _step("run")["if"] == "steps.guard.outputs.has_probe_secret == 'true'"


def test_target_is_the_production_backend_url_used_by_prod_monitor():
    workflow = _load_workflow()
    assert "vars.BACKEND_URL" in workflow["env"]["BACKEND_URL"]
    monitor = yaml.safe_load((_REPO_ROOT / ".github/workflows/prod-monitor.yml").read_text())
    assert workflow["env"]["BACKEND_URL"] == monitor["env"]["BACKEND_URL"]
    run_step = _step("run")
    assert run_step["env"]["BACKEND_URL"] == "${{ env.BACKEND_URL }}"
    assert '--base-url "$BACKEND_URL"' in run_step["run"]


def test_runs_the_interpretation_category_through_the_cli_and_keeps_its_exit_code():
    script = _step("run")["run"]
    assert "scripts/run_golden_set.py" in script
    assert "--delay 2" in script
    assert '--output "$RUNNER_TEMP/golden-run.json"' in script
    assert "GITHUB_STEP_SUMMARY" in script
    # the summary and artifact are written first, then the runner's exit code decides the job
    assert 'exit "$code"' in script
    assert script.index("GITHUB_STEP_SUMMARY") < script.index('exit "$code"')


def test_run_json_is_uploaded_as_an_artifact_even_when_the_run_fails():
    upload = [s for s in _steps() if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
    assert len(upload) == 1
    step = upload[0]
    assert step["if"] == "always()"
    assert "golden-run.json" in step["with"]["path"]
    assert step["with"]["if-no-files-found"] == "ignore", "a skipped run has nothing to upload"


def test_installs_only_what_the_runner_imports_and_pins_python():
    steps = _steps()
    setup = [s for s in steps if str(s.get("uses", "")).startswith("actions/setup-python@")]
    assert setup and setup[0]["with"]["python-version"] == "3.12"
    install = next(s for s in steps if "pip install" in s.get("run", ""))
    assert install["run"].strip() == "pip install httpx pyyaml pydantic"


def _top_level_imports(path: Path) -> set[str]:
    """Module-level imports only. Function-level imports are deliberate lazy, fail-open ones
    (evaluators.check_response_language imports utils.language and skips itself when it is
    unavailable, which is the case in the workflow)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_cli_and_runner_need_only_the_dependencies_the_workflow_installs():
    """The workflow installs httpx, pyyaml and pydantic only. The CLI and runner must not import
    `config` or `utils` (which pull the full backend requirements and need a DATABASE_URL)."""
    cli = _top_level_imports(_REPO_ROOT / "scripts" / "run_golden_set.py")
    assert cli <= {"argparse", "asyncio", "sys", "pathlib", "golden_set"}, cli

    stdlib = set(sys.stdlib_module_names)
    for module in ("runner", "evaluators", "loader", "models"):
        imports = _top_level_imports(_REPO_ROOT / "api" / "golden_set" / f"{module}.py")
        third_party = imports - stdlib - {"golden_set"}
        assert third_party <= {"httpx", "yaml", "pydantic"}, (module, third_party)

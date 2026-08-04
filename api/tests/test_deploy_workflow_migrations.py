"""Guards against the specific silent-failure mode BITB-089 exists to close.

Before this story, a revision added under `api/alembic/versions/**` matched
no path filter in the deploy workflow, so `run-migrations` never ran it --
no error, no warning, just schema drift discovered later by a 500. These
tests parse `.github/workflows/azure-deploy.yml` and assert the four things
that would let that regress silently:

  1. the `changes` job's path filter watches `api/alembic/versions/**`
  2. `changes` exposes that as a job output
  3. `run-migrations` actually invokes `alembic upgrade head`
  4. that invocation is gated on the stamp preflight (so it can't reach an
     unstamped production database), and does not reuse the legacy step's
     `?ssl=require` URL form (BITB-089's other silent hazard).

Deliberately narrow: this is a regression guard for one dangerous failure
mode, not a full schema validation of the workflow file.
"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"


def _load_workflow() -> dict:
    # PyYAML parses the `on:` mapping key as the boolean True in YAML 1.1,
    # colliding with the `true`/`false` keys workflow files also use --
    # irrelevant here since we only read `jobs`, but load raw to avoid
    # surprises if that ever changes.
    return yaml.safe_load(_WORKFLOW_PATH.read_text())


def _run_migrations_steps() -> list[dict]:
    workflow = _load_workflow()
    return workflow["jobs"]["run-migrations"]["steps"]


def test_changes_job_filters_alembic_versions():
    workflow = _load_workflow()
    filters = workflow["jobs"]["changes"]["steps"][-1]["with"]["filters"]
    assert "alembic_migrations" in filters
    assert "api/alembic/versions/**" in filters


def test_changes_job_exposes_alembic_migrations_output():
    workflow = _load_workflow()
    outputs = workflow["jobs"]["changes"]["outputs"]
    assert outputs.get("alembic_migrations") == "${{ steps.filter.outputs.alembic_migrations }}"


def test_run_migrations_job_triggers_on_alembic_change():
    workflow = _load_workflow()
    condition = workflow["jobs"]["run-migrations"]["if"]
    assert "needs.changes.outputs.alembic_migrations" in condition


def test_run_migrations_job_invokes_alembic_upgrade_head():
    steps = _run_migrations_steps()
    upgrade_steps = [s for s in steps if "alembic upgrade head" in (s.get("run") or "")]
    assert upgrade_steps, "no step in run-migrations invokes `alembic upgrade head`"


def test_alembic_upgrade_step_is_gated_on_stamp_preflight():
    steps = _run_migrations_steps()
    upgrade_steps = [s for s in steps if "alembic upgrade head" in (s.get("run") or "")]
    assert upgrade_steps, "no step in run-migrations invokes `alembic upgrade head`"
    for step in upgrade_steps:
        assert "stamped" in step.get("if", ""), (
            f"step {step.get('name')!r} runs `alembic upgrade head` without checking the "
            "stamp preflight output -- this could point an unstamped production database "
            "at CREATE TABLE for an already-existing schema"
        )


def test_no_alembic_step_uses_the_ssl_require_url_form():
    steps = _run_migrations_steps()
    alembic_steps = [s for s in steps if "alembic" in (s.get("run") or "")]
    assert alembic_steps, "expected at least one alembic step in run-migrations"
    for step in alembic_steps:
        assert "?ssl=require" not in step["run"], (
            f"step {step.get('name')!r} builds a DATABASE_URL with `?ssl=require`, which "
            "get_async_database_url() must strip -- use `?sslmode=require` for Alembic "
            "steps (see BITB-089)"
        )

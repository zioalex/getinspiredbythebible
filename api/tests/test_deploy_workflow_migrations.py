"""Guards against the silent-failure mode BITB-089 existed to close.

Before BITB-089, a revision added under `api/alembic/versions/**` matched no
path filter in the deploy workflow, so `run-migrations` never ran it -- no
error, no warning, just schema drift discovered later by a 500. The whole story
turned on a job *not running*, which is the hardest kind of failure to notice.

These tests parse `.github/workflows/azure-deploy.yml` and assert the handful of
properties that would let that regress silently. Deliberately narrow: a
regression guard for one dangerous failure mode, not a schema validation of the
workflow file.

Adapted from PR #966, which proposed a different implementation of the same
story (a separate `alembic_migrations` filter key and an `if:`-gated upgrade
step). The version that shipped in #974 reuses the existing `migration_scripts`
filter and puts the preflight inline in the step's script, so the assertions
below target that -- the intent is #966's, the specifics are main's.
"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"

_ALEMBIC_VERSIONS_GLOB = "api/alembic/versions/**"


def _load_workflow() -> dict:
    return yaml.safe_load(_WORKFLOW_PATH.read_text())


def _changes_filters() -> dict:
    """The `dorny/paths-filter` inputs from the `changes` job, parsed.

    The filters are authored as a YAML string inside the workflow YAML, so they
    need a second parse.
    """
    workflow = _load_workflow()
    for step in workflow["jobs"]["changes"]["steps"]:
        with_block = step.get("with") or {}
        if "filters" in with_block:
            return yaml.safe_load(with_block["filters"])
    raise AssertionError("no paths-filter step found in the `changes` job")


def _run_migrations_steps() -> list[dict]:
    return _load_workflow()["jobs"]["run-migrations"]["steps"]


def _alembic_steps() -> list[dict]:
    return [s for s in _run_migrations_steps() if "alembic" in (s.get("run") or "")]


def test_a_path_filter_watches_alembic_versions():
    """The bug this story fixed: nothing watched `api/alembic/versions/**`, so a
    committed revision matched no filter and was never applied."""
    filters = _changes_filters()
    watched = {glob for globs in filters.values() for glob in globs}
    assert _ALEMBIC_VERSIONS_GLOB in watched, (
        f"No path filter watches {_ALEMBIC_VERSIONS_GLOB!r}. A committed Alembic "
        f"revision would silently never deploy. Watched globs: {sorted(watched)}"
    )


def test_the_filter_watching_alembic_versions_gates_run_migrations():
    """Watching the path is useless unless `run-migrations` keys off that filter."""
    filters = _changes_filters()
    gating = [name for name, globs in filters.items() if _ALEMBIC_VERSIONS_GLOB in globs]
    assert gating, f"{_ALEMBIC_VERSIONS_GLOB!r} is not in any filter"

    condition = _load_workflow()["jobs"]["run-migrations"]["if"]
    assert any(f"needs.changes.outputs.{name}" in condition for name in gating), (
        f"run-migrations does not gate on any filter that watches "
        f"{_ALEMBIC_VERSIONS_GLOB!r} (filters watching it: {gating}). The path "
        f"would be watched but the job still would not run."
    )


def test_run_migrations_invokes_alembic_upgrade_head():
    assert [
        s for s in _run_migrations_steps() if "alembic upgrade head" in (s.get("run") or "")
    ], "no step in run-migrations invokes `alembic upgrade head`"


def test_alembic_upgrade_is_preceded_by_a_stamp_preflight():
    """`upgrade head` against an unstamped database replays the r0001 baseline
    and dies on "relation already exists". The step must check for an
    `alembic_version` row first and fail closed with the remedy.

    The preflight is inline in the step's script rather than an `if:` condition,
    so this asserts on the script.
    """
    upgrade_steps = [
        s for s in _run_migrations_steps() if "alembic upgrade head" in (s.get("run") or "")
    ]
    assert upgrade_steps, "no step in run-migrations invokes `alembic upgrade head`"
    for step in upgrade_steps:
        script = step["run"]
        assert "alembic current" in script, (
            f"step {step.get('name')!r} runs `alembic upgrade head` without first "
            "reading `alembic current` -- it cannot tell a stamped database from "
            "an unstamped one"
        )
        assert "stamp r0001" in script, (
            f"step {step.get('name')!r} has no preflight naming the remedy "
            "(`alembic stamp r0001`); an unstamped target would fail with an "
            "unhelpful 'relation already exists' instead"
        )


def test_no_alembic_step_uses_the_ssl_require_url_form():
    """`?ssl=require` reaching an asyncpg-driven tool fails with
    "parameter 'ssl' cannot be changed now". `get_async_database_url()` strips it
    now, but the URL form the workflow builds should not rely on that."""
    steps = _alembic_steps()
    assert steps, "expected at least one alembic step in run-migrations"
    for step in steps:
        assert "?ssl=require" not in step["run"], (
            f"step {step.get('name')!r} builds a DATABASE_URL with `?ssl=require`; "
            "use `?sslmode=require` for Alembic steps (BITB-089)"
        )


def test_legacy_migrations_still_run_alongside_alembic():
    """`scripts/migrations/` is frozen, not retired -- it still runs every deploy.
    Dropping it would strand any environment not yet covered by Alembic."""
    steps = _run_migrations_steps()
    assert [
        s for s in steps if "run_migrations.py" in (s.get("run") or "")
    ], "the legacy scripts/migrations runner no longer runs in run-migrations"


# -----------------------------------------------------------------------------
# BITB-097: deploy must not run before its migration.
#
# Before this story, `deploy: needs: [..., changes]` and
# `run-migrations: needs: [changes, deploy]` -- new application code went
# live *before* the migration it depended on. These tests assert the
# inverted ordering directly off the parsed job graph, so a regression back
# to "deploy first" fails loudly instead of waiting for another outage to
# surface it.
# -----------------------------------------------------------------------------


def test_deploy_depends_on_run_migrations():
    """`deploy` must wait for `run-migrations` to finish, not the reverse."""
    jobs = _load_workflow()["jobs"]
    assert "run-migrations" in jobs["deploy"]["needs"], (
        "`deploy` does not list `run-migrations` in `needs` -- application code "
        "could go live before its own migration runs (BITB-097)"
    )


def test_run_migrations_does_not_depend_on_deploy():
    """The whole point of the BITB-097 inversion: a regression back to the old
    `run-migrations: needs: [..., deploy]` order must fail this test."""
    jobs = _load_workflow()["jobs"]
    assert "deploy" not in jobs["run-migrations"]["needs"], (
        "`run-migrations` still lists `deploy` in `needs` -- the pipeline has "
        "regressed to migrating *after* the new code is already live (BITB-097)"
    )


def test_deploy_if_checks_run_migrations_result():
    """`deploy`'s `if:` opens with `always()`, so without an explicit check on
    `needs.run-migrations.result` it would proceed even after a *failed*
    migration -- `always()` disables GitHub Actions' default
    skip-on-failed-dependency behavior."""
    jobs = _load_workflow()["jobs"]
    condition = jobs["deploy"]["if"]
    assert "needs.run-migrations.result" in condition, (
        "`deploy`'s `if:` does not reference `needs.run-migrations.result` -- "
        "combined with the leading `always()`, a failed migration would not "
        "block deploy (BITB-097)"
    )


def test_functional_tests_depends_on_run_migrations():
    """`functional-tests` must not race the migration it is meant to validate
    against. Depending on `deploy` alone let it start while `run-migrations`
    was still `waiting` on approval, testing a system mid-migration."""
    jobs = _load_workflow()["jobs"]
    needs = jobs["functional-tests"]["needs"]
    assert "deploy" in needs and "run-migrations" in needs, (
        f"`functional-tests` needs {needs!r}, expected both `deploy` and "
        "`run-migrations` (BITB-097)"
    )


def test_functional_tests_if_checks_run_migrations_result():
    jobs = _load_workflow()["jobs"]
    condition = jobs["functional-tests"]["if"]
    assert "needs.run-migrations.result" in condition, (
        "`functional-tests`'s `if:` does not reference "
        "`needs.run-migrations.result` -- it could still start before the "
        "migration finishes (BITB-097)"
    )


def test_concurrency_group_prevents_run_pileup():
    """No `concurrency` group meant every push queued another full run and none
    superseded its predecessor -- 16 runs piled up in the `production`
    approval queue by 2026-08-18. `cancel-in-progress` must stay `False`:
    cancelling a *running* run mid-migration is the client-killed-DDL-survives
    failure mode BITB-096 hit."""
    workflow = _load_workflow()
    concurrency = workflow.get("concurrency")
    assert concurrency, "workflow has no top-level `concurrency` group (BITB-097)"
    assert "group" in concurrency, "`concurrency` block has no `group` key"
    assert concurrency.get("cancel-in-progress") is False, (
        f"`concurrency.cancel-in-progress` is {concurrency.get('cancel-in-progress')!r}, "
        "expected `False` -- `True` would cancel a running migration mid-DDL"
    )


def test_deploy_workflow_watches_deployment_and_itself_via_test_update():
    """BITB-097 defect 4: `azure-deploy.yml` only fires via `workflow_run` off
    `test_update.yml`, so `test_update.yml`'s own trigger paths gate whether a
    Terraform-only or azure-deploy.yml-only merge ever reaches production. A
    `deployment/main.tf`-only PR (#1002) merged 2026-08-18 and deployed
    nothing because neither path was watched."""
    test_update_path = _REPO_ROOT / ".github" / "workflows" / "test_update.yml"
    test_update = yaml.safe_load(test_update_path.read_text())
    triggers = test_update["on"]
    for trigger_name in ("pull_request", "push"):
        paths = triggers[trigger_name]["paths"]
        assert "deployment/**" in paths, (
            f"test_update.yml's `{trigger_name}.paths` does not watch "
            "`deployment/**` -- a Terraform-only merge would never trigger "
            "the test workflow, and therefore never emit the `workflow_run` "
            "event azure-deploy.yml listens for (BITB-097)"
        )
        assert ".github/workflows/azure-deploy.yml" in paths, (
            f"test_update.yml's `{trigger_name}.paths` does not watch "
            "`.github/workflows/azure-deploy.yml` itself (BITB-097)"
        )

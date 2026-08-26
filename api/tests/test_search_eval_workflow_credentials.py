"""Guards against the admin-credential regression BITB-101 fixed.

Before BITB-101, `.github/workflows/search-eval-full.yml`'s `eval-prod` job
authenticated against production Postgres with `TF_VAR_DB_ADMIN_USERNAME` /
`TF_VAR_DB_ADMIN_PASSWORD` -- the same admin credentials `run-migrations`
uses to run DDL -- even though this job only ever issues `SELECT`s, runs
unattended on a nightly schedule, and had no approval gate. The fix swaps
it to a dedicated `search_eval_ro` role (provisioned by
`api/alembic/versions/r0005_add_search_eval_ro_role.py`, with
`default_transaction_read_only = on` enforced by the database itself)
authenticated via the environment-scoped `SEARCH_EVAL_DB_PASSWORD` secret.

The whole point of the story is that this stays enforced, not just fixed
once -- a future edit to the workflow could quietly reintroduce the admin
credential (e.g. "just for a quick debug run"), and that would be exactly
as dangerous as the original defect. These tests parse
`search-eval-full.yml` and assert the properties that would let that
regress silently.

Adapted from the style of `api/tests/test_deploy_workflow_migrations.py`.
"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "search-eval-full.yml"


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text()


def _load_workflow() -> dict:
    return yaml.safe_load(_workflow_text())


def test_no_admin_credentials_in_search_eval_workflow():
    """The admin credential must never appear anywhere in this file -- not in
    an `env:` block, not in a comment explaining what *not* to do. Either
    form would be exactly the kind of quiet re-widening this story exists to
    prevent."""
    text = _workflow_text()
    assert "TF_VAR_DB_ADMIN_USERNAME" not in text, (
        "TF_VAR_DB_ADMIN_USERNAME appears in search-eval-full.yml -- the "
        "nightly eval-prod job must not authenticate with Postgres admin "
        "credentials (BITB-101)"
    )
    assert "TF_VAR_DB_ADMIN_PASSWORD" not in text, (
        "TF_VAR_DB_ADMIN_PASSWORD appears in search-eval-full.yml -- the "
        "nightly eval-prod job must not authenticate with Postgres admin "
        "credentials (BITB-101)"
    )


def test_eval_prod_uses_the_dedicated_readonly_secret():
    """Weak but literal: the new secret must actually be wired in somewhere
    in the file, not just introduced in the header comment."""
    text = _workflow_text()
    assert "SEARCH_EVAL_DB_PASSWORD" in text, (
        "search-eval-full.yml does not reference SEARCH_EVAL_DB_PASSWORD -- "
        "eval-prod has no way to authenticate as search_eval_ro (BITB-101)"
    )


def test_eval_prod_job_is_environment_scoped():
    """A plain text search can't reliably prove this -- a comment could
    contain the string `environment: search-eval` without the job actually
    being scoped to it -- so this one assertion works off the parsed YAML
    job definition instead."""
    workflow = _load_workflow()
    eval_prod = workflow["jobs"]["eval-prod"]
    assert eval_prod.get("environment") == "search-eval", (
        f"eval-prod's `environment` is {eval_prod.get('environment')!r}, "
        "expected 'search-eval' -- without environment scoping, "
        "SEARCH_EVAL_DB_PASSWORD would be a bare repo secret readable by "
        "any workflow in the repo (BITB-101)"
    )

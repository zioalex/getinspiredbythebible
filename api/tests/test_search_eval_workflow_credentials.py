"""Guards against the admin-credential regression BITB-101 fixed.

Before BITB-101, `.github/workflows/search-eval-full.yml`'s `eval-prod` job
authenticated against production Postgres with `TF_VAR_DB_ADMIN_USERNAME` /
`TF_VAR_DB_ADMIN_PASSWORD` -- the same admin credentials `run-migrations`
uses to run DDL -- even though this job only ever issues `SELECT`s, runs
unattended on a nightly schedule, and had no approval gate. The fix swaps
it to a dedicated `search_eval_ro` role (provisioned by
`api/alembic/versions/r0005_add_search_eval_ro_role.py` plus r0006's topic
table grants, with
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


# ---------------------------------------------------------------------------
# The environment-scoped secret must be read from a job that declares the
# environment (BITB-101 follow-up).
#
# Scoping SEARCH_EVAL_DB_PASSWORD to the `search-eval` environment is the
# whole point of the story above -- but it also means the secret is simply
# absent from the `secrets` context of any job that does not declare
# `environment: search-eval`. The original preflight job checked it anyway,
# so `has_db` was `false` on a correctly-configured repo exactly as it was on
# an unconfigured one, and eval-prod skipped on every scheduled run even
# after the operator created the environment and set the secret (observed on
# run 33207972265). The fail-closed default silently became fail-always.
#
# These tests pin the shape that avoids it: the presence check lives in a job
# that is environment-scoped, and preflight -- which also gates eval-smoke --
# stays out of the environment.
# ---------------------------------------------------------------------------


def _job_yaml(name: str) -> str:
    """The raw text of one job block, for assertions the parsed YAML can't
    make (`secrets.X` references live inside expression strings)."""
    text = _workflow_text()
    start = text.index(f"\n  {name}:\n")
    rest = text[start + 1 :]
    lines = rest.splitlines(keepends=True)
    body = [lines[0]]
    for line in lines[1:]:
        # A new job starts at exactly two spaces of indentation.
        if line.strip() and not line.startswith("    ") and not line.startswith("  #"):
            break
        body.append(line)
    return "".join(body)


def test_preflight_does_not_check_the_environment_scoped_secret():
    """preflight has no `environment:`, so `secrets.SEARCH_EVAL_DB_PASSWORD`
    is always empty there. Reading it would re-create the always-skip bug."""
    workflow = _load_workflow()
    preflight = workflow["jobs"]["preflight"]
    assert "environment" not in preflight, (
        "preflight declares an environment -- it gates eval-smoke as well as "
        "eval-prod, so it must not inherit the search-eval environment's "
        "branch policy or any reviewer added to it"
    )
    assert "SEARCH_EVAL_DB_PASSWORD" not in _job_yaml("preflight"), (
        "preflight reads SEARCH_EVAL_DB_PASSWORD, but an environment-scoped "
        "secret is invisible to a job that does not declare the environment: "
        "the check always yields 'false' and eval-prod is skipped even when "
        "the operator has set the secret correctly"
    )


def test_the_db_password_check_lives_in_an_environment_scoped_job():
    workflow = _load_workflow()
    gate = workflow["jobs"]["prod-secret-check"]
    assert gate.get("environment") == "search-eval", (
        f"prod-secret-check's `environment` is {gate.get('environment')!r}, "
        "expected 'search-eval' -- otherwise it cannot see the secret it "
        "exists to check"
    )
    assert "SEARCH_EVAL_DB_PASSWORD" in _job_yaml("prod-secret-check"), (
        "prod-secret-check does not read SEARCH_EVAL_DB_PASSWORD -- nothing "
        "gates eval-prod on the secret actually being set"
    )
    outputs = gate.get("outputs", {})
    msg = "prod-secret-check must publish has_db_password for eval-prod to gate on"
    assert "has_db_password" in outputs, msg


def test_eval_prod_gates_on_the_environment_scoped_check():
    workflow = _load_workflow()
    eval_prod = workflow["jobs"]["eval-prod"]
    assert "prod-secret-check" in eval_prod["needs"], (
        "eval-prod does not depend on prod-secret-check, so nothing carries "
        "the DB-password precondition"
    )
    assert "needs.prod-secret-check.outputs.has_db_password" in eval_prod["if"], (
        f"eval-prod's `if` is {eval_prod['if']!r}, expected it to gate on "
        "needs.prod-secret-check.outputs.has_db_password"
    )


def test_eval_smoke_is_not_gated_behind_the_environment():
    """eval-smoke needs no prod credential at all. Making it wait on an
    environment-scoped job would let a future environment reviewer or branch
    policy block the one route that is meant to run anywhere."""
    workflow = _load_workflow()
    eval_smoke = workflow["jobs"]["eval-smoke"]
    needs = eval_smoke["needs"]
    needs = [needs] if isinstance(needs, str) else needs
    assert "prod-secret-check" not in needs, (
        "eval-smoke depends on prod-secret-check -- the credential-light "
        "route must not inherit the search-eval environment's gating"
    )
    assert eval_smoke.get("environment") is None


# ---------------------------------------------------------------------------
# The credential has to survive being put into a URL (BITB-101 follow-up).
#
# `api/scripture/database.py` builds its engine at import time, so eval-prod's
# DSN is parsed before the CLI runs a single query. Interpolating a raw
# password into that string means any of :/?#[]@%& in it silently repoints the
# URL (a `/` moves the host, a `#` truncates it) or makes it unparseable --
# the job then dies during import, roughly a second in, with the traceback
# going only to eval-prod.log inside a zip. The password is generated and
# pasted in by an operator, so assuming it is URL-safe is assuming something
# nobody promised.
# ---------------------------------------------------------------------------


def _eval_prod_run_step() -> dict:
    workflow = _load_workflow()
    for step in workflow["jobs"]["eval-prod"]["steps"]:
        if step.get("id") == "run":
            return step
    raise AssertionError("eval-prod has no step with id 'run'")


def test_eval_prod_percent_encodes_the_db_password_into_the_dsn():
    script = _eval_prod_run_step()["run"]
    dsn_lines = [ln for ln in script.splitlines() if "DATABASE_URL=" in ln]
    assert dsn_lines, "eval-prod's run step no longer builds a DATABASE_URL"
    for line in dsn_lines:
        assert "${DB_PASS}" not in line and "$DB_PASS@" not in line, (
            f"eval-prod interpolates the raw password into the DSN ({line.strip()!r}) "
            "-- a password containing :/?#[]@%& mis-parses or crashes at import"
        )
    encode_msg = "eval-prod does not percent-encode DB_PASS before building the DSN"
    assert "urllib.parse.quote" in script, encode_msg
    assert "::add-mask::" in script, (
        "the percent-encoded password is a different string from the secret "
        "GitHub masks, so it must be registered with ::add-mask:: before it "
        "can reach a log line"
    )


def test_eval_prod_prints_its_failure_to_the_console():
    """A failure whose only copy is inside an uploaded zip cannot be read from
    the API, from a phone, or by anything automated -- which is what made run
    33212723774's import crash opaque."""
    workflow = _load_workflow()
    steps = workflow["jobs"]["eval-prod"]["steps"]
    fail_steps = [s for s in steps if "Fail the job" in s.get("name", "")]
    assert fail_steps, "eval-prod has no failure step"
    script = fail_steps[0]["run"]
    assert "eval-prod.log" in script and "tail" in script, (
        "eval-prod's failure step does not print any of eval-prod.log to the "
        "console -- the diagnosis stays locked in the artifact"
    )

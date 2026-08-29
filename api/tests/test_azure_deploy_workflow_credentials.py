"""Guards against the raw-password-in-a-DSN defect BITB-112 fixed.

A Postgres DSN is a URL: `postgresql://user:password@host/db`.  # pragma: allowlist secret
Any of the
characters `:/?#[]@%&` in the password is structural in a URL and does not
error when interpolated raw -- it silently repoints or truncates the URL
instead (`p@ss/w0rd#x` makes the host `ss`). BITB-101's first non-skipped
`eval-prod` run hit exactly this on 2026-08-28 and died at import, 1.5s in,
before a single query; PR #1020 fixed that one site
(`search-eval-full.yml`, guarded by
`test_search_eval_workflow_credentials.py`). This story is the rest: eight
`DATABASE_URL=` sites in `azure-deploy.yml`, one of which is the running
production app's own connection string (`deployment/main.tf`).

The fix at every workflow site is the same treatment PR #1020 used:
percent-encode `DB_PASS` into `DB_PASS_ENC` via `urllib.parse.quote(...,
safe="")`, register the encoded form with `::add-mask::` (GitHub masks the
literal secret, not its percent-encoded variant -- they are different
strings), and interpolate `DB_PASS_ENC` instead of `DB_PASS`.

These tests parse `azure-deploy.yml` and `deployment/main.tf` and assert the
properties that would let the raw-interpolation bug regress silently. A
future edit that reintroduces `${DB_PASS}` directly in a DSN (e.g. "just a
quick debug tweak") would look correct and work fine right up until the
password contains a structural character -- the whole reason this needs a
standing guard rather than a one-time fix.

Adapted from the style of `api/tests/test_search_eval_workflow_credentials.py`.
"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"
_MAIN_TF_PATH = _REPO_ROOT / "deployment" / "main.tf"


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text()


def _load_workflow() -> dict:
    return yaml.safe_load(_workflow_text())


def _run_steps_with_dsn() -> list[tuple[str, str, dict]]:
    """Every (job_name, step_name, step) across the whole workflow whose
    `run` script builds a `DATABASE_URL`."""
    workflow = _load_workflow()
    found = []
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            script = step.get("run") or ""
            if "DATABASE_URL=" in script:
                found.append((job_name, step.get("name", "<unnamed>"), step))
    return found


def test_azure_deploy_has_the_expected_dsn_sites():
    """A sanity floor, not a ceiling: if this drops, either a site was
    removed (update the count) or the workflow structure changed in a way
    the rest of this file should be re-checked against."""
    sites = _run_steps_with_dsn()
    assert len(sites) >= 8, (
        f"found only {len(sites)} DATABASE_URL= sites in azure-deploy.yml, "
        "expected at least 8 -- if a site was legitimately removed, lower "
        "this floor deliberately rather than letting it silently regress"
    )


def test_no_azure_deploy_dsn_interpolates_the_raw_password():
    for job_name, step_name, step in _run_steps_with_dsn():
        script = step["run"]
        dsn_lines = [ln for ln in script.splitlines() if "DATABASE_URL=" in ln]
        for line in dsn_lines:
            assert "${DB_PASS}" not in line and "$DB_PASS@" not in line, (
                f"{job_name}/{step_name!r} interpolates the raw password into "
                f"the DSN ({line.strip()!r}) -- a password containing "
                ":/?#[]@%& mis-parses or breaks the connection silently "
                "(BITB-112)"
            )


def test_every_azure_deploy_dsn_site_percent_encodes_and_masks():
    for job_name, step_name, step in _run_steps_with_dsn():
        script = step["run"]
        assert "urllib.parse.quote" in script, (
            f"{job_name}/{step_name!r} builds a DATABASE_URL but does not "
            "percent-encode DB_PASS first (BITB-112)"
        )
        assert "::add-mask::" in script, (
            f"{job_name}/{step_name!r} percent-encodes the password but never "
            "registers the encoded form with ::add-mask:: -- GitHub only "
            "masks the literal secret value, not its percent-encoded variant, "
            "so the encoded password could reach a log line unmasked"
        )
        assert "DB_PASS_ENC" in script, (
            f"{job_name}/{step_name!r} does not use the encoded DB_PASS_ENC "
            "variable in its DATABASE_URL"
        )


# ---------------------------------------------------------------------------
# `deployment/main.tf`: the running app's own connection string, plus the
# Postgres server resource it must disagree with on purpose.
#
# `DATABASE_URL` (fed to the container as an env var) is a URL and must be
# encoded. `administrator_password` (the server's own credential store) takes
# the value literally and must NOT be encoded -- encoding it there would
# configure the server with a different password than the one operators
# actually set, and than what the (correctly encoded) DATABASE_URL decodes
# back to. These two sites are supposed to differ; a test that only checked
# "is it encoded" everywhere would be as wrong as the original bug in the
# opposite direction.
# ---------------------------------------------------------------------------


def _main_tf_text() -> str:
    return _MAIN_TF_PATH.read_text()


def test_database_url_env_var_percent_encodes_the_password():
    text = _main_tf_text()
    idx = text.index('"DATABASE_URL" = {')
    block = text[idx : idx + 600]
    assert "urlencode(var.db_admin_password)" in block, (
        "deployment/main.tf's DATABASE_URL env var does not urlencode() "
        "var.db_admin_password -- a password containing :/?#[]@%& would "
        "silently repoint the running app's own database connection "
        "(BITB-112)"
    )


def test_administrator_password_stays_literal():
    text = _main_tf_text()
    idx = text.index("administrator_password = var.db_admin_password")
    # The literal assignment must not itself be wrapped in urlencode(): the
    # Postgres server resource wants the raw credential, not a URL-encoded
    # reading of it.
    preceding = text[max(0, idx - 20) : idx]
    assert "urlencode(" not in preceding, (
        "administrator_password appears to be urlencode()'d -- the server's "
        "own credential store must receive the literal password, not a "
        "URL-encoded reading of it, or it disagrees with what DATABASE_URL "
        "decodes back to"
    )

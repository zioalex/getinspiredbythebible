"""BITB-097: DB-side timeout bounds for one-shot migration connections.

A CI job's `timeout-minutes` only kills the *client*. On 2026-08-17 that left
server-side DDL holding an `ACCESS EXCLUSIVE` lock for 15 minutes after the
runner gave up, because Postgres had no `statement_timeout`/`lock_timeout` of
its own to fall back on. The fix is `lock_timeout`/`statement_timeout` set as
session-level GUCs on the migration connection itself, so the database bounds
the work regardless of what happens to the CI runner.

`api/alembic/env.py` is deliberately NOT imported here: Alembic executes it as
a script (it calls `context.is_offline_mode()` / runs migrations at import
time), so importing it in a test process runs migration logic as a side
effect. Its wiring is instead asserted via a source-text check, matching the
pattern `test_deploy_workflow_migrations.py` already uses for the workflow
YAML.
"""

import importlib.util
import re
import ssl
from pathlib import Path

import yaml

from scripture.database import get_migration_server_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_PY_PATH = _REPO_ROOT / "api" / "alembic" / "env.py"
_UTILS_PY_PATH = _REPO_ROOT / "scripts" / "migrations" / "utils.py"
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"


def _load_migration_utils_module():
    """Load `scripts/migrations/utils.py` directly by file path.

    Can't `sys.path.insert` + `import utils`, unlike
    `test_load_bible_data_path.py`'s `scripts/` import: `api/utils/` is
    already an importable package named `utils` (pulled in transitively by
    `scripture.database` above), and it's cached in `sys.modules` by the time
    this module is collected -- a plain `import utils` would silently resolve
    to the wrong package instead of `scripts/migrations/utils.py`. Loading by
    explicit spec under a distinct module name sidesteps the collision
    entirely; the function itself has no import-time side effects (unlike
    `api/alembic/env.py`, see module docstring).
    """
    spec = importlib.util.spec_from_file_location("migration_utils", _UTILS_PY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


get_migration_connection_params = _load_migration_utils_module().get_migration_connection_params


def _guc_duration_to_minutes(value: str) -> float:
    """Parse a Postgres GUC-style duration ('5s', '25min') into minutes.

    Only the two unit suffixes this codebase actually uses are supported --
    this is a regression guard, not a general GUC parser.
    """
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(s|min)", value)
    assert match, f"unrecognized GUC duration format: {value!r}"
    amount, unit = match.groups()
    return float(amount) / 60 if unit == "s" else float(amount)


def test_get_migration_server_settings_returns_expected_guc_keys():
    settings = get_migration_server_settings()
    assert isinstance(settings, dict)
    assert "lock_timeout" in settings
    assert "statement_timeout" in settings
    assert isinstance(settings["lock_timeout"], str)
    assert isinstance(settings["statement_timeout"], str)


def test_get_migration_server_settings_does_not_mutate_app_connect_args():
    """The app's long-lived pooled engine must not inherit a 5s lock_timeout --
    that would misfire on legitimate app queries. This function must be a
    plain, side-effect-free factory, not something that reaches into the
    module-level `_connect_args` used by the app's `engine`."""
    first = get_migration_server_settings()
    first["lock_timeout"] = "mutated"
    second = get_migration_server_settings()
    assert second["lock_timeout"] != "mutated", (
        "get_migration_server_settings() returned a shared/mutable object -- "
        "callers mutating their copy must not affect other callers"
    )


def test_alembic_env_applies_migration_server_settings():
    """Source-text check (not an import -- see module docstring) that
    `run_async_migrations()` actually wires `get_migration_server_settings()`
    into the connect args used for the real (online) migration connection."""
    source = _ENV_PY_PATH.read_text()
    assert "get_migration_server_settings" in source, (
        "api/alembic/env.py does not reference get_migration_server_settings() "
        "-- the online migration connection would run without a DB-side "
        "lock_timeout/statement_timeout (BITB-097)"
    )
    assert "from scripture.database import" in source
    import_line = next(
        line for line in source.splitlines() if line.startswith("from scripture.database import")
    )
    assert "get_migration_server_settings" in import_line, (
        "get_migration_server_settings is referenced but not imported from "
        "scripture.database in api/alembic/env.py"
    )


def test_legacy_migration_utils_sets_server_settings():
    """`scripts/migrations/utils.py` is frozen/legacy (see
    docs/MIGRATION_GUIDELINES.md) and deliberately does not import from
    `scripture.database`, so it needs its own inline copy of the same GUCs."""
    source = _UTILS_PY_PATH.read_text()
    assert "server_settings" in source, (
        "scripts/migrations/utils.py's get_migration_connection_params() does "
        "not set server_settings -- the legacy migration runner's connections "
        "would have no DB-side lock_timeout/statement_timeout (BITB-097)"
    )
    assert "lock_timeout" in source
    assert "statement_timeout" in source


def test_statement_timeout_is_strictly_below_the_job_timeout():
    """The acceptance criterion this exists to guard: `statement_timeout` must
    sit *below* `run-migrations`'s `timeout-minutes`, so the database gives up
    and rolls back cleanly before the runner vanishes and orphans the
    statement (BITB-097, defect 3). A value check, not just key presence --
    someone lowering `timeout-minutes` (or raising `statement_timeout`) below
    this margin must fail loudly here, not surface as a 15-minute stranded
    lock during the next real outage."""
    statement_timeout_minutes = _guc_duration_to_minutes(
        get_migration_server_settings()["statement_timeout"]
    )

    workflow = yaml.safe_load(_WORKFLOW_PATH.read_text())
    job_timeout_minutes = workflow["jobs"]["run-migrations"]["timeout-minutes"]

    assert statement_timeout_minutes < job_timeout_minutes, (
        f"statement_timeout ({statement_timeout_minutes} min) is not strictly "
        f"below run-migrations' timeout-minutes ({job_timeout_minutes} min) -- "
        "a stuck migration would have its CI runner vanish before Postgres "
        "gives up, orphaning the statement under its lock instead of rolling "
        "it back cleanly"
    )


class TestGetMigrationConnectionParamsSsl:
    """BITB-099 regression guard for `scripts/migrations/utils.py`'s
    `get_migration_connection_params()`, mirroring
    `test_database_church_coverage.py::TestGetAsyncDatabaseUrl`'s coverage of
    the sibling `api/scripture/database.py::get_async_database_url()`. Both
    helpers must agree: `require` stays unverified, `verify-ca`/`verify-full`
    verify fully -- production now uses `verify-full`."""

    def test_sslmode_require_still_unverified(self):
        url = "postgresql://user:pass@host/db?sslmode=require"  # pragma: allowlist secret
        clean_url, kwargs = get_migration_connection_params(url)

        assert "sslmode" not in clean_url
        assert "ssl" in kwargs
        ssl_context = kwargs["ssl"]
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert ssl_context.check_hostname is False

    def test_sslmode_verify_ca_is_verified(self):
        url = "postgresql://user:pass@host/db?sslmode=verify-ca"  # pragma: allowlist secret
        clean_url, kwargs = get_migration_connection_params(url)

        assert "sslmode" not in clean_url
        assert "ssl" in kwargs
        ssl_context = kwargs["ssl"]
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname is True

    def test_sslmode_verify_full_is_verified(self):
        """BITB-099: this is the mode production DSNs now use."""
        url = "postgresql://user:pass@host/db?sslmode=verify-full"  # pragma: allowlist secret
        clean_url, kwargs = get_migration_connection_params(url)

        assert "sslmode" not in clean_url
        assert "ssl" in kwargs
        ssl_context = kwargs["ssl"]
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname is True

"""Alembic rollback/round-trip test (BITB-004).

Runs `alembic upgrade head` -> `alembic downgrade base` -> `alembic upgrade head`
against a **throwaway database** created just for this test, then dropped in
teardown. It intentionally does NOT reuse the shared `DATABASE_URL` test
database the way `test_rate_limiter_integration.py` does: `downgrade base`
drops every ORM-backed table, which would wreck any other test running
against the same database. So this test creates its own
`alembic_roundtrip_test_<uuid>` database on the same Postgres server, points
a child process's `DATABASE_URL` at it, and drops it again afterwards.

Mandatory safety guard: parses the host out of `settings.database_url` and
skips unless it resolves to a local/CI database. This makes it structurally
impossible for the test to run `downgrade base` against a real database by
accident, even if someone points DATABASE_URL somewhere unexpected before
running pytest.

The alembic CLI is invoked via `subprocess`, not by importing `env.py`
directly: `env.py`'s `run_migrations_online()` calls `asyncio.run(...)`,
which raises `RuntimeError: asyncio.run() cannot be called from a running
event loop` if invoked from inside pytest-asyncio's own loop.

Skips automatically (does not fail) if Postgres is unreachable or the
connected role lacks CREATEDB privilege -- mirrors the "skip if DB
unreachable" pattern in `test_rate_limiter_integration.py`.

As of BITB-100, this file holds two unrelated concerns. Everything above is
the original DB-backed roundtrip test. Everything at the bottom of the file
is a DB-free, source-text/AST check over the revision files themselves --
it needs no fixture, no Postgres, and runs on every PR whether or not a
database is available. It exists because the connection-level timeouts
BITB-097 added (`get_migration_server_settings()` in
`api/scripture/database.py`, wired into `env.py` and
`scripts/migrations/utils.py`) are not a substitute for a per-revision
`lock_timeout`: that mechanism only applies on the online `env.py` path, so
`alembic upgrade --sql` or a hand-run `psql` migration gets none of it, and
it does not force each author to actually choose a lock budget for their
own revision. See docs/MIGRATION_GUIDELINES.md, "Locking & scale (Alembic
revisions)".
"""

import ast
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg2
import pytest

from config import settings

_API_DIR = Path(__file__).resolve().parents[1]
_VERSIONS_DIR = _API_DIR / "alembic" / "versions"

# Revisions that predate the BITB-100 lock_timeout rule. Frozen at BITB-100 --
# r0001 is the baseline and runs against an empty database; r0002/r0003 are
# COMMENT ON probes behind to_regclass guards. Nothing is ever added to this
# set: a new revision without a lock_timeout is exactly what this test exists
# to catch.
_TIMEOUT_EXEMPT_REVISIONS = frozenset({"r0001", "r0002", "r0003"})

# Opt-in env var for a deliberately non-default host (e.g. a docker-compose
# service name other than the ones below) -- absent by default, so the guard
# fails closed.
_ALLOW_HOST_ENV = "ALEMBIC_TEST_ALLOW_HOST"
_ALLOW_HOST_VALUE = "1"
_SAFE_HOSTS = {"localhost", "127.0.0.1", "postgres", "db"}


def _host_override_enabled() -> bool:
    """True only for an exact `ALEMBIC_TEST_ALLOW_HOST=1`.

    Deliberately not a truthiness check: every non-empty string is truthy in
    Python, so a plain `os.environ.get(...)` would treat `=0`, `=false` and
    `=no` -- the values someone reaches for to turn the override *off* -- as
    turning it *on*, silently disabling the guard in front of a destructive
    operation. Requiring the one value the skip message documents keeps the
    code and the docs in agreement.
    """
    return os.environ.get(_ALLOW_HOST_ENV) == _ALLOW_HOST_VALUE


def _require_local_database_or_skip() -> None:
    """Refuse to run against anything that isn't obviously a local/CI database.

    This test runs `alembic downgrade base`, which drops every ORM-backed
    table. Structurally guarding against a real database is not optional.
    """
    host = urlparse(settings.database_url).hostname
    if host not in _SAFE_HOSTS and not _host_override_enabled():
        pytest.skip(
            f"Refusing to run destructive Alembic roundtrip test against host "
            f"{host!r} (not in {_SAFE_HOSTS}). Set "
            f"{_ALLOW_HOST_ENV}={_ALLOW_HOST_VALUE} to override "
            "for an explicitly-approved non-default local/CI host."
        )


def _base_connection_params() -> dict:
    """psycopg2 connection kwargs for the *administrative* connection used to
    create/drop the throwaway database (connects to the default database on
    the same server as settings.database_url, not the throwaway one)."""
    parsed = urlparse(settings.database_url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        # Connect to the server's default maintenance database, not whatever
        # database DATABASE_URL names -- CREATE/DROP DATABASE cannot run
        # against the database you're connected to.
        "dbname": "postgres",
    }


def _database_url_for(dbname: str) -> str:
    """Return settings.database_url with its path replaced by `dbname`."""
    parsed = urlparse(settings.database_url)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


@pytest.fixture
def throwaway_database_url():
    """Create a uniquely-named throwaway database, yield its URL, drop it after.

    Skips (does not fail) if Postgres is unreachable or CREATE DATABASE fails
    (e.g. the connected role lacks CREATEDB privilege).
    """
    _require_local_database_or_skip()

    db_name = f"alembic_roundtrip_test_{uuid.uuid4().hex[:12]}"

    try:
        admin_conn = psycopg2.connect(**_base_connection_params())
    except Exception as exc:  # connection refused, auth failure, etc.
        pytest.skip(f"Postgres not reachable: {exc}")
        return
    admin_conn.autocommit = True  # CREATE DATABASE cannot run inside a transaction

    try:
        with admin_conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{db_name}"')
    except Exception as exc:
        admin_conn.close()
        pytest.skip(f"Could not CREATE DATABASE (likely missing CREATEDB privilege): {exc}")
        return

    try:
        yield _database_url_for(db_name)
    finally:
        try:
            with admin_conn.cursor() as cur:
                # Terminate any lingering connections (e.g. a leaked asyncpg
                # connection from a failed run) so DROP DATABASE doesn't hang
                # or fail with "database is being accessed by other users".
                try:
                    cur.execute(f'DROP DATABASE "{db_name}" WITH (FORCE)')
                except psycopg2.errors.SyntaxError:
                    # WITH (FORCE) requires Postgres >= 13. Fall back to a
                    # plain DROP for older servers.
                    admin_conn.rollback()
                    cur.execute(f'DROP DATABASE "{db_name}"')
        finally:
            admin_conn.close()


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    """Invoke the alembic CLI as a subprocess against `database_url`.

    Subprocess (not the Python API) because env.py's run_migrations_online()
    calls asyncio.run(), which raises if invoked from inside pytest-asyncio's
    own event loop.
    """
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        # Match the env vars the baseline migration (r0001) was generated
        # with, so Vector(embedding_dimensions) matches what's on disk.
        "EMBEDDING_PROVIDER": "ollama",
        "EMBEDDING_MODEL": "mxbai-embed-large",
        "EMBEDDING_DIMENSIONS": "1024",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_API_DIR),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    # alembic logs its own INFO lines to stderr; only fail on an actual
    # traceback, not on routine logging.
    assert (
        "Traceback (most recent call last)" not in result.stderr
    ), f"alembic {' '.join(args)} printed a traceback:\n{result.stderr}"
    return result


def _head_revision(database_url: str) -> str:
    """The revision id currently at the head of the migration chain.

    Derived from `alembic heads` rather than hardcoded. Pinning the literal
    makes the assertion below fail the moment a second revision is added --
    which is exactly what happened when r0002 landed and this still said
    "r0001". The property worth asserting is "upgrade head leaves the database
    at head", not "the head is called r0001".

    `alembic heads` reads the versions directory and never connects, so the
    database_url only has to satisfy env.py's import-time config.
    """
    result = _run_alembic("heads", database_url=database_url)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"alembic heads printed nothing to stdout:\n{result.stdout!r}"
    assert len(lines) == 1, (
        "Expected exactly one head -- a branched migration history would make "
        f"`upgrade head` ambiguous:\n{result.stdout}"
    )
    return lines[0].split()[0]


def _table_names(database_url: str) -> set[str]:
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def _alembic_version_rows(database_url: str) -> list[str]:
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _role_can_select(database_url: str, table: str) -> bool:
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT has_table_privilege('search_eval_ro', %s, 'SELECT')",
                (table,),
            )
            return bool(cur.fetchone()[0])
    finally:
        conn.close()


_ORM_BACKED_TABLES = {
    "translations",
    "books",
    "chapters",
    "verses",
    "passages",
    "topics",
    "feedback",
    "contact_submissions",
    "blocked_message_samples",
}


def test_upgrade_downgrade_upgrade_roundtrip(throwaway_database_url):
    """Full lifecycle proof: upgrade creates the schema, downgrade removes it
    cleanly, and upgrading again re-creates it (proves re-runnability)."""
    # 1. upgrade head -> all 9 ORM-backed tables exist, alembic_version has
    #    exactly one row.
    _run_alembic("upgrade", "head", database_url=throwaway_database_url)

    tables = _table_names(throwaway_database_url)
    assert _ORM_BACKED_TABLES.issubset(
        tables
    ), f"Missing expected tables after upgrade: {_ORM_BACKED_TABLES - tables}"
    assert "alembic_version" in tables

    version_rows = _alembic_version_rows(throwaway_database_url)
    assert len(version_rows) == 1, f"Expected exactly one alembic_version row, got {version_rows}"
    head = _head_revision(throwaway_database_url)
    assert (
        version_rows[0] == head
    ), f"After `upgrade head` the database should sit at {head}, got {version_rows[0]}"

    # 2. downgrade base -> all 9 ORM-backed tables are gone.
    _run_alembic("downgrade", "base", database_url=throwaway_database_url)

    tables_after_downgrade = _table_names(throwaway_database_url)
    assert not (_ORM_BACKED_TABLES & tables_after_downgrade), (
        f"Tables still present after downgrade base: "
        f"{_ORM_BACKED_TABLES & tables_after_downgrade}"
    )

    # 3. upgrade head again -> tables are back (re-runnability).
    _run_alembic("upgrade", "head", database_url=throwaway_database_url)

    tables_after_reupgrade = _table_names(throwaway_database_url)
    assert _ORM_BACKED_TABLES.issubset(tables_after_reupgrade), (
        f"Missing expected tables after re-upgrade: "
        f"{_ORM_BACKED_TABLES - tables_after_reupgrade}"
    )
    version_rows_after_reupgrade = _alembic_version_rows(throwaway_database_url)
    assert len(version_rows_after_reupgrade) == 1


def test_alembic_check_reports_no_drift(throwaway_database_url):
    """`alembic check` (the read-only command CI actually runs) must pass
    clean immediately after `upgrade head` -- proves the baseline migration
    matches the live ORM metadata exactly (modulo the compare_type=False
    carve-out documented in env.py)."""
    _run_alembic("upgrade", "head", database_url=throwaway_database_url)
    # `alembic check` exits non-zero (raising CalledProcessError, since
    # _run_alembic uses check=True) if it detects pending model changes.
    _run_alembic("check", database_url=throwaway_database_url)


def test_search_eval_topic_grants_upgrade_and_downgrade(throwaway_database_url):
    _run_alembic("upgrade", "r0005", database_url=throwaway_database_url)
    parsed = urlparse(throwaway_database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE verse_topics (verse_id integer REFERENCES verses(id), "
                "topic_id integer REFERENCES topics(id), PRIMARY KEY (verse_id, topic_id))"
            )
        conn.commit()
    finally:
        conn.close()

    _run_alembic("upgrade", "head", database_url=throwaway_database_url)
    assert _role_can_select(throwaway_database_url, "topics")
    assert _role_can_select(throwaway_database_url, "verse_topics")

    _run_alembic("downgrade", "r0005", database_url=throwaway_database_url)
    assert not _role_can_select(throwaway_database_url, "topics")
    assert not _role_can_select(throwaway_database_url, "verse_topics")


class TestHostSafetyGuard:
    """Tests for the guard itself -- the thing standing between
    `alembic downgrade base` and a database nobody meant to touch.

    These need no database: they exercise the pure host/env-var logic that
    decides whether the destructive tests above are allowed to run at all.
    """

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "2", "yes", "true"])
    def test_override_requires_the_exact_documented_value(self, monkeypatch, value):
        """Anything other than `=1` must leave the guard armed.

        Regression: the check used `not os.environ.get(...)`, and every
        non-empty string is truthy in Python -- so `=0`, `=false` and `=no`,
        the values someone picks to mean "off", all turned the override *on*.
        """
        monkeypatch.setenv(_ALLOW_HOST_ENV, value)
        assert _host_override_enabled() is False

    def test_override_enabled_by_exact_value(self, monkeypatch):
        monkeypatch.setenv(_ALLOW_HOST_ENV, _ALLOW_HOST_VALUE)
        assert _host_override_enabled() is True

    def test_override_absent_by_default(self, monkeypatch):
        """Unset means armed -- the guard fails closed."""
        monkeypatch.delenv(_ALLOW_HOST_ENV, raising=False)
        assert _host_override_enabled() is False

    @pytest.mark.parametrize("host", sorted(_SAFE_HOSTS))
    def test_local_hosts_run_without_an_override(self, monkeypatch, host):
        monkeypatch.delenv(_ALLOW_HOST_ENV, raising=False)
        monkeypatch.setattr(settings, "database_url", f"postgresql://{host}:5432/bibledb")
        _require_local_database_or_skip()  # must not raise Skipped

    def test_remote_host_skips_when_override_is_falsy(self, monkeypatch):
        """The exact case the regression allowed through."""
        monkeypatch.setenv(_ALLOW_HOST_ENV, "0")
        monkeypatch.setattr(settings, "database_url", "postgresql://prod.example.com:5432/bibledb")
        with pytest.raises(pytest.skip.Exception):
            _require_local_database_or_skip()

    def test_remote_host_skips_when_override_absent(self, monkeypatch):
        monkeypatch.delenv(_ALLOW_HOST_ENV, raising=False)
        monkeypatch.setattr(settings, "database_url", "postgresql://prod.example.com:5432/bibledb")
        with pytest.raises(pytest.skip.Exception):
            _require_local_database_or_skip()

    def test_remote_host_runs_with_explicit_override(self, monkeypatch):
        """The escape hatch still works for a deliberately-approved CI host."""
        monkeypatch.setenv(_ALLOW_HOST_ENV, _ALLOW_HOST_VALUE)
        monkeypatch.setattr(
            settings, "database_url", "postgresql://ci-postgres.internal:5432/bibledb"
        )
        _require_local_database_or_skip()  # must not raise Skipped


# ---------------------------------------------------------------------------
# BITB-100: DB-free source-text/AST checks over the revision files.
#
# Nothing below this line touches a database or uses the fixtures above --
# these run on every PR, with or without Postgres available.
# ---------------------------------------------------------------------------


def _revision_files() -> list[Path]:
    """All revision files under api/alembic/versions/, sorted by filename.

    Asserts non-empty: a glob that starts matching nothing (e.g. the
    versions directory moves, or the naming convention changes) must fail
    this test loudly rather than silently turning the parametrized test
    below into a no-op that always "passes".
    """
    files = sorted(_VERSIONS_DIR.glob("r*.py"))
    assert files, f"No revision files found under {_VERSIONS_DIR} -- glob pattern broken?"
    return files


def _revision_id(source: str) -> str:
    """The module-level `revision: str = "..."` value from a revision file's source."""
    tree = ast.parse(source)
    for node in ast.iter_child_nodes(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "revision"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise AssertionError(
        "No module-level `revision: str = ...` assignment found -- every "
        "Alembic revision file must declare one."
    )


def _upgrade_reaches_lock_timeout(source: str) -> bool:
    """True if `upgrade()` -- or a top-level helper function it calls,
    transitively -- contains the string "lock_timeout" in its own source.

    Parses `source` with `ast` and collects every top-level `FunctionDef` by
    name (asserting `upgrade` is among them), then walks the call graph
    starting at `upgrade()`: for each function currently being examined,
    `ast.walk` it for `Call` nodes whose `func` is a plain `Name` matching
    another known top-level function, and enqueue that function too
    (tracking visited names so recursion can't loop forever).

    For every function reached this way, the check is a source-text search
    within *that function's own source* (via `ast.get_source_segment`), not
    the whole file. That's what makes this correctly find a `lock_timeout`
    set inside a helper called from `upgrade()` -- r0004's actual shape --
    while correctly rejecting a revision where `lock_timeout` only appears
    inside `downgrade()`, which `upgrade()` never calls.
    """
    tree = ast.parse(source)
    functions_by_name = {
        node.name: node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef)
    }
    assert "upgrade" in functions_by_name, "Revision has no top-level upgrade() function"

    visited: set[str] = set()
    queue = ["upgrade"]
    while queue:
        name = queue.pop()
        if name in visited:
            continue
        visited.add(name)
        fn = functions_by_name.get(name)
        if fn is None:
            continue

        fn_source = ast.get_source_segment(source, fn) or ""
        if "lock_timeout" in fn_source:
            return True

        for call_node in ast.walk(fn):
            if (
                isinstance(call_node, ast.Call)
                and isinstance(call_node.func, ast.Name)
                and call_node.func.id in functions_by_name
                and call_node.func.id not in visited
            ):
                queue.append(call_node.func.id)

    return False


_REVISION_FILES = _revision_files()


@pytest.mark.parametrize("revision_file", _REVISION_FILES, ids=[p.stem for p in _REVISION_FILES])
def test_revision_upgrade_sets_lock_timeout(revision_file):
    """Every revision not in `_TIMEOUT_EXEMPT_REVISIONS` must bound itself
    with a `lock_timeout` reachable from `upgrade()`.

    Pure source-text/AST check -- no database required, runs on every PR.
    """
    source = revision_file.read_text()
    revision_id = _revision_id(source)

    if revision_id in _TIMEOUT_EXEMPT_REVISIONS:
        pytest.skip(
            f"{revision_id} predates the BITB-100 lock_timeout rule and is in "
            f"the frozen exemption list _TIMEOUT_EXEMPT_REVISIONS "
            f"({sorted(_TIMEOUT_EXEMPT_REVISIONS)})."
        )

    assert _upgrade_reaches_lock_timeout(source), (
        f"{revision_file.name}: upgrade() does not reach a `lock_timeout` call.\n\n"
        "WHY THIS MATTERS: the 2026-08-17 tsvector migration outage (see "
        "docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md) ran an "
        "unbounded ALTER TABLE that held its lock for 45 minutes -- CI's own "
        "`timeout-minutes` killed the client, not the server-side DDL, which kept "
        "the lock working toward a COMMIT that could never arrive. Every revision "
        "now has to bound itself from inside the database.\n\n"
        "HOW TO FIX: copy the `_set_timeouts()` helper from "
        "api/alembic/versions/r0004_add_verse_tsv_side_table.py (SET LOCAL "
        "lock_timeout / statement_timeout) and call it from the top of "
        "upgrade(). See docs/MIGRATION_GUIDELINES.md, "
        "'Locking & scale (Alembic revisions)'."
    )


def test_timeout_exempt_revisions_still_exist():
    """Guards against the exemption set silently becoming permanent if a
    revision it names is renamed or removed -- every id in
    `_TIMEOUT_EXEMPT_REVISIONS` must resolve to an actual file."""
    revision_ids = {_revision_id(f.read_text()) for f in _REVISION_FILES}
    missing = _TIMEOUT_EXEMPT_REVISIONS - revision_ids
    assert not missing, (
        f"_TIMEOUT_EXEMPT_REVISIONS references revision id(s) with no matching "
        f"file under {_VERSIONS_DIR}: {sorted(missing)}. If a revision was "
        "renamed or removed, update the exemption set to match."
    )


class TestUpgradeReachesLockTimeout:
    """Unit tests for `_upgrade_reaches_lock_timeout` against inline source
    strings -- no files, no database, no fixtures."""

    def test_lock_timeout_set_directly_in_upgrade(self):
        source = """
def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("CREATE TABLE foo (id integer)")
"""
        assert _upgrade_reaches_lock_timeout(source) is True

    def test_lock_timeout_set_in_helper_called_from_upgrade(self):
        """Mirrors r0004's actual shape: a module-level helper does the
        `SET LOCAL`, and `upgrade()` just calls it."""
        source = """
def _set_timeouts():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '10min'")


def upgrade():
    _set_timeouts()
    op.execute("CREATE TABLE foo (id integer)")
"""
        assert _upgrade_reaches_lock_timeout(source) is True

    def test_no_lock_timeout_anywhere(self):
        source = """
def upgrade():
    op.execute("CREATE TABLE foo (id integer)")


def downgrade():
    op.execute("DROP TABLE foo")
"""
        assert _upgrade_reaches_lock_timeout(source) is False

    def test_lock_timeout_only_in_downgrade_does_not_count(self):
        source = """
def upgrade():
    op.execute("CREATE TABLE foo (id integer)")


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("DROP TABLE foo")
"""
        assert _upgrade_reaches_lock_timeout(source) is False


def test_app_code_never_calls_create_all():
    """BITB-090: Alembic is the only schema authority.

    A `metadata.create_all` anywhere in the app source re-creates the
    two-authorities bug this story removed: a table could appear in the
    database on next boot with no revision and no `alembic_version` change.
    Pure source-text check -- no database required, runs on every PR.

    `api/tests/` and `api/alembic/versions/` are exempt: test fixtures that
    build an isolated throwaway schema (e.g. `test_weekly_report_integration.py`)
    are not a competing authority over the app's real schema, and Alembic's own
    baseline revision necessarily calls `create_all`-equivalent DDL by hand.
    """
    offenders = []
    for path in _API_DIR.rglob("*.py"):
        if _API_DIR / "tests" in path.parents or _API_DIR / "alembic" in path.parents:
            continue
        if "metadata.create_all" in path.read_text():
            offenders.append(str(path.relative_to(_API_DIR)))

    assert not offenders, (
        f"metadata.create_all() found outside api/tests/ and api/alembic/: {offenders}\n"
        "Schema creation is Alembic's job (BITB-090) -- add a revision instead."
    )

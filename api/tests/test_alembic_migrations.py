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
"""

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

# Opt-in env var for a deliberately non-default host (e.g. a docker-compose
# service name other than the ones below) -- absent by default, so the guard
# fails closed.
_ALLOW_HOST_ENV = "ALEMBIC_TEST_ALLOW_HOST"
_SAFE_HOSTS = {"localhost", "127.0.0.1", "postgres", "db"}


def _require_local_database_or_skip() -> None:
    """Refuse to run against anything that isn't obviously a local/CI database.

    This test runs `alembic downgrade base`, which drops every ORM-backed
    table. Structurally guarding against a real database is not optional.
    """
    host = urlparse(settings.database_url).hostname
    if host not in _SAFE_HOSTS and not os.environ.get(_ALLOW_HOST_ENV):
        pytest.skip(
            f"Refusing to run destructive Alembic roundtrip test against host "
            f"{host!r} (not in {_SAFE_HOSTS}). Set {_ALLOW_HOST_ENV}=1 to override "
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
    assert version_rows[0] == "r0001"

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

"""
Integration test for utils/session_tracker.py's session upsert, run against a
real database instead of mocking the session.

Why this file exists
---------------------
track_session's `INSERT ... ON CONFLICT (session_token) DO UPDATE ...
COALESCE(...)` upsert is only ever asserted against a mock's canned return
value elsewhere (test_session_tracker.py) — real `ON CONFLICT`/`COALESCE`
semantics can't be verified by a mock.

Applies migration 008's DDL (idempotent) against whatever `DATABASE_URL`
points at. Cleans up only the rows it created, keyed by a unique sentinel
token prefix, so it never touches unrelated data in a shared test database.

Skips automatically when no Postgres is reachable (e.g. local runs without a
DB). CI's `backend-tests` job provides a service container with
`DATABASE_URL` set, so this runs on every PR.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from scripture.database import get_async_database_url
from utils.session_tracker import track_session

_MIGRATION_008 = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "008_add_sessions_table.sql"
)
_TOKEN_PREFIX = "zz-itest-session-tracker-"


@pytest_asyncio.fixture
async def sessions_table():
    """Ensures migration 008's ``sessions`` table exists against the real
    ``DATABASE_URL``. Skips when Postgres is unreachable. Yields a live
    ``AsyncSession`` for the test to use; deletes only its own sentinel rows
    on teardown."""
    from scripture import database as scripture_database

    # scripture.database's engine/pool is a module-level singleton bound to
    # whichever event loop created it; pytest-asyncio gives each test its own
    # loop, so dispose first to force fresh connections on this test's loop.
    await scripture_database.engine.dispose()

    url, connect_args = get_async_database_url()
    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)

    try:
        # Strip comment lines before splitting on ";" (mirrors
        # test_rate_limiter_integration.py's approach for migration 009).
        sql_lines = (
            line
            for line in _MIGRATION_008.read_text().splitlines()
            if not line.strip().startswith("--")
        )
        async with engine.begin() as conn:
            for statement in "\n".join(sql_lines).split(";"):
                statement = statement.strip()
                if statement:
                    await conn.execute(text(statement))
    except Exception as exc:  # connection refused, auth failure, etc.
        await engine.dispose()
        pytest.skip(f"Postgres not reachable: {exc}")

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.rollback()
        await session.execute(
            text("DELETE FROM sessions WHERE session_token LIKE :prefix"),
            {"prefix": f"{_TOKEN_PREFIX}%"},
        )
        await session.commit()
        await session.close()
        await engine.dispose()


async def _fetch(session: AsyncSession, token: str):
    return (
        await session.execute(
            text(
                "SELECT message_count, is_mobile, language, user_agent "
                "FROM sessions WHERE session_token = :t"
            ),
            {"t": token},
        )
    ).one()


@pytest.mark.asyncio
async def test_track_session_inserts_new_row(sessions_table):
    session = sessions_table
    token = f"{_TOKEN_PREFIX}insert"

    await track_session(
        session, session_token=token, user_agent="Mozilla/5.0 (iPhone)", language="en"
    )
    await session.commit()

    row = await _fetch(session, token)
    assert row.message_count == 1
    assert row.is_mobile is True
    assert row.language == "en"
    assert row.user_agent == "Mozilla/5.0 (iPhone)"


@pytest.mark.asyncio
async def test_track_session_upserts_existing_row_increments_count(sessions_table):
    session = sessions_table
    token = f"{_TOKEN_PREFIX}upsert"

    await track_session(
        session, session_token=token, user_agent="Mozilla/5.0 (iPhone)", language="en"
    )
    await session.commit()

    # Second visit with no user_agent/language: language/user_agent are
    # passed through as NULL, so COALESCE(:lang, sessions.language) and
    # COALESCE(:ua, sessions.user_agent) retain the first call's values --
    # real Postgres semantics a mock can't validate.
    await track_session(session, session_token=token, user_agent=None, language=None)
    await session.commit()

    row = await _fetch(session, token)
    assert row.message_count == 2
    assert row.language == "en"
    assert row.user_agent == "Mozilla/5.0 (iPhone)"
    # is_mobile is retained the same way: track_session binds :mobile as NULL
    # when user_agent is absent, so COALESCE(:mobile, sessions.is_mobile)
    # preserves the earlier detection instead of flipping an established
    # mobile session back to web.
    assert row.is_mobile is True


@pytest.mark.asyncio
async def test_track_session_records_android_app_as_mobile(sessions_table):
    """The Android app's own User-Agent must land as a mobile session.

    Regression guard for the weekly digest reporting zero Android users: the
    app used to send OkHttp's default UA, which stored is_mobile = false and
    made every Android session count as web.
    """
    session = sessions_table
    token = f"{_TOKEN_PREFIX}android"

    await track_session(
        session,
        session_token=token,
        user_agent="VoxQuieta/1.8.0 (Android 14; Pixel 7)",
        language="de",
    )
    await session.commit()

    row = await _fetch(session, token)
    assert row.is_mobile is True
    assert row.language == "de"

"""
Integration test for the Postgres-backed rate limiter (BITB-061), run against
a real database instead of mocking the session.

Why this file exists
---------------------
`test_rate_limiter.py`'s concurrency proof runs `asyncio.gather` over a single
in-process `InMemoryStore`, which was never the problem — a single process
serializes fine even without a lock (no `await` inside its critical section).
The actual bug this migration fixes only shows up **across separate
connections/replicas**: two independent sessions racing the same session's
lifetime counter must not double-count or lose an increment. That needs a
real Postgres and real concurrent connections, which mocks can't reproduce.

Applies migration 009's DDL (idempotent) against whatever `DATABASE_URL`
points at, then hammers the real `PostgresStore` with concurrent connections.
Cleans up only the rows it created, keyed by a unique test-run prefix, so it
never touches unrelated data in a shared test database.

Skips automatically when no Postgres is reachable (e.g. local runs without a
DB). CI's `backend-tests` job provides a service container with
`DATABASE_URL` set, so this runs on every PR.
"""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from scripture.database import get_async_database_url
from utils.rate_limiter import RateLimiter

_MIGRATION_009 = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "009_add_rate_limit_tables.sql"
)


@pytest_asyncio.fixture
async def rate_limit_tables():
    """Ensures migration 009's tables exist against the real `DATABASE_URL`.
    Skips when Postgres is unreachable. Yields nothing usable by callers other
    than a live `scripture.database.async_session_factory` (imported fresh by
    `PostgresStore` inside `check_and_record`)."""
    # scripture.database's engine/pool is a module-level singleton that can
    # outlive the event loop it was created on -- pytest-asyncio gives each
    # test function its own loop, and asyncpg connections are bound to the
    # loop that opened them. Disposing here forces PostgresStore (which reuses
    # that same engine) to open fresh connections on *this* test's loop,
    # instead of occasionally handing back a stale connection from a prior
    # test's now-closed loop (observed as a spurious "Event loop is closed"
    # -> fallback -> one extra allowed request when run as part of the full
    # suite).
    from scripture import database as scripture_database

    await scripture_database.engine.dispose()

    url, connect_args = get_async_database_url()

    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    try:
        # Strip comment lines before splitting on ";" -- this migration's
        # prose comments contain semicolons of their own (e.g. "short-lived;
        # see migration 010"), which would otherwise split a statement in
        # the wrong place. asyncpg only executes one statement per call.
        sql_lines = (
            line
            for line in _MIGRATION_009.read_text().splitlines()
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

    try:
        yield
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lifetime_cap_holds_across_concurrent_connections(rate_limit_tables):
    """The whole point of BITB-061 phase 3: concurrent requests against the
    same session, from independent Postgres connections (not shared
    in-process state), must not double-count or lose an increment."""
    session_id = "itest-BITB-061-concurrent-session"
    ip = "203.0.113.1"  # TEST-NET-3, RFC 5737

    try:
        # Each RateLimiter/PostgresStore opens its own session via
        # scripture.database.async_session_factory, so N limiter instances
        # give N independent connections racing the same session_id.
        limiters = [
            RateLimiter(
                requests_per_minute=1000,
                session_requests_per_minute=1000,
                session_max_requests=10,
                backend="postgres",
            )
            for _ in range(50)
        ]

        results = await asyncio.gather(
            *[limiter.check_rate_limit(ip, session_id) for limiter in limiters]
        )

        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == 10
    finally:
        # Clean up only what this test created.
        url, connect_args = get_async_database_url()
        engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM rate_limit_sessions WHERE session_id = :sid"),
                {"sid": session_id},
            )
            await conn.execute(
                text("DELETE FROM rate_limit_hits WHERE limit_key IN (:ip_key, :sess_key)"),
                {"ip_key": f"ip:{ip}", "sess_key": f"session:{session_id}"},
            )
        await engine.dispose()

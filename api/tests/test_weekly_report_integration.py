"""
Integration test that runs ``build_weekly_report`` against a live Postgres
instead of mocking ``db.execute``.

Why this file exists
--------------------
The weekly digest broke in production twice in ways mocks cannot catch:

* The production database predates the ``sessions`` table (it was only in
  ``scripts/init.sql``, never a migration), so the engagement queries failed
  with ``UndefinedTable`` and the endpoint returned 500.
* The first fix (PR #811) caught the error but did not roll back the aborted
  transaction, so the *next* query died with ``InFailedSQLTransaction`` — an
  error state that only exists on a real connection, which is exactly what the
  mock-based tests in ``test_weekly_report.py`` could not reproduce.

These tests run the builder in an isolated schema, first *without* a
``sessions`` table (must fall back to zero engagement, not raise) and then
*with* it, created from the real migration file so the DDL is exercised too.

Skips automatically when no Postgres is reachable (e.g. local runs without a
DB). CI's ``backend-tests`` job provides a service container with
``DATABASE_URL`` set, so these run on every PR.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from feedback.models import Base, ContactSubmission, Feedback
from reports.weekly_report import build_weekly_report
from scripture.database import get_async_database_url

# Dedicated schema so the test never touches (or depends on) real tables.
_SCHEMA = "zz_weekly_report_itest"

_MIGRATION_008 = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "008_add_sessions_table.sql"
)


@pytest_asyncio.fixture
async def reporting_session():
    """An ``AsyncSession`` whose search_path is an isolated, empty schema
    containing only the ``feedback`` and ``contact_submissions`` tables —
    deliberately *no* ``sessions`` table. Skips when Postgres is unreachable."""
    url, connect_args = get_async_database_url()

    setup_engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    try:
        async with setup_engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE"))
            await conn.execute(text(f"CREATE SCHEMA {_SCHEMA}"))
    except Exception as exc:  # connection refused, auth failure, etc.
        await setup_engine.dispose()
        pytest.skip(f"Postgres not reachable: {exc}")

    # search_path is set at the connection level (server_settings) rather than
    # via ``SET`` so the rollback inside build_weekly_report cannot revert it.
    schema_connect_args = {
        **connect_args,
        "server_settings": {"search_path": _SCHEMA},
    }
    engine = create_async_engine(url, poolclass=NullPool, connect_args=schema_connect_args)

    # BITB-090 removed create_all() as *the app's* schema authority, but this fixture
    # isn't that: it builds two tables inside a throwaway `zz_weekly_report_itest`
    # schema specifically so it deliberately lacks `sessions` (the report's "no
    # session data" path needs that absence). Alembic targets the public schema
    # only, so it cannot stand in here without duplicating the tables it doesn't
    # want. No competing authority over the app's real schema is created.
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Feedback.__table__, ContactSubmission.__table__],
        )

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
        async with setup_engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE"))
        await setup_engine.dispose()


@pytest.mark.asyncio
async def test_build_report_survives_missing_sessions_table(reporting_session: AsyncSession):
    """Regression for the production 500: with no ``sessions`` table, the
    builder must fall back to zero engagement and still complete the
    remaining queries on the same (rolled-back) session."""
    await reporting_session.execute(
        text(
            "INSERT INTO feedback (message_id, rating, created_at)"
            " VALUES (gen_random_uuid(), 'positive', NOW() - INTERVAL '1 day'),"
            "        (gen_random_uuid(), 'negative', NOW() - INTERVAL '2 days'),"
            "        (gen_random_uuid(), 'positive', NOW() - INTERVAL '10 days')"
        )
    )
    await reporting_session.commit()

    report = await build_weekly_report(reporting_session)

    assert report.feedback.total == 2
    assert report.feedback.positive == 1
    assert report.feedback.negative == 1
    # Ran after the failed sessions query — proves the transaction was usable.
    assert report.feedback_total_prev == 1
    assert report.engagement.active_sessions == 0
    assert report.engagement.top_languages == []
    assert report.new_sessions_prev == 0


@pytest.mark.asyncio
async def test_build_report_with_sessions_table_from_migration(reporting_session: AsyncSession):
    """With the ``sessions`` table created from the real migration 008 DDL,
    the engagement queries run for real and count seeded sessions."""
    # asyncpg runs one statement per execute, so apply the file statement-wise.
    for statement in _MIGRATION_008.read_text().split(";"):
        if statement.strip():
            await reporting_session.execute(text(statement))
    await reporting_session.execute(
        text(
            "INSERT INTO sessions"
            " (session_token, created_at, last_activity, message_count, language, is_mobile)"
            " VALUES"
            " ('web-1', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 hour', 5, 'en', FALSE),"
            " ('mob-1', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 hours', 3, 'it', TRUE),"
            " ('old-1', NOW() - INTERVAL '30 days', NOW() - INTERVAL '20 days', 9, 'en', FALSE)"
        )
    )
    await reporting_session.commit()

    report = await build_weekly_report(reporting_session)

    assert report.engagement.active_sessions == 2
    assert report.engagement.new_sessions == 2
    assert report.engagement.total_messages == 8
    assert report.engagement.web_sessions == 1
    assert report.engagement.mobile_sessions == 1
    assert {lc.language for lc in report.engagement.top_languages} == {"en", "it"}


@pytest.mark.asyncio
async def test_build_report_read_aloud_section_with_real_table(reporting_session: AsyncSession):
    """BITB-247: with ``tts_event_daily`` present the funnel is aggregated from real rows
    (7 UTC days, upsert-incremented counts), and old rows fall outside the window."""
    from feedback.models import TtsEventDaily
    from utils.tts_events import build_tts_event_upsert

    await reporting_session.run_sync(
        lambda sync_session: Base.metadata.create_all(
            sync_session.connection(), tables=[TtsEventDaily.__table__]
        )
    )
    from datetime import UTC, datetime, timedelta

    today = datetime.now(UTC).date()
    dims = {"locale": "en", "platform": "web", "browser": "safari", "os": "ios"}
    for event, times in (("tts_started", 3), ("tts_completed", 2), ("tts_error", 1)):
        for _ in range(times):  # repeated upserts must increment, not duplicate
            await reporting_session.execute(build_tts_event_upsert(day=today, event=event, **dims))
    await reporting_session.execute(
        build_tts_event_upsert(day=today - timedelta(days=30), event="tts_started", **dims)
    )
    await reporting_session.commit()

    report = await build_weekly_report(reporting_session)

    assert report.tts.available is True
    assert report.tts.totals["tts_started"] == 3  # the 30-day-old row is outside the window
    assert report.tts.totals["tts_completed"] == 2
    assert report.tts.totals["tts_error"] == 1
    assert report.tts.completion_rate == pytest.approx(2 / 3)
    assert [(p.browser, p.os, p.failures) for p in report.tts.top_failures] == [
        ("safari", "ios", 1)
    ]


@pytest.mark.asyncio
async def test_build_report_tolerates_missing_tts_table_on_real_connection(
    reporting_session: AsyncSession,
):
    """BITB-247: the fixture schema has no ``tts_event_daily``; the report must roll back and
    fall back to an unavailable section instead of raising."""
    report = await build_weekly_report(reporting_session)
    assert report.tts.available is False
    assert report.tts.totals["tts_started"] == 0

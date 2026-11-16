"""
BITB-329: retention sweep for feedback and contact-form data.

Two layers:

* DB-free tests (always run): error handling, settings validation, policy <-> settings tie.
* Real-database tests: rows with controlled ``created_at`` against a throwaway Postgres
  database (only the feedback tables are created -- no pgvector needed). They skip, never
  fail, when no local/CI Postgres is reachable, using the same safety guard as
  ``test_alembic_migrations.py``.
"""

import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse, urlunparse

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import Settings, settings
from feedback import retention
from feedback.models import Base, ContactSubmission, Feedback
from feedback.retention import purge_expired_feedback

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def _ago(days: float, extra_seconds: int = 0) -> datetime:
    return NOW - timedelta(days=days, seconds=extra_seconds)


# --------------------------------------------------------------------------- DB-free


class TestSettingsValidation:
    def test_defaults_match_the_privacy_policy(self):
        s = Settings()
        assert (s.feedback_text_retention_days, s.feedback_retention_days) == (30, 90)
        assert s.contact_retention_days == 90

    @pytest.mark.parametrize(
        "text,row",
        [(1, 1), (1, 3650), (30, 90), (90, 90)],
    )
    def test_valid_feedback_windows(self, text, row):
        s = Settings(feedback_text_retention_days=text, feedback_retention_days=row)
        assert (s.feedback_text_retention_days, s.feedback_retention_days) == (text, row)

    @pytest.mark.parametrize(
        "text,row",
        [(0, 90), (-1, 90), (91, 90), (30, 3651), (3651, 3651), (1, 0)],
    )
    def test_invalid_feedback_windows_rejected(self, text, row):
        with pytest.raises(ValidationError):
            Settings(feedback_text_retention_days=text, feedback_retention_days=row)

    @pytest.mark.parametrize("days", [1, 90, 3650])
    def test_valid_contact_window(self, days):
        assert Settings(contact_retention_days=days).contact_retention_days == days

    @pytest.mark.parametrize("days", [0, -5, 3651])
    def test_invalid_contact_window_rejected(self, days):
        with pytest.raises(ValidationError):
            Settings(contact_retention_days=days)

    def test_env_manifest_documents_the_settings(self):
        manifest = (
            Path(__file__).resolve().parents[2] / "scripts" / "env-manifest.yaml"
        ).read_text()
        for name in (
            "FEEDBACK_TEXT_RETENTION_DAYS",
            "FEEDBACK_RETENTION_DAYS",
            "CONTACT_RETENTION_DAYS",
        ):
            assert re.search(rf"^  {name}:\n    required_in: none", manifest, re.M)


class TestSweepNeverRaises:
    async def test_import_error_returns_zero_counts(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "scripture.database", None)
        assert await purge_expired_feedback() == {
            "feedback_text_cleared": 0,
            "feedback_deleted": 0,
            "contacts_deleted": 0,
        }

    async def test_failing_step_is_rolled_back_swallowed_and_logged_without_text(self, caplog):
        db = MagicMock()
        db.execute = AsyncMock(side_effect=RuntimeError("connection dropped: SECRET-TEXT"))
        db.rollback = AsyncMock()
        factory = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=db)
        cm.__aexit__ = AsyncMock(return_value=False)
        factory.return_value = cm

        with patch("scripture.database.async_session_factory", factory):
            counts = await purge_expired_feedback(NOW)

        assert counts == {"feedback_text_cleared": 0, "feedback_deleted": 0, "contacts_deleted": 0}
        assert db.rollback.await_count == 3  # one per step; later steps still ran
        assert "SECRET-TEXT" not in caplog.text


class TestPolicyNumbersTiedToSettings:
    """The privacy policy quotes the settings' numbers in every language."""

    POLICY_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "legal"

    def _policies(self):
        files = sorted(self.POLICY_DIR.glob("privacy-policy*.md"))
        assert len(files) == 11
        return files

    def test_every_policy_states_the_configured_retention_numbers(self):
        text_days = settings.feedback_text_retention_days
        row_days = settings.feedback_retention_days
        contact_days = settings.contact_retention_days
        for path in self._policies():
            body = path.read_text(encoding="utf-8")
            for days in {text_days, row_days, contact_days}:
                assert re.search(
                    rf"(?<!\d){days}(?!\d)", body
                ), f"{path.name} does not mention {days} days"
            # The feedback and contact sections carry the numbers together with the data kind.
            assert "SMTP2GO" in body, f"{path.name} does not disclose SMTP2GO"

    def test_policy_and_settings_agree_on_the_default_windows(self):
        """Changing a retention default must come with a policy edit (and vice versa)."""
        assert (
            settings.feedback_text_retention_days,
            settings.feedback_retention_days,
            settings.contact_retention_days,
        ) == (30, 90, 90)


# ----------------------------------------------------------------------- real database

_SAFE_HOSTS = {"localhost", "127.0.0.1", "postgres", "db"}


@pytest.fixture
def retention_session_factory():
    import psycopg2

    parsed = urlparse(settings.database_url)
    if parsed.hostname not in _SAFE_HOSTS:
        pytest.skip(f"Refusing to create a database on host {parsed.hostname!r}")
    admin = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "dbname": "postgres",
    }
    try:
        conn = psycopg2.connect(**admin)
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
        return
    conn.autocommit = True
    name = f"feedback_retention_{uuid.uuid4().hex[:12]}"
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{name}"')
    except Exception as exc:
        conn.close()
        pytest.skip(f"Could not CREATE DATABASE: {exc}")
        return

    path_url = urlunparse(parsed._replace(path=f"/{name}", query=""))
    sync_url = path_url.replace(parsed.scheme + "://", "postgresql+psycopg2://", 1)
    async_url = path_url.replace(parsed.scheme + "://", "postgresql+asyncpg://", 1)
    sync_engine = create_engine(sync_url)
    async_engine = create_async_engine(async_url)
    try:
        Base.metadata.create_all(sync_engine)
        yield async_sessionmaker(async_engine, expire_on_commit=False), sync_engine
    finally:
        sync_engine.dispose()
        with conn.cursor() as cur:
            cur.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        conn.close()


def _feedback(created_at: datetime, **overrides) -> Feedback:
    base = dict(
        message_id=uuid.uuid4(),
        rating="negative",
        session_id="a" * 64,
        comment="a comment",
        user_message="a question",
        assistant_response="an answer",
        reason="inaccurate",
        created_at=created_at,
    )
    base.update(overrides)
    return Feedback(**base)


def _contact(created_at: datetime) -> ContactSubmission:
    return ContactSubmission(
        subject="bug",
        message="hello",
        email="a@example.com",
        created_at=created_at,
    )


async def _run(factory, now=NOW):
    with patch("scripture.database.async_session_factory", factory):
        return await purge_expired_feedback(now)


def _fetch(sync_engine, model):
    from sqlalchemy.orm import Session

    with Session(sync_engine) as s:
        return {r.id: r for r in s.execute(select(model)).scalars()}


class TestSweepAgainstRealDatabase:
    async def test_text_cleared_at_30_days_and_not_before(self, retention_session_factory):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            young = _feedback(_ago(29, 3600))  # 29d 1h
            old = _feedback(_ago(30, 60))  # 30d 1min
            s.add_all([young, old])
            s.commit()
            young_id, old_id = young.id, old.id

        counts = await _run(factory)

        rows = _fetch(engine, Feedback)
        assert rows[young_id].user_message == "a question"
        assert rows[young_id].comment == "a comment"
        assert rows[old_id].user_message is None
        assert rows[old_id].assistant_response is None
        assert rows[old_id].comment is None
        # the non-text part of the old row survives until 90 days
        assert rows[old_id].rating == "negative"
        assert rows[old_id].reason == "inaccurate"
        assert rows[old_id].session_id == "a" * 64
        assert counts["feedback_text_cleared"] == 1
        assert counts["feedback_deleted"] == 0

    async def test_feedback_rows_deleted_at_90_days_and_not_before(self, retention_session_factory):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            keep = _feedback(_ago(89, 3600))
            drop = _feedback(_ago(90, 60))
            s.add_all([keep, drop])
            s.commit()
            keep_id, drop_id = keep.id, drop.id

        counts = await _run(factory)

        rows = _fetch(engine, Feedback)
        assert keep_id in rows and drop_id not in rows
        assert counts["feedback_deleted"] == 1

    async def test_contacts_deleted_at_90_days_and_not_before(self, retention_session_factory):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            keep = _contact(_ago(89, 3600))
            drop = _contact(_ago(90, 60))
            s.add_all([keep, drop])
            s.commit()
            keep_id, drop_id = keep.id, drop.id

        counts = await _run(factory)

        rows = _fetch(engine, ContactSubmission)
        assert keep_id in rows and drop_id not in rows
        assert rows[keep_id].message == "hello" and rows[keep_id].email == "a@example.com"
        assert counts["contacts_deleted"] == 1

    async def test_young_rows_untouched_and_created_at_never_changes(
        self, retention_session_factory
    ):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            fb = _feedback(_ago(1))
            old = _feedback(_ago(45))
            ct = _contact(_ago(1))
            s.add_all([fb, old, ct])
            s.commit()
            before = {fb.id: fb.created_at, old.id: old.created_at}
            ct_before = ct.created_at

        counts = await _run(factory)

        rows = _fetch(engine, Feedback)
        assert {i: r.created_at for i, r in rows.items()} == before
        assert rows[fb.id].user_message == "a question"
        assert next(iter(_fetch(engine, ContactSubmission).values())).created_at == ct_before
        assert counts == {"feedback_text_cleared": 1, "feedback_deleted": 0, "contacts_deleted": 0}

    async def test_sweep_is_idempotent(self, retention_session_factory):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            s.add_all([_feedback(_ago(45)), _feedback(_ago(120)), _contact(_ago(120))])
            s.commit()

        first = await _run(factory)
        second = await _run(factory)

        assert first == {"feedback_text_cleared": 1, "feedback_deleted": 1, "contacts_deleted": 1}
        assert second == {"feedback_text_cleared": 0, "feedback_deleted": 0, "contacts_deleted": 0}

    async def test_settings_are_respected(self, retention_session_factory, monkeypatch):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        monkeypatch.setattr(settings, "feedback_text_retention_days", 5)
        monkeypatch.setattr(settings, "feedback_retention_days", 10)
        monkeypatch.setattr(settings, "contact_retention_days", 20)
        with Session(engine) as s:
            s.add_all(
                [
                    _feedback(_ago(6)),  # text window passed (5d), row kept (<10d)
                    _feedback(_ago(11)),  # row window passed
                    _contact(_ago(19)),  # kept
                    _contact(_ago(21)),  # deleted
                ]
            )
            s.commit()

        counts = await _run(factory)

        assert counts == {"feedback_text_cleared": 1, "feedback_deleted": 1, "contacts_deleted": 1}
        remaining = list(_fetch(engine, Feedback).values())
        assert len(remaining) == 1 and remaining[0].user_message is None
        assert len(_fetch(engine, ContactSubmission)) == 1

    async def test_large_backlog_is_processed_in_bounded_batches(
        self, retention_session_factory, monkeypatch
    ):
        factory, engine = retention_session_factory
        from sqlalchemy.orm import Session

        monkeypatch.setattr(retention, "BATCH_SIZE", 3)
        with Session(engine) as s:
            s.add_all([_feedback(_ago(45)) for _ in range(10)])
            s.commit()

        counts = await _run(factory)

        assert counts["feedback_text_cleared"] == 10
        assert all(r.user_message is None for r in _fetch(engine, Feedback).values())

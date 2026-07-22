"""
Tests for feedback/blocked_samples.py (BITB-057-adjacent privacy-minimal
capture of messages blocked by the safety pipeline).

Mocks the DB session directly (no real database) and asserts the
gating/dedup/insert/error-swallow branches, mirroring the mocking style in
test_feedback_repository.py.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import settings
from feedback.blocked_samples import purge_expired_blocked_samples, record_blocked_sample


def _async_session_factory_returning(db):
    """Build a callable that mimics ``async_session_factory()`` — an async
    context manager whose ``__aenter__`` yields the given mock session."""
    factory = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = cm
    return factory


@pytest.mark.asyncio
async def test_record_blocked_sample_noop_when_capture_disabled(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", False)
    factory = _async_session_factory_returning(MagicMock())

    with patch("scripture.database.async_session_factory", factory):
        await record_blocked_sample(message="blocked text", stage="keyword_filter")

    factory.assert_not_called()


@pytest.mark.asyncio
async def test_record_blocked_sample_noop_when_message_empty(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", True)
    factory = _async_session_factory_returning(MagicMock())

    with patch("scripture.database.async_session_factory", factory):
        await record_blocked_sample(message="", stage="keyword_filter")

    factory.assert_not_called()


@pytest.mark.asyncio
async def test_record_blocked_sample_swallows_import_error(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", True)
    monkeypatch.setitem(sys.modules, "scripture.database", None)

    # Must not raise, even though the lazy import of async_session_factory fails.
    await record_blocked_sample(message="blocked text", stage="keyword_filter")


@pytest.mark.asyncio
async def test_record_blocked_sample_dedup_increments_hit_count(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", True)

    existing_row = MagicMock(id=7, hit_count=2)
    select_result = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_row))
    update_result = MagicMock()

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[select_result, update_result])
    db.commit = AsyncMock()
    db.add = MagicMock()

    factory = _async_session_factory_returning(db)
    with patch("scripture.database.async_session_factory", factory):
        await record_blocked_sample(message="repeat offender", stage="llama_guard")

    assert db.execute.await_count == 2
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_blocked_sample_insert_when_no_existing_row(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", True)

    select_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    db = MagicMock()
    db.execute = AsyncMock(return_value=select_result)
    db.commit = AsyncMock()
    db.add = MagicMock()

    factory = _async_session_factory_returning(db)
    with patch("scripture.database.async_session_factory", factory):
        await record_blocked_sample(message="brand new violation", stage="openai_moderation")

    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert added.hit_count == 1
    assert added.reviewed is False
    assert added.stage == "openai_moderation"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_blocked_sample_hashes_session_id_when_provided(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", True)

    select_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    db = MagicMock()
    db.execute = AsyncMock(return_value=select_result)
    db.commit = AsyncMock()
    db.add = MagicMock()

    factory = _async_session_factory_returning(db)
    with patch("scripture.database.async_session_factory", factory):
        await record_blocked_sample(
            message="flagged", stage="keyword_filter", session_id="user-session-abc"
        )

    added = db.add.call_args.args[0]
    assert added.session_id_hash is not None
    assert added.session_id_hash != "user-session-abc"  # hashed, not stored raw


@pytest.mark.asyncio
async def test_record_blocked_sample_rollback_and_reraise_swallowed_by_outer(monkeypatch):
    monkeypatch.setattr(settings, "blocked_sample_capture_enabled", True)

    db = MagicMock()
    db.execute = AsyncMock(side_effect=ValueError("db exploded"))
    db.rollback = AsyncMock()

    factory = _async_session_factory_returning(db)
    with patch("scripture.database.async_session_factory", factory):
        # Must not raise: record_blocked_sample's contract is to never
        # propagate failures back to the caller.
        await record_blocked_sample(message="whatever", stage="azure_content_safety")

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_purge_expired_blocked_samples_returns_zero_on_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "scripture.database", None)

    result = await purge_expired_blocked_samples()

    assert result == 0


@pytest.mark.asyncio
async def test_purge_expired_blocked_samples_happy_path_returns_rowcount():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(rowcount=5))
    db.commit = AsyncMock()

    factory = _async_session_factory_returning(db)
    with patch("scripture.database.async_session_factory", factory):
        result = await purge_expired_blocked_samples()

    assert result == 5
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_purge_expired_blocked_samples_rollback_returns_zero_on_error():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("connection dropped"))
    db.rollback = AsyncMock()

    factory = _async_session_factory_returning(db)
    with patch("scripture.database.async_session_factory", factory):
        result = await purge_expired_blocked_samples()

    assert result == 0
    db.rollback.assert_awaited_once()

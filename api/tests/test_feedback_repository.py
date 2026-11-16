"""
Tests for FeedbackRepository's DB disconnect-retry behavior (BITB-143 Phase 2).

save_feedback/save_contact now route their commit/refresh sequence through
run_with_disconnect_retry (utils/db_retry.py). These tests mock the DB session
directly (no real database) and assert one retry then success on a transient
disconnect, mirroring the pattern in test_chat_coverage.py's
TestChatServiceSearchScripture disconnect-retry test.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from feedback.models import ContactRequest, Feedback, FeedbackRequest
from feedback.repository import FeedbackRepository


class ConnectionDoesNotExistError(Exception):
    """Stand-in for asyncpg's transient mid-operation disconnect error."""


def _make_feedback_request() -> FeedbackRequest:
    return FeedbackRequest(
        message_id=str(uuid.uuid4()),
        rating="positive",
        comment=None,
        user_message="What does the Bible say about hope?",
        assistant_response="The Bible speaks extensively about hope...",
        verses_cited=None,
        model_used=None,
        response_time_ms=None,
        session_id=None,
        reason=None,
    )


def _make_contact_request() -> ContactRequest:
    return ContactRequest(
        email="user@example.com",
        subject="feedback",
        message="Great app!",
        session_id=None,
        user_agent=None,
    )


@pytest.mark.asyncio
async def test_save_feedback_retries_once_on_disconnect_then_succeeds():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=[ConnectionDoesNotExistError("closed mid-operation"), None])
    db.refresh = AsyncMock()

    repo = FeedbackRepository(db)
    result = await repo.save_feedback(_make_feedback_request())

    assert result is not None
    assert db.commit.await_count == 2
    # add() is called once per attempt (rebuilds the ORM object each time).
    assert db.add.call_count == 2
    assert db.refresh.await_count == 1


@pytest.mark.asyncio
async def test_save_feedback_non_transient_error_raises_without_retry():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=ValueError("constraint violation"))
    db.refresh = AsyncMock()

    repo = FeedbackRepository(db)

    with pytest.raises(ValueError):
        await repo.save_feedback(_make_feedback_request())

    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_save_contact_retries_once_on_disconnect_then_succeeds():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=[ConnectionDoesNotExistError("closed mid-operation"), None])
    db.refresh = AsyncMock()

    repo = FeedbackRepository(db)
    result = await repo.save_contact(_make_contact_request())

    assert result is not None
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_get_feedback_by_message_id_found():
    message_id = str(uuid.uuid4())
    found = Feedback(message_id=uuid.UUID(message_id), rating="positive")

    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=found)))

    repo = FeedbackRepository(db)
    result = await repo.get_feedback_by_message_id(message_id)

    assert result is found
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_feedback_by_message_id_not_found():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    repo = FeedbackRepository(db)
    result = await repo.get_feedback_by_message_id(str(uuid.uuid4()))

    assert result is None


@pytest.mark.asyncio
async def test_get_feedback_by_message_id_invalid_uuid_raises():
    db = MagicMock()
    db.execute = AsyncMock()

    repo = FeedbackRepository(db)

    with pytest.raises(ValueError):
        await repo.get_feedback_by_message_id("not-a-uuid")

    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# BITB-329: only a one-way session hash is stored; contact user agents are not
# ---------------------------------------------------------------------------


def _saved_row(db):
    return db.add.call_args.args[0]


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
@pytest.mark.parametrize("session_id", ["sess-123", "日本語-é", "x" * 128])
async def test_save_feedback_stores_hash_not_raw_session_id(session_id):
    import hashlib

    from feedback.blocked_samples import _hash_session_id

    request = _make_feedback_request().model_copy(update={"session_id": session_id})
    db = _db()
    await FeedbackRepository(db).save_feedback(request)

    stored = _saved_row(db).session_id
    assert stored == hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    assert stored == _hash_session_id(session_id)  # same digest as blocked samples
    assert session_id not in stored


@pytest.mark.asyncio
async def test_save_contact_stores_hash_and_no_user_agent():
    from feedback.blocked_samples import _hash_session_id

    request = _make_contact_request().model_copy(
        update={"session_id": "sess-abc", "user_agent": "Mozilla/5.0 Chrome/120"}
    )
    db = _db()
    await FeedbackRepository(db).save_contact(request)

    row = _saved_row(db)
    assert row.session_id == _hash_session_id("sess-abc")
    assert row.user_agent is None


@pytest.mark.asyncio
async def test_missing_session_id_stays_null():
    db = _db()
    await FeedbackRepository(db).save_feedback(_make_feedback_request())
    assert _saved_row(db).session_id is None

    db = _db()
    await FeedbackRepository(db).save_contact(_make_contact_request())
    assert _saved_row(db).session_id is None

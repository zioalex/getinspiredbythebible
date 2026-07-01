"""
Tests for FeedbackRepository's DB disconnect-retry behavior (BITB-057 Phase 2).

save_feedback/save_contact now route their commit/refresh sequence through
run_with_disconnect_retry (utils/db_retry.py). These tests mock the DB session
directly (no real database) and assert one retry then success on a transient
disconnect, mirroring the pattern in test_chat_coverage.py's
TestChatServiceSearchScripture disconnect-retry test.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from feedback.models import ContactRequest, FeedbackRequest
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

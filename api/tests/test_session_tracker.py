"""
Tests for utils/session_tracker.py (DAU/MAU session upsert tracking).

Mocks the DB session directly (no real database). track_session's ON
CONFLICT upsert semantics against a real Postgres are covered separately by
tests/test_session_tracker_integration.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.session_tracker import _detect_mobile, track_session


@pytest.mark.asyncio
async def test_track_session_returns_immediately_when_no_token():
    db = MagicMock()
    db.execute = AsyncMock()

    await track_session(db, session_token=None, user_agent="Mozilla/5.0")

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_track_session_builds_upsert_with_bind_params():
    db = MagicMock()
    db.execute = AsyncMock()

    await track_session(
        db,
        session_token="tok-123",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS)",
        language="en",
    )

    db.execute.assert_awaited_once()
    query, params = db.execute.call_args.args
    assert "ON CONFLICT (session_token) DO UPDATE" in str(query)
    assert params == {
        "token": "tok-123",
        "lang": "en",
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS)",
        "mobile": True,
    }


@pytest.mark.asyncio
async def test_track_session_mobile_is_null_when_no_user_agent():
    """No UA must not assert "not mobile".

    `mobile` is bound as NULL so COALESCE(:mobile, sessions.is_mobile) keeps a
    previously detected mobile flag; a concrete False would overwrite it.
    """
    db = MagicMock()
    db.execute = AsyncMock()

    await track_session(db, session_token="tok-456", user_agent=None, language="fr")

    query, params = db.execute.call_args.args
    assert params["mobile"] is None
    # The insert branch still needs a non-NULL value for the NOT-NULL-ish default.
    assert "COALESCE(:mobile, FALSE)" in str(query)


@pytest.mark.asyncio
async def test_track_session_flags_android_app_user_agent_as_mobile():
    """The Android app's own UA (UserAgentInterceptor) must count as mobile."""
    db = MagicMock()
    db.execute = AsyncMock()

    await track_session(
        db,
        session_token="tok-android",
        user_agent="VoxQuieta/1.8.0 (Android 14; Pixel 7)",
        language="de",
    )

    _, params = db.execute.call_args.args
    assert params["mobile"] is True


@pytest.mark.asyncio
async def test_track_session_swallows_execute_exception_and_logs_warning():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=Exception("connection closed mid-operation"))

    with patch("utils.session_tracker.logger") as mock_logger:
        # Must not raise -- tracking failures never affect the chat response.
        await track_session(db, session_token="tok-789", user_agent="Mozilla/5.0")

    mock_logger.warning.assert_called_once()
    assert mock_logger.warning.call_args.kwargs.get("exc_info") is True


@pytest.mark.parametrize(
    "user_agent,expected",
    [
        ("Mozilla/5.0 (Linux; Android 14)", True),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)", True),
        ("Mozilla/5.0 (iPad; CPU OS 17_0)", True),
        ("SomeApp/1.0 Mobile", True),
        ("MOZILLA/5.0 (IPHONE)", True),
        # The Android app's own User-Agent, set by UserAgentInterceptor.
        ("VoxQuieta/1.8.0 (Android 14; Pixel 7)", True),
        # App installs predating that interceptor send OkHttp's default UA;
        # they are still Android traffic, not web traffic.
        ("okhttp/4.12.0", True),
        ("Dalvik/2.1.0 (Linux; U; Android 13; SM-G991B Build/TP1A)", True),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", False),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", False),
    ],
)
def test_detect_mobile_matches_keywords(user_agent, expected):
    assert _detect_mobile(user_agent) is expected

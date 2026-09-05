"""
Session tracking for DAU/MAU usage analytics.

Upserts a row in the `sessions` table on each chat request to track
unique users, activity timestamps, and message counts.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging_config import get_logger

logger = get_logger(__name__)

# User-Agent substrings that identify a request as coming from a mobile client.
#
# Mobile *browsers* announce themselves with "mobile"/"android"/"iphone"/"ipad".
# The Vox Quieta Android app is not a browser: it sends the UA built by
# `UserAgentInterceptor` ("VoxQuieta/<version> (Android <release>)"),
# which matches "android".
#
# Dalvik is Android's runtime and is therefore also a reliable mobile marker.
# A bare "okhttp/<version>" is not: OkHttp is a generic JVM client and does not
# identify either Android or the Vox Quieta app.
MOBILE_UA_MARKERS = ("mobile", "android", "iphone", "ipad", "dalvik")


async def track_session(
    db: AsyncSession,
    session_token: str | None,
    user_agent: str | None = None,
    language: str | None = None,
) -> None:
    """
    Upsert a session record: create on first visit, update on subsequent visits.

    This is fire-and-forget — errors are logged but never raised so that
    tracking failures do not affect the chat response.
    """
    if not session_token:
        return

    normalized_user_agent = user_agent.strip() if user_agent else None
    normalized_user_agent = normalized_user_agent or None

    # None (not False) when the request carries no meaningful User-Agent, so that the
    # upsert's COALESCE(:mobile, sessions.is_mobile) keeps whatever was
    # detected on an earlier request instead of silently flipping an
    # established mobile session back to web. On insert the column default
    # (FALSE) applies.
    is_mobile = _detect_mobile(normalized_user_agent) if normalized_user_agent else None

    try:
        await db.execute(
            text("""
                INSERT INTO sessions (session_token, language, user_agent, is_mobile, message_count)
                VALUES (:token, :lang, :ua, COALESCE(:mobile, FALSE), 1)
                ON CONFLICT (session_token) DO UPDATE SET
                    last_activity = NOW(),
                    message_count = sessions.message_count + 1,
                    language = COALESCE(:lang, sessions.language),
                    user_agent = COALESCE(:ua, sessions.user_agent),
                    is_mobile = COALESCE(:mobile, sessions.is_mobile)
            """),
            {
                "token": session_token,
                "lang": language,
                "ua": normalized_user_agent,
                "mobile": is_mobile,
            },
        )
    except Exception:
        logger.warning("Failed to track session %s", session_token, exc_info=True)


def _detect_mobile(user_agent: str) -> bool:
    """Simple mobile detection from User-Agent string."""
    ua_lower = user_agent.lower()
    return any(keyword in ua_lower for keyword in MOBILE_UA_MARKERS)

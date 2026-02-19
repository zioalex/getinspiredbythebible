"""
Session tracking for DAU/MAU usage analytics.

Upserts a row in the `sessions` table on each chat request to track
unique users, activity timestamps, and message counts.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging_config import get_logger

logger = get_logger(__name__)


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

    is_mobile = _detect_mobile(user_agent) if user_agent else False

    try:
        await db.execute(
            text("""
                INSERT INTO sessions (session_token, language, user_agent, is_mobile, message_count)
                VALUES (:token, :lang, :ua, :mobile, 1)
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
                "ua": user_agent,
                "mobile": is_mobile,
            },
        )
    except Exception:
        logger.warning("Failed to track session %s", session_token, exc_info=True)


def _detect_mobile(user_agent: str) -> bool:
    """Simple mobile detection from User-Agent string."""
    ua_lower = user_agent.lower()
    return any(keyword in ua_lower for keyword in ("mobile", "android", "iphone", "ipad"))

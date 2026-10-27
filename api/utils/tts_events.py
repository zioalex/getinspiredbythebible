"""Daily aggregate of read-aloud client events (BITB-247).

``record_tts_event`` increments a ``tts_event_daily`` row with an atomic
``INSERT ... ON CONFLICT DO UPDATE SET count = count + 1``. It never raises:
telemetry must not fail the request (or playback), so any error is logged and
swallowed.
"""

from datetime import UTC, date, datetime

from sqlalchemy.dialects.postgresql import insert

from feedback.models import TtsEventDaily
from utils.logging_config import get_logger

logger = get_logger(__name__)


def build_tts_event_upsert(
    *, day: date, event: str, locale: str, platform: str, browser: str, os: str
):
    """The atomic upsert statement (separate so tests can compile it)."""
    stmt = insert(TtsEventDaily).values(
        day=day, event=event, locale=locale, platform=platform, browser=browser, os=os, count=1
    )
    return stmt.on_conflict_do_update(
        index_elements=[
            TtsEventDaily.day,
            TtsEventDaily.event,
            TtsEventDaily.locale,
            TtsEventDaily.platform,
            TtsEventDaily.browser,
            TtsEventDaily.os,
        ],
        set_={"count": TtsEventDaily.count + 1},
    )


async def record_tts_event(
    *, event: str, locale: str, platform: str, browser: str, os: str
) -> bool:
    """Increment today's (UTC) counter row. Returns True on success, False if swallowed."""
    try:
        from scripture.database import async_session_factory

        stmt = build_tts_event_upsert(
            day=datetime.now(UTC).date(),
            event=event,
            locale=locale,
            platform=platform,
            browser=browser,
            os=os,
        )
        async with async_session_factory() as session:
            await session.execute(stmt)
            await session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - telemetry must never fail the request
        logger.warning("tts_event_daily upsert failed", extra={"error": type(exc).__name__})
        return False

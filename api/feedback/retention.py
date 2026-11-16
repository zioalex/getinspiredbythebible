"""
Retention sweep for feedback and contact-form data (BITB-329).

The privacy policy promises (numbers are the settings defaults and are tied to the policy
text by a test):

- feedback free text (``user_message``, ``assistant_response``, ``comment``): 30 days, then
  set to NULL;
- the rest of a feedback row (rating, reason, message id, verses, model, timing, session
  hash): 90 days, then deleted;
- contact submissions: 90 days, then deleted.

Ages are counted from ``created_at``. No code path updates ``created_at``, and the sweep
only ever touches rows older than the cutoff, so retention can never be extended.

The sweep is idempotent (the text pass only matches rows that still hold text), bounded
(rows are processed in batches of ``BATCH_SIZE``), and never raises. Logs carry counts
only, never message, reply, comment or e-mail text.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update

from config import settings
from utils.logging_config import get_logger

from .models import ContactSubmission, Feedback

logger = get_logger(__name__)

BATCH_SIZE = 500
# Safety valve: at most this many batches per table per sweep (the sweep runs hourly, so a
# large backlog simply drains over a few runs instead of holding the database for long).
MAX_BATCHES = 200


async def _clear_expired_text(db, cutoff: datetime) -> int:
    """NULL the free-text columns of feedback rows older than ``cutoff``; returns rows."""
    total = 0
    for _ in range(MAX_BATCHES):
        ids = (
            (
                await db.execute(
                    select(Feedback.id)
                    .where(
                        Feedback.created_at < cutoff,
                        or_(
                            Feedback.user_message.is_not(None),
                            Feedback.assistant_response.is_not(None),
                            Feedback.comment.is_not(None),
                        ),
                    )
                    .order_by(Feedback.id)
                    .limit(BATCH_SIZE)
                )
            )
            .scalars()
            .all()
        )
        if not ids:
            break
        result = await db.execute(
            update(Feedback)
            .where(
                Feedback.id.in_(ids),
                # re-check: a concurrent sweep may have cleared these rows since the SELECT
                or_(
                    Feedback.user_message.is_not(None),
                    Feedback.assistant_response.is_not(None),
                    Feedback.comment.is_not(None),
                ),
            )
            .values(user_message=None, assistant_response=None, comment=None)
        )
        await db.commit()
        total += int(getattr(result, "rowcount", 0) or 0)
        if len(ids) < BATCH_SIZE:
            break
    return total


async def _delete_older_than(db, model, cutoff: datetime) -> int:
    """Delete ``model`` rows created before ``cutoff`` in batches; returns rows."""
    total = 0
    for _ in range(MAX_BATCHES):
        ids = (
            (
                await db.execute(
                    select(model.id)
                    .where(model.created_at < cutoff)
                    .order_by(model.id)
                    .limit(BATCH_SIZE)
                )
            )
            .scalars()
            .all()
        )
        if not ids:
            break
        result = await db.execute(delete(model).where(model.id.in_(ids)))
        await db.commit()
        total += int(getattr(result, "rowcount", 0) or 0)
        if len(ids) < BATCH_SIZE:
            break
    return total


async def purge_expired_feedback(now: datetime | None = None) -> dict[str, int]:
    """
    Apply the feedback/contact retention windows. Returns counts:
    ``{"feedback_text_cleared": n, "feedback_deleted": n, "contacts_deleted": n}``.

    Never raises; a failing step is rolled back and reports 0.
    """
    counts = {"feedback_text_cleared": 0, "feedback_deleted": 0, "contacts_deleted": 0}
    try:
        from scripture.database import async_session_factory
    except Exception:
        return counts

    now = now or datetime.now(UTC)
    text_cutoff = now - timedelta(days=settings.feedback_text_retention_days)
    row_cutoff = now - timedelta(days=settings.feedback_retention_days)
    contact_cutoff = now - timedelta(days=settings.contact_retention_days)

    # Delete first so rows past their row window are not pointlessly rewritten.
    steps = (
        ("feedback_deleted", lambda db: _delete_older_than(db, Feedback, row_cutoff)),
        ("feedback_text_cleared", lambda db: _clear_expired_text(db, text_cutoff)),
        (
            "contacts_deleted",
            lambda db: _delete_older_than(db, ContactSubmission, contact_cutoff),
        ),
    )
    for key, step in steps:
        try:
            async with async_session_factory() as db:
                try:
                    counts[key] = await step(db)
                except Exception:
                    await db.rollback()
                    raise
        except Exception as e:
            # Error class only: never log row content.
            logger.warning(
                "Feedback retention step failed", extra={"step": key, "error": type(e).__name__}
            )
    return counts


__all__ = ["purge_expired_feedback"]

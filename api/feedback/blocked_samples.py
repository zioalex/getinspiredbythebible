"""
Privacy-minimal capture of messages blocked by the safety system.

Stores enough signal to fine-tune the multi-stage filter pipeline
(keyword filter, OpenAI Moderation, Llama Guard, Azure Content Safety)
without retaining identifiable user data:

- No raw IP, user id, or user-agent — only `session_id_hash`.
- Text is capped (settings.blocked_sample_max_chars) and deduplicated
  by sha256; repeats increment `hit_count` instead of adding rows.
- Rows are deleted after `expires_at`
  (settings.blocked_sample_retention_days).
- Writes are gated by settings.blocked_sample_capture_enabled and never
  raise back to the caller (capture failures must not affect the user
  response).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from config import settings
from utils.db_retry import run_with_disconnect_retry

from .models import BlockedMessageSample


def _hash_session_id(session_id: str | None) -> str | None:
    if not session_id:
        return None
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def record_blocked_sample(
    *,
    message: str,
    stage: str,
    categories: dict | list | None = None,
    severity: int | None = None,
    language: str | None = None,
    session_id: str | None = None,
) -> None:
    """
    Persist a privacy-minimal record of a blocked message.

    Best-effort: never raises. Returns silently if capture is disabled,
    the message is empty, or any error occurs (logged in the importer).
    """
    if not settings.blocked_sample_capture_enabled:
        return
    if not message:
        return

    # Imported lazily so test environments and offline tooling can import
    # this module without a configured database engine.
    try:
        from scripture.database import async_session_factory
    except Exception:
        return

    try:
        capped = message[: settings.blocked_sample_max_chars]
        text_hash = _hash_text(message)  # hash full message for stable dedup
        session_hash = _hash_session_id(session_id)
        now = datetime.now(UTC)
        expires = now + timedelta(days=settings.blocked_sample_retention_days)

        async def _do_record() -> None:
            # Opens a fresh session per attempt (required by
            # run_with_disconnect_retry: a connection that died mid-operation
            # cannot be reused, so each retry needs its own session).
            async with async_session_factory() as db:
                try:
                    existing = await db.execute(
                        select(BlockedMessageSample).where(
                            BlockedMessageSample.message_sha256 == text_hash
                        )
                    )
                    row = existing.scalar_one_or_none()
                    if row is not None:
                        # Dedup: bump counter, refresh TTL, do not store text again.
                        await db.execute(
                            update(BlockedMessageSample)
                            .where(BlockedMessageSample.id == row.id)
                            .values(hit_count=row.hit_count + 1, expires_at=expires)
                        )
                    else:
                        db.add(
                            BlockedMessageSample(
                                created_at=now,
                                expires_at=expires,
                                stage=stage,
                                categories=categories,
                                severity=severity,
                                language=language,
                                message_text=capped,
                                message_sha256=text_hash,
                                session_id_hash=session_hash,
                                hit_count=1,
                                reviewed=False,
                            )
                        )
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

        # The helper's own final failure (after exhausting retries) is still
        # caught by the outer except below — record_blocked_sample's contract
        # is to never raise back to the caller.
        await run_with_disconnect_retry(_do_record, op_name="record_blocked_sample")
    except Exception:
        # Capture must never break the user response. Swallow silently;
        # the caller already logged the violation through normal channels.
        return


async def purge_expired_blocked_samples() -> int:
    """
    Delete rows whose `expires_at` is in the past. Returns rowcount.

    Intended to be invoked from a periodic task; safe to call at any time.
    """
    try:
        from scripture.database import async_session_factory
    except Exception:
        return 0

    now = datetime.now(UTC)
    async with async_session_factory() as db:
        try:
            result = await db.execute(
                delete(BlockedMessageSample).where(BlockedMessageSample.expires_at < now)
            )
            await db.commit()
            return int(getattr(result, "rowcount", 0) or 0)
        except Exception:
            await db.rollback()
            return 0

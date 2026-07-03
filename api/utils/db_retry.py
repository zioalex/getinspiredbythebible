"""
Generalized DB disconnect-retry helper (BITB-057 Phase 2).

Generalizes the retry-on-transient-disconnect pattern that previously lived
only in chat/service.py::_search_scripture (as a bespoke recursive
`_allow_retry` mechanism), so other DB-writing/reading call sites (feedback
repository, blocked-sample capture, cited-verse resolution) can opt in
without duplicating the classification logic.
"""

from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

from utils.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def is_disconnection_error(exc: Exception) -> bool:
    """True if ``exc`` indicates a dropped/invalidated Postgres connection.

    ``pool_pre_ping`` validates a connection at checkout, but cannot save one that
    dies *mid-operation* (e.g. Azure Postgres closing an idle backend, or asyncpg's
    ``ConnectionDoesNotExistError: connection was closed in the middle of operation``).
    Those are transient — SQLAlchemy invalidates the connection and the next checkout
    gets a fresh, pre-pinged one — so the caller can safely retry once.
    """
    from sqlalchemy.exc import DBAPIError, DisconnectionError

    transient_names = {
        "ConnectionDoesNotExistError",
        "ConnectionResetError",
        "InterfaceError",
    }
    if isinstance(exc, DisconnectionError):
        return True
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return True
    if type(exc).__name__ in transient_names:
        return True
    cause = getattr(exc, "orig", None) or getattr(exc, "__cause__", None)
    return cause is not None and type(cause).__name__ in transient_names


async def run_with_disconnect_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 2,
    op_name: str = "db_operation",
) -> T:
    """Run ``fn()`` and retry once (by default) on a transient DB disconnect.

    IMPORTANT: ``fn`` must be a closure that acquires its OWN db session (or
    otherwise obtains a fresh connection) on each call. A connection that died
    mid-operation cannot be reused — the whole point of retrying is to get a
    new, pre-pinged connection from the pool on the next attempt. Do not
    capture and reuse a single session across attempts.

    Args:
        fn: Zero-arg async callable to run, acquiring its own DB session per call.
        max_attempts: Total attempts (including the first). Default 2 (one retry).
        op_name: Label used in the warning log on retry, for triage.

    Returns:
        The return value of the first successful ``fn()`` call.

    Raises:
        The last exception if all attempts fail (immediately, with no retry,
        if the exception is not a transient disconnection error).
    """
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            is_last_attempt = attempt == max_attempts - 1
            if not is_disconnection_error(e) or is_last_attempt:
                raise
            logger.warning(
                f"{op_name} hit a transient DB disconnect "
                f"({type(e).__name__}); retrying (attempt {attempt + 2}/{max_attempts})"
            )
    # Unreachable: the loop either returns or raises on every iteration.
    assert last_error is not None
    raise last_error

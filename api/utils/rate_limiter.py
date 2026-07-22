"""
Shared rate limiter (BITB-061).

Enforces per-IP and per-session sliding-window rate limits plus a durable
per-session lifetime cap. Backed by Postgres by default so limits hold across
replicas and survive deploys/restarts (the in-memory limiter this replaces
tracked counters per-process, so with N replicas the effective limit was N
times the configured value, and every restart reset the lifetime cap it
exists to enforce). Falls back to an in-process store — circuit-breaker
mediated — when Postgres is transiently unavailable, and is selectable as the
sole backend via `rate_limit_backend=memory` for tests/local dev without a
database.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import text

from utils.circuit_breaker import CircuitBreaker
from utils.logging_config import get_logger
from utils.metrics import (
    rate_limiter_db_error_counter,
    rate_limiter_fail_closed_counter,
    rate_limiter_fallback_counter,
)

logger = get_logger(__name__)


@dataclass
class RateLimitEntry:
    """Tracks request timestamps for a single key (IP or session)."""

    timestamps: list[float] = field(default_factory=list)
    total_requests: int = 0  # Lifetime counter (for session limits)
    last_seen: float = 0.0  # Timestamp of the most recent request (for session TTL)


class RateLimitStore(Protocol):
    """A backend that decides + atomically records a rate-limit check."""

    async def check_and_record(
        self, ip_address: str, session_id: str | None
    ) -> tuple[bool, str | None]: ...

    def get_stats(self) -> dict: ...


class InMemoryStore:
    """
    In-process sliding-window store (the pre-BITB-061 behavior).

    Not shared across replicas and reset on restart — kept as the fallback
    used when Postgres is unavailable, and as the backend selectable via
    `rate_limit_backend=memory` for tests/local dev without a database.
    """

    def __init__(
        self,
        requests_per_minute: int,
        session_requests_per_minute: int,
        session_max_requests: int,
        window_seconds: int,
        cleanup_interval_seconds: int,
        session_ttl_seconds: int,
    ):
        self.requests_per_minute = requests_per_minute
        self.session_requests_per_minute = session_requests_per_minute
        self.session_max_requests = session_max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval_seconds
        # How long a session's lifetime counter is retained after its last
        # request. Decoupled from window_seconds so the lifetime session limit
        # survives normal idle gaps instead of resetting every minute.
        self.session_ttl_seconds = session_ttl_seconds

        self._ip_limits: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._session_limits: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._last_cleanup = time.time()

    async def check_and_record(
        self, ip_address: str, session_id: str | None = None
    ) -> tuple[bool, str | None]:
        now = time.time()
        cutoff = now - self.window_seconds

        if now - self._last_cleanup > self.cleanup_interval:
            await self._cleanup(now, cutoff)
            self._last_cleanup = now

        ip_entry = self._ip_limits[ip_address]
        ip_entry.timestamps = [t for t in ip_entry.timestamps if t > cutoff]

        if len(ip_entry.timestamps) >= self.requests_per_minute:
            return False, "IP rate limit exceeded"

        if session_id:
            session_entry = self._session_limits[session_id]
            session_entry.timestamps = [t for t in session_entry.timestamps if t > cutoff]

            # Check lifetime session limit first so it always takes precedence
            # over the per-minute check, ensuring the farewell UX is shown.
            if session_entry.total_requests >= self.session_max_requests:
                return False, "Session lifetime limit exceeded"

            if len(session_entry.timestamps) >= self.session_requests_per_minute:
                return False, "Session rate limit exceeded"

        ip_entry.timestamps.append(now)

        if session_id:
            session_entry = self._session_limits[session_id]
            session_entry.timestamps.append(now)
            session_entry.total_requests += 1
            session_entry.last_seen = now

        return True, None

    async def _cleanup(self, now: float, cutoff: float) -> None:
        """Remove expired entries to prevent memory growth."""
        expired_ips = [
            ip
            for ip, entry in self._ip_limits.items()
            if not entry.timestamps or all(t <= cutoff for t in entry.timestamps)
        ]
        for ip in expired_ips:
            del self._ip_limits[ip]

        # Clean session entries by inactivity TTL only, not the 60s rate
        # window, so the lifetime counter survives normal idle gaps.
        session_cutoff = now - self.session_ttl_seconds
        expired_sessions = [
            sid for sid, entry in self._session_limits.items() if entry.last_seen <= session_cutoff
        ]
        for sid in expired_sessions:
            del self._session_limits[sid]

    def get_stats(self) -> dict:
        return {
            "backend": "memory",
            "tracked_ips": len(self._ip_limits),
            "tracked_sessions": len(self._session_limits),
            "config": {
                "requests_per_minute": self.requests_per_minute,
                "session_requests_per_minute": self.session_requests_per_minute,
                "session_max_requests": self.session_max_requests,
                "window_seconds": self.window_seconds,
            },
        }


class PostgresStore:
    """
    Shared, cross-replica store backed by Postgres (`rate_limit_hits` /
    `rate_limit_sessions`, migration 009).

    Uses transaction-scoped advisory locks (`pg_advisory_xact_lock`) keyed by
    IP/session so concurrent requests for the *same* key serialize (matching
    the single-lock semantics `InMemoryStore` had per-process, now enforced
    across replicas too) while different keys never block each other. The
    session lifetime counter is updated via an atomic
    `INSERT ... ON CONFLICT DO UPDATE` so concurrent replicas can never
    double-count or lose an increment. Window rows are purged by pg_cron
    (migration 010), not by this class.
    """

    def __init__(
        self,
        requests_per_minute: int,
        session_requests_per_minute: int,
        session_max_requests: int,
        window_seconds: int,
    ):
        self.requests_per_minute = requests_per_minute
        self.session_requests_per_minute = session_requests_per_minute
        self.session_max_requests = session_max_requests
        self.window_seconds = window_seconds

    async def check_and_record(
        self, ip_address: str, session_id: str | None = None
    ) -> tuple[bool, str | None]:
        # Lazy import: avoids a module-load-time cycle between utils.security
        # (imports utils.rate_limiter) and scripture.database.
        from scripture.database import async_session_factory

        ip_key = f"ip:{ip_address}"
        sess_key = f"session:{session_id}" if session_id else None

        async with async_session_factory() as session:
            # Lock in a deterministic order so a request touching both an IP
            # key and a session key can never deadlock against another
            # request locking the same two keys in the opposite order.
            for key in sorted(k for k in (ip_key, sess_key) if k):
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key}
                )

            ip_count = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM rate_limit_hits "
                        "WHERE limit_key = :key "
                        "AND created_at > now() - make_interval(secs => :secs)"
                    ),
                    {"key": ip_key, "secs": self.window_seconds},
                )
            ).scalar_one()

            if ip_count >= self.requests_per_minute:
                return False, "IP rate limit exceeded"

            if sess_key:
                lifetime_total = (
                    await session.execute(
                        text(
                            "SELECT total_requests FROM rate_limit_sessions WHERE session_id = :sid"
                        ),
                        {"sid": session_id},
                    )
                ).scalar_one_or_none()

                # Lifetime limit takes precedence over the per-minute check so
                # the farewell UX is shown, matching InMemoryStore's ordering.
                if (lifetime_total or 0) >= self.session_max_requests:
                    return False, "Session lifetime limit exceeded"

                session_count = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM rate_limit_hits "
                            "WHERE limit_key = :key "
                            "AND created_at > now() - make_interval(secs => :secs)"
                        ),
                        {"key": sess_key, "secs": self.window_seconds},
                    )
                ).scalar_one()

                if session_count >= self.session_requests_per_minute:
                    return False, "Session rate limit exceeded"

            await session.execute(
                text("INSERT INTO rate_limit_hits (limit_key) VALUES (:key)"), {"key": ip_key}
            )

            if sess_key:
                await session.execute(
                    text("INSERT INTO rate_limit_hits (limit_key) VALUES (:key)"), {"key": sess_key}
                )
                await session.execute(
                    text(
                        "INSERT INTO rate_limit_sessions (session_id, total_requests, last_seen) "
                        "VALUES (:sid, 1, now()) "
                        "ON CONFLICT (session_id) DO UPDATE "
                        "SET total_requests = rate_limit_sessions.total_requests + 1, "
                        "last_seen = now()"
                    ),
                    {"sid": session_id},
                )

            await session.commit()
            return True, None

    def get_stats(self) -> dict:
        return {
            "backend": "postgres",
            "config": {
                "requests_per_minute": self.requests_per_minute,
                "session_requests_per_minute": self.session_requests_per_minute,
                "session_max_requests": self.session_max_requests,
                "window_seconds": self.window_seconds,
            },
        }


class RateLimiter:
    """
    Public entry point used by `api/utils/security.py` — signature and
    behavior are unchanged from the pre-BITB-061 in-memory-only limiter.

    Delegates to a Postgres-backed store by default. An isolated Postgres
    error falls back to an in-process store for that check (degraded but
    still enforcing *something*) and emits `rate_limiter.fallback_total`.
    Persistent Postgres failures trip a circuit breaker and the check fails
    CLOSED (`rate_limiter.fail_closed_total`) rather than silently allowing
    every request through — the fail-open behavior this story exists to
    close.
    """

    def __init__(
        self,
        requests_per_minute: int = 20,
        session_requests_per_minute: int = 10,
        session_max_requests: int = 100,
        window_seconds: int = 60,
        cleanup_interval_seconds: int = 300,
        session_ttl_seconds: int = 3600,
        backend: str = "postgres",
    ):
        self._fallback = InMemoryStore(
            requests_per_minute=requests_per_minute,
            session_requests_per_minute=session_requests_per_minute,
            session_max_requests=session_max_requests,
            window_seconds=window_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds,
            session_ttl_seconds=session_ttl_seconds,
        )
        self._use_postgres = backend == "postgres"
        self._store: RateLimitStore
        if self._use_postgres:
            self._store = PostgresStore(
                requests_per_minute=requests_per_minute,
                session_requests_per_minute=session_requests_per_minute,
                session_max_requests=session_max_requests,
                window_seconds=window_seconds,
            )
        else:
            self._store = self._fallback

        # Trip after 5 consecutive Postgres errors; cooldown 30s — mirrors
        # TurnstileVerifier's breaker (utils/turnstile.py). While closed, an
        # isolated DB blip falls back to the in-memory store; once open,
        # checks fail closed without hitting the network until cooldown.
        self._breaker = CircuitBreaker(
            name="rate_limiter",
            failure_threshold=5,
            cooldown_seconds=30.0,
        )

    async def check_rate_limit(
        self, ip_address: str, session_id: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if a request should be allowed, recording it if so.

        Args:
            ip_address: Client IP address
            session_id: Optional session identifier

        Returns:
            Tuple of (allowed, error_reason)
        """
        if not self._use_postgres:
            return await self._store.check_and_record(ip_address, session_id)

        if self._breaker.is_open():
            rate_limiter_fail_closed_counter.add(1)
            logger.error("Rate limiter Postgres store circuit open — failing closed")
            return False, "Rate limiter temporarily unavailable"

        try:
            result = await self._store.check_and_record(ip_address, session_id)
            self._breaker.record_success()
            return result
        except Exception as e:
            self._breaker.record_failure()
            rate_limiter_db_error_counter.add(1, {"reason": type(e).__name__.lower()})
            logger.warning(
                "Rate limiter Postgres store failed (%s) — falling back to in-memory store",
                type(e).__name__,
                exc_info=True,
            )
            if self._breaker.is_open():
                rate_limiter_fail_closed_counter.add(1)
                logger.error("Rate limiter Postgres store persistently failing — failing closed")
                return False, "Rate limiter temporarily unavailable"
            rate_limiter_fallback_counter.add(1)
            return await self._fallback.check_and_record(ip_address, session_id)

    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        return self._store.get_stats()


# Global instance (initialized on first use)
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        from config import settings

        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute,
            session_requests_per_minute=settings.rate_limit_requests_per_session_minute,
            session_max_requests=settings.rate_limit_session_max_requests,
            session_ttl_seconds=settings.rate_limit_session_ttl_seconds,
            backend=settings.rate_limit_backend,
        )
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Test hook: clear the singleton so the next get_rate_limiter() call re-reads config."""
    global _rate_limiter
    _rate_limiter = None

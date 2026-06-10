"""
In-memory sliding window rate limiter.

Provides per-IP and per-session rate limiting with automatic cleanup.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimitEntry:
    """Tracks request timestamps for a single key (IP or session)."""

    timestamps: list[float] = field(default_factory=list)
    total_requests: int = 0  # Lifetime counter (for session limits)
    last_seen: float = 0.0  # Timestamp of the most recent request (for session TTL)


class RateLimiter:
    """
    Sliding window rate limiter with automatic cleanup.

    Tracks:
    - Per-IP request rate (requests per minute)
    - Per-session request rate (requests per minute)
    - Per-session lifetime requests (total requests ever)

    Thread-safe via asyncio lock.
    """

    def __init__(
        self,
        requests_per_minute: int = 20,
        session_requests_per_minute: int = 10,
        session_max_requests: int = 100,
        window_seconds: int = 60,
        cleanup_interval_seconds: int = 300,
        session_ttl_seconds: int = 3600,
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

        # Storage
        self._ip_limits: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._session_limits: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()

    async def check_rate_limit(
        self, ip_address: str, session_id: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if a request should be allowed.

        Args:
            ip_address: Client IP address
            session_id: Optional session identifier

        Returns:
            Tuple of (allowed, error_reason)
        """
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Periodic cleanup
            if now - self._last_cleanup > self.cleanup_interval:
                await self._cleanup(now, cutoff)
                self._last_cleanup = now

            # Check IP rate limit
            ip_entry = self._ip_limits[ip_address]
            ip_entry.timestamps = [t for t in ip_entry.timestamps if t > cutoff]

            if len(ip_entry.timestamps) >= self.requests_per_minute:
                return False, "IP rate limit exceeded"

            # Check session limits (if session provided)
            if session_id:
                session_entry = self._session_limits[session_id]
                session_entry.timestamps = [t for t in session_entry.timestamps if t > cutoff]

                # Check lifetime session limit first so it always takes precedence
                # over the per-minute check, ensuring the farewell UX is shown.
                if session_entry.total_requests >= self.session_max_requests:
                    return False, "Session lifetime limit exceeded"

                # Check per-minute session limit
                if len(session_entry.timestamps) >= self.session_requests_per_minute:
                    return False, "Session rate limit exceeded"

            # Allow request and record it
            ip_entry.timestamps.append(now)

            if session_id:
                session_entry = self._session_limits[session_id]
                session_entry.timestamps.append(now)
                session_entry.total_requests += 1
                session_entry.last_seen = now

            return True, None

    async def _cleanup(self, now: float, cutoff: float) -> None:
        """Remove expired entries to prevent memory growth."""
        # Clean IP entries (purely rate-window based)
        expired_ips = [
            ip
            for ip, entry in self._ip_limits.items()
            if not entry.timestamps or all(t <= cutoff for t in entry.timestamps)
        ]
        for ip in expired_ips:
            del self._ip_limits[ip]

        # Clean session entries by inactivity TTL only. Previously sessions under
        # the lifetime limit were deleted once idle past the 60s rate window,
        # which silently reset the "lifetime" counter on brief idle gaps. Evicting
        # by last_seen keeps the count alive for the session's real lifetime while
        # still bounding memory.
        session_cutoff = now - self.session_ttl_seconds
        expired_sessions = [
            sid
            for sid, entry in self._session_limits.items()
            if entry.last_seen <= session_cutoff
        ]
        for sid in expired_sessions:
            del self._session_limits[sid]

    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        return {
            "tracked_ips": len(self._ip_limits),
            "tracked_sessions": len(self._session_limits),
            "config": {
                "requests_per_minute": self.requests_per_minute,
                "session_requests_per_minute": self.session_requests_per_minute,
                "session_max_requests": self.session_max_requests,
                "window_seconds": self.window_seconds,
            },
        }


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
        )
    return _rate_limiter

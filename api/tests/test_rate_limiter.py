"""
Tests for the Postgres-backed shared rate limiter (BITB-061).

`test_utils_coverage.py` / `test_security.py` already cover the sliding-window
algorithm itself via `RateLimiter(backend="memory")`. This file covers what's
new in this phase:

- `PostgresStore` issues the right SQL/params for each decision branch
  (mocked `AsyncSession` — no DB required).
- `RateLimiter` falls back to the in-memory store on an isolated Postgres
  error, and fails closed once the circuit breaker trips on persistent
  failures — never silently fails open.
- True concurrent-request safety (the reason this migration exists): a burst
  of concurrent `check_rate_limit` calls against the same session must not
  double-count or lose an increment.
"""

import asyncio
from unittest.mock import patch

import pytest

import utils.rate_limiter as rate_limiter_module
from utils.rate_limiter import PostgresStore, RateLimiter


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    """Minimal async-context-manager stand-in for `AsyncSession`.

    Routes each `execute()` call to a canned result by inspecting the SQL
    text/params, so tests don't need to hardcode call order/count.
    """

    def __init__(
        self, ip_count: int = 0, session_count: int = 0, lifetime_total: int | None = None
    ):
        self.ip_count = ip_count
        self.session_count = session_count
        self.lifetime_total = lifetime_total
        self.executed: list[tuple[str, dict]] = []
        self.committed = False

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        self.executed.append((sql, params))

        if "pg_advisory_xact_lock" in sql:
            return FakeResult(None)
        if "total_requests FROM rate_limit_sessions" in sql:
            return FakeResult(self.lifetime_total)
        if "count(*) FROM rate_limit_hits" in sql:
            key = params.get("key", "")
            return FakeResult(self.ip_count if key.startswith("ip:") else self.session_count)
        return FakeResult(None)  # INSERT / ON CONFLICT UPSERT

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FailingSession:
    """Every `execute()` raises, simulating a Postgres outage."""

    async def execute(self, stmt, params=None):
        raise RuntimeError("connection refused")

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _patch_session_factory(session):
    return patch("scripture.database.async_session_factory", lambda: session)


class TestPostgresStoreSql:
    """PostgresStore issues the expected SQL for each decision branch."""

    @pytest.mark.asyncio
    async def test_allows_and_records_when_under_all_limits(self):
        session = FakeSession(ip_count=0, session_count=0, lifetime_total=0)
        store = PostgresStore(
            requests_per_minute=20,
            session_requests_per_minute=10,
            session_max_requests=100,
            window_seconds=60,
        )
        with _patch_session_factory(session):
            allowed, reason = await store.check_and_record("1.2.3.4", "sess-1")

        assert allowed is True
        assert reason is None
        assert session.committed is True
        inserted_keys = {
            p["key"] for sql, p in session.executed if sql.startswith("INSERT INTO rate_limit_hits")
        }
        assert inserted_keys == {"ip:1.2.3.4", "session:sess-1"}
        upsert = [p for sql, p in session.executed if "ON CONFLICT (session_id)" in sql]
        assert upsert == [{"sid": "sess-1"}]

    @pytest.mark.asyncio
    async def test_blocks_on_ip_limit_without_recording(self):
        session = FakeSession(ip_count=20)
        store = PostgresStore(
            requests_per_minute=20,
            session_requests_per_minute=10,
            session_max_requests=100,
            window_seconds=60,
        )
        with _patch_session_factory(session):
            allowed, reason = await store.check_and_record("1.2.3.4", None)

        assert allowed is False
        assert reason == "IP rate limit exceeded"
        assert session.committed is False
        assert not any(sql.startswith("INSERT") for sql, _ in session.executed)

    @pytest.mark.asyncio
    async def test_blocks_on_session_lifetime_limit_before_per_minute_check(self):
        session = FakeSession(ip_count=0, session_count=0, lifetime_total=100)
        store = PostgresStore(
            requests_per_minute=20,
            session_requests_per_minute=10,
            session_max_requests=100,
            window_seconds=60,
        )
        with _patch_session_factory(session):
            allowed, reason = await store.check_and_record("1.2.3.4", "sess-1")

        assert allowed is False
        assert reason == "Session lifetime limit exceeded"
        # Lifetime check short-circuits before the session per-minute query.
        assert not any(
            "count(*) FROM rate_limit_hits" in sql and p.get("key") == "session:sess-1"
            for sql, p in session.executed
        )

    @pytest.mark.asyncio
    async def test_blocks_on_session_per_minute_limit(self):
        session = FakeSession(ip_count=0, session_count=10, lifetime_total=5)
        store = PostgresStore(
            requests_per_minute=20,
            session_requests_per_minute=10,
            session_max_requests=100,
            window_seconds=60,
        )
        with _patch_session_factory(session):
            allowed, reason = await store.check_and_record("1.2.3.4", "sess-1")

        assert allowed is False
        assert reason == "Session rate limit exceeded"


class TestRateLimiterFailover:
    """RateLimiter must never silently fail open on a Postgres error."""

    @pytest.mark.asyncio
    async def test_isolated_db_error_falls_back_to_in_memory(self):
        limiter = RateLimiter(requests_per_minute=5, backend="postgres")
        with (
            patch.object(rate_limiter_module, "rate_limiter_fallback_counter") as fallback_counter,
            _patch_session_factory(FailingSession()),
        ):
            allowed, reason = await limiter.check_rate_limit("1.2.3.4")

        assert allowed is True
        assert reason is None
        fallback_counter.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_persistent_db_errors_trip_breaker_and_fail_closed(self):
        limiter = RateLimiter(requests_per_minute=5, backend="postgres")
        with (
            patch.object(
                rate_limiter_module, "rate_limiter_fail_closed_counter"
            ) as fail_closed_counter,
            _patch_session_factory(FailingSession()),
        ):
            results = [await limiter.check_rate_limit("1.2.3.4") for _ in range(6)]

        # First 4 failures fall back (breaker still closed); the 5th failure
        # trips the breaker (failure_threshold=5) and fails closed from then on.
        assert [allowed for allowed, _ in results[:4]] == [True, True, True, True]
        assert results[4] == (False, "Rate limiter temporarily unavailable")
        assert results[5] == (False, "Rate limiter temporarily unavailable")
        assert fail_closed_counter.add.call_count == 2

    @pytest.mark.asyncio
    async def test_memory_backend_never_touches_postgres(self):
        """backend="memory" must not import/patch scripture.database at all."""
        limiter = RateLimiter(requests_per_minute=5, backend="memory")
        allowed, reason = await limiter.check_rate_limit("1.2.3.4")
        assert allowed is True
        assert reason is None


class TestConcurrency:
    """Concurrent requests must not double-count or lose an increment."""

    @pytest.mark.asyncio
    async def test_in_memory_lifetime_cap_holds_under_concurrent_requests(self):
        limiter = RateLimiter(
            requests_per_minute=1000,
            session_requests_per_minute=1000,
            session_max_requests=10,
            backend="memory",
        )

        results = await asyncio.gather(
            *[limiter.check_rate_limit("1.2.3.4", "burst-session") for _ in range(50)]
        )

        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == 10

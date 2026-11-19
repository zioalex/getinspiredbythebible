"""Tests for the client-error reporting endpoint (BITB-066)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import _normalize_client_error_type, app  # noqa: E402

client = TestClient(app)


def test_client_errors_accepts_valid_report():
    resp = client.post(
        "/api/v1/client-errors",
        json={"type": "window_onerror", "detail": "boom"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_client_errors_defaults_missing_fields():
    # Empty body is valid — both fields default.
    resp = client.post("/api/v1/client-errors", json={})
    assert resp.status_code == 200


def test_client_errors_rejects_oversized_detail():
    # detail has a max_length of 4096 on the model → 422.
    resp = client.post(
        "/api/v1/client-errors",
        json={"type": "api_failure", "detail": "x" * 5000},
    )
    assert resp.status_code == 422


def test_normalize_client_error_type_bounds_cardinality():
    assert _normalize_client_error_type("window_onerror") == "window_onerror"
    assert _normalize_client_error_type("unhandledrejection") == "unhandledrejection"
    # Turnstile reports (prefixed) collapse to a single label.
    assert _normalize_client_error_type("turnstile_error") == "turnstile"
    # Anything unknown collapses to "other" to bound metric cardinality.
    assert _normalize_client_error_type("some_random_type") == "other"


def test_client_errors_rejects_extra_fields():
    # BITB-310: unknown fields (notably a stray session_id) are a 422, not silently accepted.
    resp = client.post(
        "/api/v1/client-errors",
        json={"type": "x", "detail": "y", "session_id": "s"},
    )
    assert resp.status_code == 422


# --- BITB-310: telemetry rate limiting is IP-only and never touches chat budgets -------------

import pytest  # noqa: E402

from config import settings  # noqa: E402
from utils.rate_limiter import (  # noqa: E402
    get_rate_limiter,
    get_scoped_rate_limiter,
    reset_rate_limiter,
)

TELEMETRY_LIMIT = 3
SESSION = "chat-session-abc"
ERROR_BODY = {"type": "window_onerror", "detail": "boom"}
EVENT_BODY = {"event": "tts_started", "locale": "en"}


@pytest.fixture
def limited(monkeypatch):
    """Memory-backed limiter, tiny telemetry cap, fresh state, IP picked by X-Test-IP."""
    reset_rate_limiter()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "rate_limit_telemetry_per_minute", TELEMETRY_LIMIT)
    monkeypatch.setattr(
        "utils.security.get_client_ip", lambda r: r.headers.get("x-test-ip", "10.0.0.1")
    )
    with patch("main.record_tts_event", new=AsyncMock(return_value=True)):
        yield TestClient(app)
    reset_rate_limiter()


def test_telemetry_with_session_id_does_not_charge_chat_session(limited):
    # Both routes, body carries a real chat session_id. client-errors now 422s (extra=forbid)
    # and client-events 422s (extra=forbid) — either way the chat budget must stay untouched.
    chat = get_rate_limiter()
    before = chat.check_rate_limit
    calls = []

    async def spy(*args, **kwargs):
        calls.append(args)
        return await before(*args, **kwargs)

    chat.check_rate_limit = spy  # type: ignore[method-assign]
    try:
        for _ in range(TELEMETRY_LIMIT):
            limited.post("/api/v1/client-errors", json={**ERROR_BODY, "session_id": SESSION})
            limited.post("/api/v1/client-events", json={**EVENT_BODY, "session_id": SESSION})
    finally:
        chat.check_rate_limit = before  # type: ignore[method-assign]
    assert calls == []

    # The session still has its full lifetime budget.
    import asyncio

    async def drain():
        results = []
        for _ in range(settings.rate_limit_session_max_requests):
            results.append((await get_rate_limiter().check_rate_limit("9.9.9.9", SESSION))[0])
        return results

    assert all(asyncio.run(drain()))


def test_telemetry_over_limit_is_429_and_chat_limiter_unused(limited):
    chat = get_rate_limiter()
    chat.check_rate_limit = AsyncMock(side_effect=AssertionError("chat limiter consulted"))  # type: ignore[method-assign]
    h = {"X-Test-IP": "1.1.1.1"}
    # The two routes share one bucket: 2 errors + 1 event use the whole budget.
    assert limited.post("/api/v1/client-errors", json=ERROR_BODY, headers=h).status_code == 200
    assert limited.post("/api/v1/client-errors", json=ERROR_BODY, headers=h).status_code == 200
    assert limited.post("/api/v1/client-events", json=EVENT_BODY, headers=h).status_code == 200
    for path, body in (
        ("/api/v1/client-errors", ERROR_BODY),
        ("/api/v1/client-events", EVENT_BODY),
    ):
        resp = limited.post(path, json=body, headers=h)
        assert resp.status_code == 429
        assert resp.json()["detail"] == {"error": "Rate limit exceeded", "retry_after": 60}
    # Another IP is unaffected.
    other = {"X-Test-IP": "2.2.2.2"}
    assert limited.post("/api/v1/client-errors", json=ERROR_BODY, headers=other).status_code == 200


@pytest.mark.asyncio
async def test_telemetry_bucket_is_independent_of_other_scopes(limited):
    h = {"X-Test-IP": "3.3.3.3"}
    for _ in range(TELEMETRY_LIMIT):
        assert limited.post("/api/v1/client-errors", json=ERROR_BODY, headers=h).status_code == 200
    assert limited.post("/api/v1/client-errors", json=ERROR_BODY, headers=h).status_code == 429
    # Same IP, same per-minute number, other scopes / chat: all still have full budget.
    for scope in ("feedback", "search"):
        ok, _ = await get_scoped_rate_limiter(scope, TELEMETRY_LIMIT).check_rate_limit(
            f"{scope}:3.3.3.3"
        )
        assert ok
    ok, _ = await get_rate_limiter().check_rate_limit("3.3.3.3", None)
    assert ok

"""Tests for the read-aloud client-event sink (BITB-119)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import _normalize_client_event_locale, app  # noqa: E402
from utils.security import require_rate_limit  # noqa: E402


@pytest.fixture(autouse=True)
def _no_db_write():
    """The daily-aggregate upsert needs Postgres; it is asserted separately below."""
    with patch("main.record_tts_event", new=AsyncMock(return_value=True)) as rec:
        yield rec


@pytest.fixture(autouse=True)
def _bypass_rate_limit():
    """The shared limiter needs Postgres; its wiring is asserted separately below."""
    app.dependency_overrides[require_rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(require_rate_limit, None)


client = TestClient(app)

LOCALES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]


EVENTS = ["tts_started", "tts_completed", "tts_start_failed", "tts_error", "tts_unavailable"]


def _attrs(event, locale, platform="web", browser="other", os="other"):
    return {
        "event": event,
        "locale": locale,
        "platform": platform,
        "browser": browser,
        "os": os,
    }


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("locale", LOCALES)
def test_client_events_accepts_whitelisted_event_and_locale(event, locale, _no_db_write):
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json={"event": event, "locale": locale})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # Missing platform/browser/os default to web/other/other.
    counter.add.assert_called_once_with(1, _attrs(event, locale))
    _no_db_write.assert_awaited_once_with(**_attrs(event, locale))


@pytest.mark.parametrize(
    "platform,browser,os",
    [
        ("web", "chrome", "windows"),
        ("web", "firefox", "ios"),
        ("web", "safari", "macos"),
        ("web", "edge", "windows"),
        ("web", "samsung", "android"),
        ("web", "firefox", "linux"),
        ("android", "app", "android"),
    ],
)
def test_client_events_accepts_platform_browser_os_enums(platform, browser, os, _no_db_write):
    body = {
        "event": "tts_start_failed",
        "locale": "de",
        "platform": platform,
        "browser": browser,
        "os": os,
    }
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json=body)
    assert resp.status_code == 200
    expected = _attrs("tts_start_failed", "de", platform, browser, os)
    counter.add.assert_called_once_with(1, expected)
    _no_db_write.assert_awaited_once_with(**expected)


def test_client_events_unknown_platform_browser_os_normalized(_no_db_write):
    body = {
        "event": "tts_error",
        "locale": "en",
        "platform": "smart-fridge",
        "browser": "<script>",
        "os": "BeOS",
    }
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json=body)
    assert resp.status_code == 200
    # Unknown platform falls back to "web"; unknown browser/os to "other".
    counter.add.assert_called_once_with(1, _attrs("tts_error", "en", "web", "other", "other"))


def test_client_events_enum_matching_is_case_insensitive():
    body = {"event": "tts_started", "locale": "en", "browser": " Chrome ", "os": "MacOS"}
    with patch("main.client_tts_events_counter") as counter:
        client.post("/api/v1/client-events", json=body)
    counter.add.assert_called_once_with(1, _attrs("tts_started", "en", "web", "chrome", "macos"))


def test_client_events_db_failure_never_fails_request(_no_db_write):
    _no_db_write.side_effect = None
    _no_db_write.return_value = False
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json={"event": "tts_started", "locale": "en"})
    assert resp.status_code == 200
    counter.add.assert_called_once()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("zh-CN", "zh"),
        ("pt_BR", "pt"),
        ("EN-us", "en"),
        ("xx", "other"),
        ("", "other"),
        ("<script>", "other"),
    ],
)
def test_locale_normalization(raw, expected):
    assert _normalize_client_event_locale(raw) == expected


def test_client_events_unknown_locale_becomes_other():
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json={"event": "tts_started", "locale": "tlh"})
    assert resp.status_code == 200
    counter.add.assert_called_once_with(1, _attrs("tts_started", "other"))


def test_client_events_rejects_unknown_event():
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json={"event": "tts_hacked", "locale": "en"})
    assert resp.status_code == 422
    counter.add.assert_not_called()


def test_client_events_rejects_extra_fields():
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post(
            "/api/v1/client-events",
            json={"event": "tts_started", "locale": "en", "text": "John 3:16"},
        )
    assert resp.status_code == 422
    counter.add.assert_not_called()


def test_client_events_rejects_oversized_locale():
    resp = client.post("/api/v1/client-events", json={"event": "tts_started", "locale": "x" * 40})
    assert resp.status_code == 422


def test_client_events_counter_receives_only_bounded_enum_attributes():
    with patch("main.client_tts_events_counter") as counter:
        client.post(
            "/api/v1/client-events",
            json={"event": "tts_unavailable", "locale": "ko"},
            headers={"User-Agent": "secret-ua", "X-Forwarded-For": "1.2.3.4"},
        )
    attrs = counter.add.call_args.args[1]
    assert set(attrs) == {"event", "locale", "platform", "browser", "os"}
    assert "secret-ua" not in attrs.values()
    assert "1.2.3.4" not in attrs.values()


# ==================== Daily aggregate (BITB-247) ====================


def test_upsert_statement_is_atomic_increment_on_all_dimensions():
    from datetime import date

    from sqlalchemy.dialects import postgresql

    from utils.tts_events import build_tts_event_upsert

    stmt = build_tts_event_upsert(
        day=date(2026, 10, 27),
        event="tts_started",
        locale="it",
        platform="web",
        browser="chrome",
        os="linux",
    )
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO tts_event_daily" in sql
    assert "ON CONFLICT (day, event, locale, platform, browser, os) DO UPDATE" in sql
    # Increment in SQL (not read-modify-write in Python).
    assert "SET count = (tts_event_daily.count + " in sql


@pytest.mark.asyncio
async def test_record_tts_event_executes_upsert_and_commits():
    from utils import tts_events

    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("scripture.database.async_session_factory", factory):
        ok = await tts_events.record_tts_event(
            event="tts_completed", locale="ar", platform="android", browser="app", os="android"
        )

    assert ok is True
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_tts_event_swallows_db_errors():
    from utils import tts_events

    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("relation does not exist"))
    session.commit = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("scripture.database.async_session_factory", factory):
        ok = await tts_events.record_tts_event(
            event="tts_error", locale="en", platform="web", browser="safari", os="ios"
        )

    assert ok is False
    session.commit.assert_not_awaited()


def test_client_events_is_rate_limited():
    from main import report_client_event

    route = next(r for r in app.routes if getattr(r, "path", "") == "/api/v1/client-events")
    assert route.endpoint is report_client_event
    assert any(d.call is require_rate_limit for d in route.dependant.dependencies)

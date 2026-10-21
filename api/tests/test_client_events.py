"""Tests for the read-aloud client-event sink (BITB-119)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import _normalize_client_event_locale, app  # noqa: E402
from utils.security import require_rate_limit  # noqa: E402


@pytest.fixture(autouse=True)
def _bypass_rate_limit():
    """The shared limiter needs Postgres; its wiring is asserted separately below."""
    app.dependency_overrides[require_rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(require_rate_limit, None)


client = TestClient(app)

LOCALES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]


@pytest.mark.parametrize("event", ["tts_started", "tts_unavailable"])
@pytest.mark.parametrize("locale", LOCALES)
def test_client_events_accepts_whitelisted_event_and_locale(event, locale):
    with patch("main.client_tts_events_counter") as counter:
        resp = client.post("/api/v1/client-events", json={"event": event, "locale": locale})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    counter.add.assert_called_once_with(1, {"event": event, "locale": locale})


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
    counter.add.assert_called_once_with(1, {"event": "tts_started", "locale": "other"})


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


def test_client_events_counter_receives_only_event_and_locale():
    with patch("main.client_tts_events_counter") as counter:
        client.post(
            "/api/v1/client-events",
            json={"event": "tts_unavailable", "locale": "ko"},
            headers={"User-Agent": "secret-ua", "X-Forwarded-For": "1.2.3.4"},
        )
    attrs = counter.add.call_args.args[1]
    assert set(attrs) == {"event", "locale"}


def test_client_events_is_rate_limited():
    from main import report_client_event

    route = next(r for r in app.routes if getattr(r, "path", "") == "/api/v1/client-events")
    assert route.endpoint is report_client_event
    assert any(d.call is require_rate_limit for d in route.dependant.dependencies)

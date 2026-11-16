"""
BITB-298: IP-only per-scope rate limits, input caps, honest church User-Agent and the
cached /scripture/stats on the endpoints that cost money or call third parties.
"""

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from feedback.models import ContactRequest, FeedbackRequest
from main import app
from providers import get_embedding_provider
from routes import scripture as scripture_routes
from routes.feedback import get_feedback_repository
from scripture import SearchResults, get_db_session
from utils.rate_limiter import get_rate_limiter, reset_rate_limiter

LIMIT = 2
PROBE = "probe-secret"  # pragma: allowlist secret

# One sample per supported language family that matters for "characters, not bytes":
# Arabic (RTL, 2-byte), Chinese/Korean (3-byte CJK), Hindi (3-byte Devanagari).
MULTIBYTE_CHARS = {"ar": "س", "zh": "圣", "hi": "ह", "ko": "한", "en": "a"}


def _contact_body(**over):
    body = {"email": "a@example.com", "subject": "bug", "message": "hello"}
    body.update(over)
    return body


def _feedback_body(**over):
    body = {
        "message_id": str(uuid.uuid4()),
        "rating": "positive",
        "user_message": "q",
        "assistant_response": "a",
    }
    body.update(over)
    return body


@pytest.fixture(autouse=True)
def limiter_env():
    """Memory-backed limiter, tiny caps, fresh state, IP chosen by the X-Test-IP header."""
    reset_rate_limiter()
    scripture_routes.reset_stats_cache()

    def fake_ip(request):
        return request.headers.get("x-test-ip", "10.0.0.1")

    repo = MagicMock()
    repo.save_feedback = AsyncMock(
        return_value=SimpleNamespace(
            id=1, message_id=uuid.uuid4(), rating="positive", created_at="2026-01-01T00:00:00Z"
        )
    )
    repo.save_contact = AsyncMock(
        return_value=SimpleNamespace(id=1, subject="bug", created_at="2026-01-01T00:00:00Z")
    )
    app.dependency_overrides[get_feedback_repository] = lambda: repo
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    app.dependency_overrides[get_embedding_provider] = lambda: MagicMock()

    search_service = MagicMock()
    search_service.search = AsyncMock(
        return_value=SearchResults(query="hope", verses=[], passages=[])
    )
    search_service.text_search = AsyncMock(return_value=[])

    with (
        patch.object(settings, "rate_limit_enabled", True),
        patch.object(settings, "rate_limit_backend", "memory"),
        patch.object(settings, "turnstile_enabled", False),
        patch.object(settings, "monitor_probe_secret", PROBE),
        patch.object(settings, "rate_limit_search_per_minute", LIMIT),
        patch.object(settings, "rate_limit_feedback_per_minute", LIMIT),
        patch.object(settings, "rate_limit_contact_per_minute", LIMIT),
        patch.object(settings, "rate_limit_church_per_minute", LIMIT),
        patch("utils.security.get_client_ip", fake_ip),
        patch("routes.feedback.email_service.send_feedback_notification", AsyncMock()),
        patch("routes.feedback.email_service.send_contact_notification", AsyncMock()),
        patch("routes.scripture.ScriptureSearchService", return_value=search_service),
        patch(
            "routes.church.httpx.AsyncClient.post",
            new=AsyncMock(
                return_value=httpx.Response(
                    200,
                    json={"results": []},
                    request=httpx.Request("POST", "https://disciplestoday.org"),
                )
            ),
        ),
    ):
        yield TestClient(app)
    app.dependency_overrides.clear()
    reset_rate_limiter()
    scripture_routes.reset_stats_cache()


ROUTES = {
    "search": lambda c, h: c.get("/api/v1/scripture/search", params={"q": "hope"}, headers=h),
    "search_text": lambda c, h: c.get(
        "/api/v1/scripture/search/text", params={"q": "hope"}, headers=h
    ),
    "feedback": lambda c, h: c.post("/api/v1/feedback", json=_feedback_body(), headers=h),
    "contact": lambda c, h: c.post("/api/v1/feedback/contact", json=_contact_body(), headers=h),
    "church": lambda c, h: c.post("/api/v1/church/search", json={"location": "Rome"}, headers=h),
}


class TestPerIpLimit:
    @pytest.mark.parametrize("name", list(ROUTES))
    def test_request_n_plus_one_is_429_and_other_ip_is_ok(self, limiter_env, name):
        call = ROUTES[name]
        h1 = {"X-Test-IP": "1.1.1.1"}
        for _ in range(LIMIT):
            assert call(limiter_env, h1).status_code == 200
        blocked = call(limiter_env, h1)
        assert blocked.status_code == 429
        assert blocked.json()["detail"] == {"error": "Rate limit exceeded", "retry_after": 60}
        assert call(limiter_env, {"X-Test-IP": "2.2.2.2"}).status_code == 200

    def test_search_routes_share_the_search_scope(self, limiter_env):
        h = {"X-Test-IP": "3.3.3.3"}
        assert ROUTES["search"](limiter_env, h).status_code == 200
        assert ROUTES["search_text"](limiter_env, h).status_code == 200
        assert ROUTES["search"](limiter_env, h).status_code == 429

    def test_disabled_limiter_never_blocks(self, limiter_env):
        with patch.object(settings, "rate_limit_enabled", False):
            for _ in range(LIMIT + 3):
                assert ROUTES["contact"](limiter_env, {}).status_code == 200


class TestScopeIndependence:
    @pytest.mark.asyncio
    async def test_exhausted_feedback_does_not_affect_search_or_chat(self, limiter_env):
        h = {"X-Test-IP": "4.4.4.4"}
        for _ in range(LIMIT):
            ROUTES["feedback"](limiter_env, h)
        assert ROUTES["feedback"](limiter_env, h).status_code == 429
        assert ROUTES["search"](limiter_env, h).status_code == 200
        # The chat limiter keys on the bare IP, so the feedback bucket must not touch it.
        allowed, _ = await get_rate_limiter().check_rate_limit("4.4.4.4", None)
        assert allowed

    @pytest.mark.asyncio
    async def test_feedback_posts_do_not_consume_chat_lifetime_cap(self, limiter_env):
        """Regression: feedback bodies carry session_id; it must never count as a chat turn."""
        session = "sess-lifetime"
        with patch.object(settings, "rate_limit_feedback_per_minute", 100):
            for i in range(15):
                r = limiter_env.post(
                    "/api/v1/feedback",
                    json=_feedback_body(session_id=session),
                    headers={"X-Test-IP": f"5.5.5.{i}"},
                )
                assert r.status_code == 200
        allowed, reason = await get_rate_limiter().check_rate_limit("6.6.6.6", session)
        assert allowed, reason
        assert settings.rate_limit_session_max_requests <= 15  # the cap the posts could have eaten


class TestProbeBypass:
    @pytest.mark.parametrize("name", list(ROUTES))
    def test_probe_secret_skips_the_limiter(self, limiter_env, name):
        h = {"X-Test-IP": "7.7.7.7", "X-Monitor-Probe-Secret": PROBE}
        for _ in range(LIMIT + 3):
            assert ROUTES[name](limiter_env, h).status_code == 200

    def test_wrong_probe_secret_does_not_bypass(self, limiter_env):
        h = {"X-Test-IP": "7.7.7.8", "X-Monitor-Probe-Secret": "nope"}
        for _ in range(LIMIT):
            ROUTES["contact"](limiter_env, h)
        assert ROUTES["contact"](limiter_env, h).status_code == 429


class TestFieldCaps:
    @pytest.mark.parametrize(
        "field,cap",
        [("comment", 2000), ("user_message", 2000), ("assistant_response", 20000)],
    )
    @pytest.mark.parametrize("lang", list(MULTIBYTE_CHARS))
    def test_feedback_text_cap_counts_characters(self, field, cap, lang):
        ch = MULTIBYTE_CHARS[lang]
        FeedbackRequest(**_feedback_body(**{field: ch * cap}))
        with pytest.raises(ValidationError):
            FeedbackRequest(**_feedback_body(**{field: ch * (cap + 1)}))

    @pytest.mark.parametrize("lang", list(MULTIBYTE_CHARS))
    def test_contact_message_cap_counts_characters(self, lang):
        ch = MULTIBYTE_CHARS[lang]
        ContactRequest(**_contact_body(message=ch * 5000))
        with pytest.raises(ValidationError):
            ContactRequest(**_contact_body(message=ch * 5001))

    @pytest.mark.parametrize(
        "field,cap",
        [("message_id", 128), ("session_id", 128), ("model_used", 100), ("reason", 40)],
    )
    def test_feedback_short_field_caps(self, field, cap):
        FeedbackRequest(**_feedback_body(**{field: "x" * cap}))
        with pytest.raises(ValidationError):
            FeedbackRequest(**_feedback_body(**{field: "x" * (cap + 1)}))

    def test_verses_cited_item_count_and_length(self):
        FeedbackRequest(**_feedback_body(verses_cited=["J" * 100] * 50))
        with pytest.raises(ValidationError):
            FeedbackRequest(**_feedback_body(verses_cited=["J"] * 51))
        with pytest.raises(ValidationError):
            FeedbackRequest(**_feedback_body(verses_cited=["J" * 101]))

    def test_contact_session_and_user_agent_caps(self):
        ContactRequest(**_contact_body(user_agent="u" * 500, session_id="s" * 128))
        with pytest.raises(ValidationError):
            ContactRequest(**_contact_body(user_agent="u" * 501))
        with pytest.raises(ValidationError):
            ContactRequest(**_contact_body(session_id="s" * 129))

    def test_over_cap_is_422_over_http(self, limiter_env):
        r = limiter_env.post("/api/v1/feedback/contact", json=_contact_body(message="x" * 5001))
        assert r.status_code == 422
        r = limiter_env.post("/api/v1/feedback", json=_feedback_body(comment="x" * 2001))
        assert r.status_code == 422

    @pytest.mark.parametrize("path", ["/api/v1/scripture/search", "/api/v1/scripture/search/text"])
    def test_q_201_chars_is_422_and_200_is_ok(self, limiter_env, path):
        assert limiter_env.get(path, params={"q": "a" * 200}).status_code == 200
        assert limiter_env.get(path, params={"q": "a" * 201}).status_code == 422

    @pytest.mark.parametrize("lang", list(MULTIBYTE_CHARS))
    def test_church_location_cap(self, limiter_env, lang):
        ch = MULTIBYTE_CHARS[lang]
        assert (
            limiter_env.post("/api/v1/church/search", json={"location": ch * 200}).status_code
            == 200
        )
        assert (
            limiter_env.post("/api/v1/church/search", json={"location": ch * 201}).status_code
            == 422
        )


class TestStatsCache:
    def test_two_calls_hit_the_database_once(self, limiter_env):
        stats = {"books": 66, "verses": 31102}
        with patch("routes.scripture.ScriptureRepository") as repo_cls:
            repo_cls.return_value.get_stats = AsyncMock(return_value=stats)
            assert limiter_env.get("/api/v1/scripture/stats").json() == stats
            assert limiter_env.get("/api/v1/scripture/stats").json() == stats
            assert repo_cls.return_value.get_stats.await_count == 1

    def test_cache_expires_after_ttl(self, limiter_env):
        with (
            patch("routes.scripture.ScriptureRepository") as repo_cls,
            patch.object(
                scripture_routes,
                "time",
                SimpleNamespace(monotonic=MagicMock(side_effect=[1000.0, 1000.0 + 301.0])),
            ),
        ):
            repo_cls.return_value.get_stats = AsyncMock(return_value={"books": 66})
            limiter_env.get("/api/v1/scripture/stats")
            limiter_env.get("/api/v1/scripture/stats")
            assert repo_cls.return_value.get_stats.await_count == 2


class TestChurchHonestHeaders:
    def test_outbound_request_identifies_voxquieta(self, limiter_env):
        post = AsyncMock(
            return_value=httpx.Response(
                200, json={"results": []}, request=httpx.Request("POST", "https://x")
            )
        )
        with patch("routes.church.httpx.AsyncClient.post", new=post):
            assert (
                limiter_env.post("/api/v1/church/search", json={"location": "Rome"}).status_code
                == 200
            )
        headers = post.await_args.kwargs["headers"]
        assert headers["User-Agent"] == f"VoxQuieta/{settings.app_version} (+https://voxquieta.org)"
        lowered = {k.lower() for k in headers}
        assert "origin" not in lowered and "referer" not in lowered
        assert "mozilla" not in headers["User-Agent"].lower()


class TestTelemetryUnchanged:
    """Requirement 8: client-events/-errors bodies carry no session_id, so they stay on the
    shared limiter; this pins that assumption so adding a session_id later fails loudly."""

    def test_bodies_have_no_session_id(self):
        import main

        assert "session_id" not in main.ClientErrorReport.model_fields
        assert "session_id" not in main.ClientEvent.model_fields

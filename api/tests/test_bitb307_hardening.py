"""BITB-307: trimmed /config, generic upstream errors, bounded metric labels, tight CORS."""

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import main  # noqa: E402
from config import settings  # noqa: E402
from main import PUBLIC_CONFIG_KEYS, app, get_cors_middleware_kwargs  # noqa: E402
from providers import ProviderError, get_embedding_provider, get_llm_provider  # noqa: E402
from scripture import get_db_session  # noqa: E402
from utils.security import check_content_filter, require_rate_limit  # noqa: E402
from utils.turnstile import require_turnstile  # noqa: E402

SECRET = "probe-secret"  # pragma: allowlist secret
PROD_ORIGIN = "https://voxquieta.org"
LOCAL_ORIGIN = "http://localhost:3000"


# ==================== /config ====================


def test_public_config_keys_match_allowlist():
    """Adding a field to /config must be a deliberate act (update PUBLIC_CONFIG_KEYS)."""
    data = TestClient(app).get("/config").json()
    assert {k: set(v) for k, v in data.items()} == PUBLIC_CONFIG_KEYS
    assert PUBLIC_CONFIG_KEYS == {
        "chat": {"max_message_length", "session_max_requests"},
        "features": {"tts_enabled"},
        "security": {"turnstile_enabled", "turnstile_site_key"},
    }


def test_public_config_has_no_provider_or_model_names():
    body = TestClient(app).get("/config").text.lower()
    for needle in (
        settings.llm_provider,
        settings.llm_model,
        settings.openrouter_model,
        settings.embedding_provider,
        settings.embedding_model,
        "llm",
        "embedding",
        "telemetry",
        "appinsights",
    ):
        assert needle.lower() not in body


def test_admin_config_requires_probe_secret():
    client = TestClient(app)
    with patch.object(settings, "monitor_probe_secret", SECRET):
        assert client.get("/api/v1/admin/config").status_code == 401
        resp = client.get("/api/v1/admin/config", headers={"X-Monitor-Probe-Secret": "nope"})
        assert resp.status_code == 401
    with patch.object(settings, "monitor_probe_secret", None):
        resp = client.get("/api/v1/admin/config", headers={"X-Monitor-Probe-Secret": SECRET})
        assert resp.status_code == 401


def test_admin_config_returns_full_detail_with_secret():
    client = TestClient(app)
    with patch.object(settings, "monitor_probe_secret", SECRET):
        resp = client.get("/api/v1/admin/config", headers={"X-Monitor-Probe-Secret": SECRET})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == set(PUBLIC_CONFIG_KEYS) | {"llm", "embedding", "telemetry"}
    assert data["llm"]["provider"] == settings.llm_provider
    expected_model = (
        settings.openrouter_model if settings.llm_provider == "openrouter" else settings.llm_model
    )
    assert data["llm"]["model"] == expected_model
    assert data["embedding"]["dimensions"] == settings.embedding_dimensions
    assert "appinsights_configured" in data["telemetry"]


# ==================== Generic upstream errors ====================


def test_provider_error_body_is_generic_and_logged(caplog):
    sentinel = "SENTINEL-upstream-secret-4242 http://ollama:11434"

    @app.get("/test-bitb307-provider-error")
    async def _boom():
        raise ProviderError(sentinel)

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        resp = client.get("/test-bitb307-provider-error")
    assert resp.status_code == 503
    body = resp.json()
    assert body == {
        "error": "LLM Provider Error",
        "detail": "The AI service is temporarily unavailable.",
    }
    assert "SENTINEL" not in resp.text
    assert "ollama" not in resp.text.lower()
    assert sentinel in caplog.text


# ==================== Metric label ====================


async def _noop() -> None:
    return None


async def _fake_db():
    yield object()


@pytest.fixture
def chat_client():
    llm = MagicMock()
    for dep in (require_turnstile, require_rate_limit, check_content_filter):
        app.dependency_overrides[dep] = _noop
    app.dependency_overrides[get_llm_provider] = lambda: llm
    app.dependency_overrides[get_embedding_provider] = lambda: MagicMock()
    app.dependency_overrides[get_db_session] = _fake_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _fake_service():
    from chat import ChatResponse

    svc = MagicMock()
    svc.chat = AsyncMock(
        return_value=ChatResponse(message_id="m1", message="hi", provider="test", model="test")
    )

    async def _stream(*_a, **_k):
        yield {"type": "token", "content": "hi"}

    svc.chat_stream = _stream
    return svc


@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
def test_sessions_counter_has_no_session_token_attribute(chat_client, path):
    with (
        patch("routes.chat.ChatService", return_value=_fake_service()),
        patch("routes.chat.track_session", new=AsyncMock()),
        patch("routes.chat.chat_sessions_counter") as counter,
    ):
        resp = chat_client.post(path, json={"message": "hello", "session_id": "sess-abc-123"})
        assert resp.status_code == 200, resp.text
    counter.add.assert_called_once_with(1)


# ==================== CORS ====================


def test_cors_origins_exclude_localhost_by_default():
    with (
        patch.object(settings, "debug", False),
        patch.object(settings, "cors_allow_localhost", False),
        patch.object(settings, "cors_origins", ""),
    ):
        origins = main._get_cors_origins()
    assert settings.production_frontend_url in origins
    assert not any("localhost" in o or "127.0.0.1" in o for o in origins)


@pytest.mark.parametrize("debug,flag", [(True, False), (False, True)])
def test_cors_origins_include_localhost_when_opted_in(debug, flag):
    with (
        patch.object(settings, "debug", debug),
        patch.object(settings, "cors_allow_localhost", flag),
    ):
        origins = main._get_cors_origins()
    for o in (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ):
        assert o in origins


def _cors_app(debug: bool, flag: bool) -> TestClient:
    with (
        patch.object(settings, "debug", debug),
        patch.object(settings, "cors_allow_localhost", flag),
        patch.object(settings, "cors_origins", ""),
        patch.object(settings, "production_frontend_url", PROD_ORIGIN),
    ):
        kwargs = get_cors_middleware_kwargs()
    small = FastAPI()
    small.add_middleware(CORSMiddleware, **kwargs)

    @small.post("/x")
    async def _x():
        return {"ok": True}

    return TestClient(small)


def _preflight(client, origin, method="POST", headers="Content-Type"):
    return client.options(
        "/x",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_cors_prod_origin_allowed():
    resp = _preflight(_cors_app(False, False), PROD_ORIGIN)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == PROD_ORIGIN
    assert "access-control-allow-credentials" not in resp.headers


def test_cors_localhost_rejected_when_flag_unset():
    resp = _preflight(_cors_app(False, False), LOCAL_ORIGIN)
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_cors_localhost_allowed_with_flag():
    resp = _preflight(_cors_app(False, True), LOCAL_ORIGIN)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == LOCAL_ORIGIN


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH"])
def test_cors_disallowed_method_rejected(method):
    resp = _preflight(_cors_app(False, False), PROD_ORIGIN, method=method)
    assert resp.status_code == 400


def test_cors_disallowed_header_rejected():
    resp = _preflight(_cors_app(False, False), PROD_ORIGIN, headers="X-Evil-Header")
    assert resp.status_code == 400


def test_cors_client_headers_allowed():
    resp = _preflight(
        _cors_app(False, False),
        PROD_ORIGIN,
        headers="Content-Type, X-Turnstile-Token, X-Monitor-Probe-Secret, X-Request-ID",
    )
    assert resp.status_code == 200

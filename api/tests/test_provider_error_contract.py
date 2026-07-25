"""
Contract tests for BITB-063: the OpenRouter provider's model-exhaustion error
must stay a type the chat routes actually catch.

These tests fail if EITHER side of the contract drifts:
- the provider stops raising `AllModelsExhaustedError` on exhaustion, or
- the routes stop catching that type and mapping it to a 503 / error chunk.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from openai import APIStatusError

from chat.service import ChatRequest
from providers import AllModelsExhaustedError
from providers.openrouter import OpenRouterProvider
from routes.chat import chat, chat_stream


def _make_provider(**kwargs):
    defaults = {
        "api_key": "sk-or-v1-test-key",  # pragma: allowlist secret
        "model": "primary-model",
        "fallback_models": ["fallback-model"],
        "allow_fallbacks": True,
    }
    defaults.update(kwargs)
    return OpenRouterProvider(**defaults)


def _rate_limit_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {}
    return APIStatusError(message="Rate limited", response=mock_resp, body={})


class TestProviderRaisesTypedError:
    """Provider side: exhaustion must raise AllModelsExhaustedError, not RuntimeError."""

    @pytest.mark.asyncio
    async def test_chat_provider_exhaustion_raises_typed(self):
        provider = _make_provider()

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=_rate_limit_error(),
        ):
            with pytest.raises(AllModelsExhaustedError) as exc:
                await provider.chat([])

        assert exc.value.reason == "rate_limited"
        assert exc.value.models_tried == ["primary-model", "fallback-model"]

    @pytest.mark.asyncio
    async def test_chat_stream_provider_exhaustion_raises_typed(self):
        provider = _make_provider()

        async def always_fails(**kwargs):
            raise _rate_limit_error()

        with patch.object(
            provider._client.chat.completions,
            "create",
            side_effect=always_fails,
        ):
            with pytest.raises(AllModelsExhaustedError) as exc:
                async for _ in provider.chat_stream([]):
                    pass

        assert exc.value.reason == "rate_limited"
        assert exc.value.models_tried == ["primary-model", "fallback-model"]


class TestRouteMapsTypedError:
    """Route side: AllModelsExhaustedError must map to 503 / an error chunk."""

    @staticmethod
    def _mock_http_request():
        mock_req = MagicMock()
        mock_req.headers = {"user-agent": "test-agent", "accept-language": "en-US"}
        return mock_req

    @pytest.mark.asyncio
    async def test_route_maps_typed_error_to_503(self):
        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()
        mock_http = self._mock_http_request()
        request = ChatRequest(message="Hello")

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.chat = AsyncMock(
                side_effect=AllModelsExhaustedError(
                    "All models unavailable",
                    reason="unavailable",
                    models_tried=["primary-model", "fallback-model"],
                )
            )
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await chat(request, mock_http, mock_db, mock_llm, mock_embedding)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "upstream_unavailable"
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_stream_route_maps_typed_error_to_error_chunk(self):
        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()
        mock_http = self._mock_http_request()
        request = ChatRequest(message="Hello")

        async def mock_gen(req):
            raise AllModelsExhaustedError(
                "All models unavailable in streaming",
                reason="rate_limited",
                models_tried=["primary-model", "fallback-model"],
            )
            yield  # pragma: no cover - unreachable, makes this an async generator

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.chat_stream = mock_gen
            mock_service_cls.return_value = mock_service

            response = await chat_stream(request, mock_http, mock_db, mock_llm, mock_embedding)

            chunks = [chunk async for chunk in response.body_iterator]

        assert any("upstream_unavailable" in chunk for chunk in chunks)
        assert any('"error_code"' in chunk for chunk in chunks)

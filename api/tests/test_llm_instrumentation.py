"""
Tests for LLM performance instrumentation.

Verifies that:
- OTel spans are created for each LLM operation (chat and streaming)
- Span attributes are correct (provider, model, duration, streaming, TTFT, request_id)
- Fallback detection works (OpenRouter)
- Rate limit detection works (OpenRouter)
- Metrics are recorded correctly
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.context import REQUEST_ID_CTX_VAR


class TestLLMTelemetryModule:
    """Verify the telemetry module has LLM tracer and metrics."""

    def test_llm_tracer_is_not_none(self):
        """LLM tracer should be initialized."""
        from utils.telemetry import llm_tracer

        assert llm_tracer is not None

    def test_llm_metrics_are_not_none(self):
        """LLM metrics should be initialized."""
        from utils.telemetry import (
            llm_duration_histogram,
            llm_fallback_attempts_counter,
            llm_rate_limit_hits_counter,
            llm_tokens_per_second_histogram,
            llm_tokens_total_counter,
            llm_ttft_histogram,
        )

        assert llm_duration_histogram is not None
        assert llm_ttft_histogram is not None
        assert llm_tokens_per_second_histogram is not None
        assert llm_tokens_total_counter is not None
        assert llm_fallback_attempts_counter is not None
        assert llm_rate_limit_hits_counter is not None


class TestChatServiceSpans:
    """Verify ChatService creates spans with correct attributes."""

    @pytest.mark.asyncio
    async def test_chat_creates_span_with_attributes(self):
        """chat() creates a span with provider, model, duration, streaming=false."""
        from chat.service import ChatService
        from providers.base import LLMResponse

        # Mock dependencies
        mock_db_session = AsyncMock()
        mock_llm_provider = AsyncMock()
        mock_embedding_provider = AsyncMock()

        # Mock LLM response
        mock_response = LLMResponse(
            content="Test response",
            model="test-model",
            provider="test-provider",
            tokens_used=50,
        )
        mock_llm_provider.chat = AsyncMock(return_value=mock_response)

        # Mock search service
        with patch("chat.service.ScriptureSearchService"):
            service = ChatService(mock_db_session, mock_llm_provider, mock_embedding_provider)

            # Mock the search to return no results
            service.search_service.search = AsyncMock(return_value=None)

            with patch("chat.service.llm_tracer") as mock_tracer:
                mock_span = MagicMock()
                mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                    return_value=mock_span
                )
                mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                    return_value=False
                )

                # Set a request ID
                token = REQUEST_ID_CTX_VAR.set("test-request-123")
                try:
                    from chat.service import ChatRequest

                    request = ChatRequest(message="Test message", include_search=False)
                    await service.chat(request)

                    # Verify span was created
                    mock_tracer.start_as_current_span.assert_called_once_with("llm.chat")

                    # Verify attributes were set
                    calls = {
                        call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list
                    }
                    assert calls["llm.provider"] == "test-provider"
                    assert calls["llm.model"] == "test-model"
                    assert calls["llm.streaming"] is False
                    assert "llm.duration_ms" in calls
                    assert calls["request_id"] == "test-request-123"
                finally:
                    REQUEST_ID_CTX_VAR.reset(token)


class TestChatStreamSpans:
    """Verify ChatService.chat_stream tracks TTFT and creates spans."""

    @pytest.mark.asyncio
    async def test_chat_stream_creates_span_with_ttft(self):
        """chat_stream() creates a span and tracks TTFT."""
        from chat.service import ChatService

        # Mock dependencies
        mock_db_session = AsyncMock()
        mock_llm_provider = AsyncMock()
        mock_embedding_provider = AsyncMock()

        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        mock_llm_provider.chat_stream = mock_stream

        # Mock search service
        with patch("chat.service.ScriptureSearchService"):
            service = ChatService(mock_db_session, mock_llm_provider, mock_embedding_provider)
            service.search_service.search = AsyncMock(return_value=None)

            with patch("chat.service.llm_tracer") as mock_tracer:
                mock_span = MagicMock()
                mock_tracer.start_span.return_value = mock_span

                from chat.service import ChatRequest

                request = ChatRequest(message="Test message", include_search=False)

                # Consume the stream
                chunks = []
                async for chunk in service.chat_stream(request):
                    chunks.append(chunk)

                # Verify span was created
                mock_tracer.start_span.assert_called_once_with("llm.chat_stream")

                # Verify span.end() was called
                mock_span.end.assert_called_once()

                # Verify attributes include TTFT and duration
                calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
                assert calls["llm.streaming"] is True
                assert "llm.duration_ms" in calls
                assert "llm.ttft_ms" in calls


class TestOpenRouterFallback:
    """Verify OpenRouter fallback detection and span attributes."""

    @pytest.mark.asyncio
    async def test_fallback_triggered_sets_span_attribute(self):
        """Fallback sets llm.fallback.triggered=True and llm.fallback.model."""
        from openai import RateLimitError

        from providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key="test-key",  # pragma: allowlist secret
            model="primary-model",
            fallback_models=["fallback-model"],
            allow_fallbacks=True,
        )

        # Mock the client
        mock_client = AsyncMock()
        provider._client = mock_client

        # Mock response for fallback
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.model = "fallback-model"

        # First call raises RateLimitError, second succeeds
        mock_client.chat.completions.create.side_effect = [
            RateLimitError("Rate limit exceeded", response=MagicMock(), body={}),
            mock_response,
        ]

        with patch("providers.openrouter.llm_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            from providers.base import ChatMessage

            messages = [ChatMessage(role="user", content="Test")]
            await provider.chat(messages)

            # Verify fallback attributes
            calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
            assert calls.get("llm.fallback.triggered") is True
            assert calls.get("llm.fallback.model") == "fallback-model"


class TestOpenRouterRateLimit:
    """Verify OpenRouter rate limit detection."""

    @pytest.mark.asyncio
    async def test_rate_limit_hit_sets_span_attribute(self):
        """Rate limit error sets llm.rate_limit.hit=True and increments counter."""
        from openai import RateLimitError

        from providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key="test-key",  # pragma: allowlist secret
            model="test-model",
            allow_fallbacks=False,
        )

        # Mock the client
        mock_client = AsyncMock()
        provider._client = mock_client

        # Mock RateLimitError with no fallback
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded", response=MagicMock(), body={}
        )

        with patch("providers.openrouter.llm_tracer") as mock_tracer:
            with patch("providers.openrouter.llm_rate_limit_hits_counter") as mock_counter:
                mock_span = MagicMock()
                mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                    return_value=mock_span
                )
                mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                    return_value=False
                )

                from providers.base import ChatMessage

                messages = [ChatMessage(role="user", content="Test")]

                try:
                    await provider.chat(messages)
                except RateLimitError:
                    pass  # Expected

                # Verify rate limit attribute
                calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
                assert calls.get("llm.rate_limit.hit") is True

                # Verify counter was incremented
                mock_counter.add.assert_called_once()


class TestClaudeProviderSpans:
    """Verify Claude provider creates spans."""

    @pytest.mark.asyncio
    async def test_claude_chat_creates_span(self):
        """Claude chat() creates a span with correct attributes."""
        from providers.claude import ClaudeProvider

        provider = ClaudeProvider(
            api_key="test-key",  # pragma: allowlist secret
            model="claude-test",
        )

        # Mock the client
        mock_client = AsyncMock()
        provider._client = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].type = "text"
        mock_response.content[0].text = "Test response"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_response.stop_reason = "end_turn"

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("providers.claude.llm_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            from providers.base import ChatMessage

            messages = [ChatMessage(role="user", content="Test")]
            await provider.chat(messages)

            # Verify span was created
            mock_tracer.start_as_current_span.assert_called_once_with("llm.claude.chat")

            # Verify attributes
            calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
            assert calls["llm.provider"] == "claude"
            assert calls["llm.model"] == "claude-test"
            assert calls["llm.streaming"] is False
            assert "llm.duration_ms" in calls


class TestOllamaProviderSpans:
    """Verify Ollama provider creates spans."""

    @pytest.mark.asyncio
    async def test_ollama_chat_creates_span(self):
        """Ollama chat() creates a span with correct attributes."""
        from providers.ollama import OllamaProvider

        provider = OllamaProvider(host="http://localhost:11434", model="llama3:8b")

        # Mock the client
        mock_client = AsyncMock()
        provider._client = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Test response"},
            "eval_count": 50,
            "done_reason": "stop",
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("providers.ollama.llm_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            from providers.base import ChatMessage

            messages = [ChatMessage(role="user", content="Test")]
            await provider.chat(messages)

            # Verify span was created
            mock_tracer.start_as_current_span.assert_called_once_with("llm.ollama.chat")

            # Verify attributes
            calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
            assert calls["llm.provider"] == "ollama"
            assert calls["llm.model"] == "llama3:8b"
            assert calls["llm.streaming"] is False
            assert "llm.duration_ms" in calls

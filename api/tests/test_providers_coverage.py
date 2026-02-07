"""
Comprehensive tests for LLM and embedding provider implementations.

Covers: providers/claude.py, providers/ollama.py, providers/azure_openai.py,
providers/factory.py, providers/base.py, providers/openrouter.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ChatMessage, EmbeddingResponse, LLMResponse

# =============================================================================
# Claude Provider Tests
# =============================================================================


class TestClaudeProvider:
    """Tests for the Claude (Anthropic) LLM provider."""

    def _make_provider(self):
        with patch("providers.claude.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            from providers.claude import ClaudeProvider

            provider = ClaudeProvider(
                api_key="test-key",  # pragma: allowlist secret
                model="claude-sonnet-4-20250514",
            )
            return provider, mock_client

    def test_provider_name(self):
        """Claude provider should return 'claude' as its name."""
        provider, _ = self._make_provider()
        assert provider.provider_name == "claude"

    def test_model_stored(self):
        """Claude provider should store the model name."""
        provider, _ = self._make_provider()
        assert provider.model == "claude-sonnet-4-20250514"

    def test_convert_messages_extracts_system(self):
        """_convert_messages should extract system message separately."""
        provider, _ = self._make_provider()
        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there"),
        ]
        system_prompt, converted = provider._convert_messages(messages)
        assert system_prompt == "You are helpful"
        assert len(converted) == 2
        assert converted[0] == {"role": "user", "content": "Hello"}
        assert converted[1] == {"role": "assistant", "content": "Hi there"}

    def test_convert_messages_no_system(self):
        """_convert_messages should handle messages without system prompt."""
        provider, _ = self._make_provider()
        messages = [
            ChatMessage(role="user", content="Hello"),
        ]
        system_prompt, converted = provider._convert_messages(messages)
        assert system_prompt is None
        assert len(converted) == 1

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Claude chat should return LLMResponse on success."""
        provider, mock_client = self._make_provider()

        # Mock response
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Hello! How can I help?"

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_response.stop_reason = "end_turn"

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role="user", content="Hi")]
        result = await provider.chat(messages)

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello! How can I help?"
        assert result.provider == "claude"
        assert result.tokens_used == 30
        assert result.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self):
        """Claude chat should pass system prompt when present."""
        provider, mock_client = self._make_provider()

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Response"

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 5
        mock_response.stop_reason = "end_turn"

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        messages = [
            ChatMessage(role="system", content="Be helpful"),
            ChatMessage(role="user", content="Hi"),
        ]
        await provider.chat(messages)

        # Verify system was passed
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "Be helpful"

    @pytest.mark.asyncio
    async def test_chat_multiple_text_blocks(self):
        """Claude chat should concatenate multiple text blocks."""
        provider, mock_client = self._make_provider()

        block1 = MagicMock()
        block1.type = "text"
        block1.text = "Part 1 "

        block2 = MagicMock()
        block2.type = "text"
        block2.text = "Part 2"

        block3 = MagicMock()
        block3.type = "tool_use"  # Non-text block should be skipped

        mock_response = MagicMock()
        mock_response.content = [block1, block2, block3]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 10
        mock_response.stop_reason = "end_turn"

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.chat([ChatMessage(role="user", content="Hi")])
        assert result.content == "Part 1 Part 2"

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """Claude chat_stream should yield text chunks."""
        provider, mock_client = self._make_provider()

        # Create mock stream context manager
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        async def text_stream_gen():
            yield "Hello"
            yield " world"

        mock_stream.text_stream = text_stream_gen()
        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        messages = [ChatMessage(role="user", content="Hi")]
        chunks = []
        async for chunk in provider.chat_stream(messages):
            chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Claude health_check should return True on success."""
        provider, mock_client = self._make_provider()

        mock_response = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Claude health_check should return False on exception."""
        provider, mock_client = self._make_provider()

        mock_client.messages.create = AsyncMock(side_effect=Exception("Connection failed"))

        result = await provider.health_check()
        assert result is False


# =============================================================================
# Ollama Provider Tests
# =============================================================================


class TestOllamaProvider:
    """Tests for the Ollama LLM provider."""

    def _make_provider(self):
        from providers.ollama import OllamaProvider

        return OllamaProvider(host="http://localhost:11434", model="llama3:8b")

    def test_provider_name(self):
        provider = self._make_provider()
        assert provider.provider_name == "ollama"

    def test_host_trailing_slash_stripped(self):
        from providers.ollama import OllamaProvider

        provider = OllamaProvider(host="http://localhost:11434/", model="llama3:8b")
        assert provider.host == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_get_client_creates_once(self):
        """_get_client should create client on first call and reuse it."""
        provider = self._make_provider()
        assert provider._client is None

        client1 = await provider._get_client()
        assert client1 is not None

        client2 = await provider._get_client()
        assert client1 is client2

        await provider.close()

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Ollama chat should return LLMResponse on success."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Test response"},
            "eval_count": 42,
            "done_reason": "stop",
        }

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.chat([ChatMessage(role="user", content="Hi")])

        assert isinstance(result, LLMResponse)
        assert result.content == "Test response"
        assert result.provider == "ollama"
        assert result.tokens_used == 42
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """Ollama chat_stream should yield content chunks."""
        provider = self._make_provider()

        async def mock_aiter_lines():
            yield '{"message": {"content": "Hello"}}'
            yield '{"message": {"content": " world"}}'
            yield '{"done": true}'

        mock_stream_response = AsyncMock()
        mock_stream_response.raise_for_status = MagicMock()
        mock_stream_response.aiter_lines = mock_aiter_lines
        mock_stream_response.__aenter__ = AsyncMock(return_value=mock_stream_response)
        mock_stream_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=mock_stream_response)
            mock_get_client.return_value = mock_client

            chunks = []
            async for chunk in provider.chat_stream([ChatMessage(role="user", content="Hi")]):
                chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_health_check_model_available(self):
        """health_check should return True if model is in tags."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "llama3:8b"}, {"name": "mistral:7b"}]
        }

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_model_not_available(self):
        """health_check should return False if model not found."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "mistral:7b"}]}

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """health_check should return False on connection error."""
        provider = self._make_provider()

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_get_client.return_value = mock_client

            result = await provider.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_close(self):
        """close should clean up the HTTP client."""
        provider = self._make_provider()
        # Create a client first
        provider._client = AsyncMock()

        await provider.close()

        provider._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        """close should be safe when no client exists."""
        provider = self._make_provider()
        await provider.close()  # Should not raise


# =============================================================================
# Ollama Embedding Provider Tests
# =============================================================================


class TestOllamaEmbeddingProvider:
    """Tests for the Ollama Embedding provider."""

    def _make_provider(self):
        from providers.ollama import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(
            host="http://localhost:11434",
            model="mxbai-embed-large",
            dimensions=1024,
        )

    def test_provider_name(self):
        provider = self._make_provider()
        assert provider.provider_name == "ollama"

    def test_dimensions(self):
        provider = self._make_provider()
        assert provider.dimensions == 1024

    def test_host_trailing_slash_stripped(self):
        from providers.ollama import OllamaEmbeddingProvider

        provider = OllamaEmbeddingProvider(
            host="http://localhost:11434/", model="test", dimensions=768
        )
        assert provider.host == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_embed_success(self):
        """embed should return EmbeddingResponse."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.embed("test text")

        assert isinstance(result, EmbeddingResponse)
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.model == "mxbai-embed-large"
        assert result.provider == "ollama"

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """embed_batch should return list of EmbeddingResponse."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1 * call_count]}
            return mock_resp

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            results = await provider.embed_batch(["text1", "text2"])

        assert len(results) == 2
        assert all(isinstance(r, EmbeddingResponse) for r in results)

    @pytest.mark.asyncio
    async def test_health_check_model_available(self):
        """health_check should return True if embedding model is available."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "mxbai-embed-large:latest"}]}

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """health_check should return False on error."""
        provider = self._make_provider()

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("fail"))
            mock_get_client.return_value = mock_client

            result = await provider.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_close(self):
        """close should clean up HTTP client."""
        provider = self._make_provider()
        provider._client = AsyncMock()
        await provider.close()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        """close should be safe with no client."""
        provider = self._make_provider()
        await provider.close()


# =============================================================================
# Azure OpenAI Embedding Provider Tests
# =============================================================================


class TestAzureOpenAIEmbeddingProvider:
    """Tests for the Azure OpenAI Embedding provider."""

    def _make_provider(self):
        with patch("providers.azure_openai.AsyncAzureOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            from providers.azure_openai import AzureOpenAIEmbeddingProvider

            provider = AzureOpenAIEmbeddingProvider(
                endpoint="https://test.openai.azure.com/",
                api_key="test-key",  # pragma: allowlist secret
                deployment_name="text-embedding-3-small",
                dimensions=1536,
            )
            return provider, mock_client

    def test_provider_name(self):
        provider, _ = self._make_provider()
        assert provider.provider_name == "azure_openai"

    def test_dimensions(self):
        provider, _ = self._make_provider()
        assert provider.dimensions == 1536

    def test_endpoint_trailing_slash_stripped(self):
        provider, _ = self._make_provider()
        assert provider.endpoint == "https://test.openai.azure.com"

    @pytest.mark.asyncio
    async def test_embed_success(self):
        """embed should return EmbeddingResponse."""
        provider, mock_client = self._make_provider()

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3]

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed("test text")

        assert isinstance(result, EmbeddingResponse)
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.model == "text-embedding-3-small"
        assert result.provider == "azure_openai"

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """embed_batch should handle batch embedding."""
        provider, mock_client = self._make_provider()

        mock_emb1 = MagicMock()
        mock_emb1.embedding = [0.1]
        mock_emb2 = MagicMock()
        mock_emb2.embedding = [0.2]

        mock_response = MagicMock()
        mock_response.data = [mock_emb1, mock_emb2]

        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        results = await provider.embed_batch(["text1", "text2"])

        assert len(results) == 2
        assert results[0].embedding == [0.1]
        assert results[1].embedding == [0.2]

    @pytest.mark.asyncio
    async def test_embed_batch_large_batches(self):
        """embed_batch should chunk large batches into groups of 100."""
        provider, mock_client = self._make_provider()

        def make_response(n):
            mock_response = MagicMock()
            mock_response.data = []
            for i in range(n):
                mock_emb = MagicMock()
                mock_emb.embedding = [float(i)]
                mock_response.data.append(mock_emb)
            return mock_response

        # 150 texts should be split into batches of 100 + 50
        mock_client.embeddings.create = AsyncMock(
            side_effect=[make_response(100), make_response(50)]
        )

        texts = [f"text {i}" for i in range(150)]
        results = await provider.embed_batch(texts)

        assert len(results) == 150
        assert mock_client.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """health_check should return True on success."""
        provider, mock_client = self._make_provider()
        mock_client.embeddings.create = AsyncMock(return_value=MagicMock())

        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """health_check should return False on error."""
        provider, mock_client = self._make_provider()
        mock_client.embeddings.create = AsyncMock(side_effect=Exception("fail"))

        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_close_is_noop(self):
        """close should be a no-op for Azure OpenAI."""
        provider, _ = self._make_provider()
        await provider.close()  # Should not raise


# =============================================================================
# Provider Factory Tests
# =============================================================================


class TestProviderFactory:
    """Tests for the provider factory."""

    def test_create_claude_provider(self):
        """Factory should create Claude provider with API key."""
        from config import Settings
        from providers.factory import create_llm_provider

        config = Settings(
            llm_provider="claude",
            llm_model="claude-sonnet-4-20250514",
            anthropic_api_key="test-key",  # pragma: allowlist secret
        )
        provider = create_llm_provider(config)
        assert provider.provider_name == "claude"

    def test_create_claude_requires_api_key(self):
        """Factory should raise ProviderError for Claude without API key."""
        from config import Settings
        from providers.factory import ProviderError, create_llm_provider

        config = Settings(
            llm_provider="claude",
            llm_model="claude-sonnet-4-20250514",
            anthropic_api_key=None,
        )
        with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
            create_llm_provider(config)

    def test_create_openai_raises_not_implemented(self):
        """Factory should raise ProviderError for OpenAI (not yet implemented)."""
        from config import Settings
        from providers.factory import ProviderError, create_llm_provider

        config = Settings(llm_provider="openai", llm_model="gpt-4")
        with pytest.raises(ProviderError, match="not yet implemented"):
            create_llm_provider(config)

    def test_create_unknown_provider_raises(self):
        """Factory should raise ProviderError for unknown provider."""
        from providers.factory import ProviderError, create_llm_provider

        # Settings validates llm_provider via Literal type, so we mock it
        config = MagicMock()
        config.llm_provider = "unknown_provider"
        with pytest.raises(ProviderError, match="Unknown LLM provider"):
            create_llm_provider(config)

    def test_create_embedding_ollama(self):
        """Factory should create Ollama embedding provider."""
        from config import Settings
        from providers.factory import create_embedding_provider
        from providers.ollama import OllamaEmbeddingProvider

        config = Settings(
            embedding_provider="ollama",
            embedding_model="mxbai-embed-large",
            embedding_dimensions=1024,
            ollama_host="http://localhost:11434",
        )
        provider = create_embedding_provider(config)
        assert isinstance(provider, OllamaEmbeddingProvider)

    def test_create_embedding_azure_openai(self):
        """Factory should create Azure OpenAI embedding provider."""
        from config import Settings
        from providers.factory import create_embedding_provider

        config = Settings(
            embedding_provider="azure_openai",
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_api_key="test-key",  # pragma: allowlist secret
            azure_embedding_deployment="text-embedding-3-small",
            embedding_dimensions=1536,
        )
        provider = create_embedding_provider(config)
        assert provider.provider_name == "azure_openai"

    def test_create_embedding_azure_requires_endpoint(self):
        """Factory should raise if Azure endpoint is missing."""
        from config import Settings
        from providers.factory import ProviderError, create_embedding_provider

        config = Settings(
            embedding_provider="azure_openai",
            azure_openai_endpoint=None,
            azure_openai_api_key="test-key",  # pragma: allowlist secret
        )
        with pytest.raises(ProviderError, match="AZURE_OPENAI_ENDPOINT"):
            create_embedding_provider(config)

    def test_create_embedding_azure_requires_api_key(self):
        """Factory should raise if Azure API key is missing."""
        from config import Settings
        from providers.factory import ProviderError, create_embedding_provider

        config = Settings(
            embedding_provider="azure_openai",
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_api_key=None,
        )
        with pytest.raises(ProviderError, match="AZURE_OPENAI_API_KEY"):
            create_embedding_provider(config)

    def test_create_embedding_openrouter_raises(self):
        """Factory should raise for OpenRouter embeddings (not supported)."""
        from config import Settings
        from providers.factory import ProviderError, create_embedding_provider

        config = Settings(embedding_provider="openrouter")
        with pytest.raises(ProviderError, match="doesn't support embeddings"):
            create_embedding_provider(config)

    def test_create_embedding_openai_raises(self):
        """Factory should raise for OpenAI embeddings (not yet implemented)."""
        from config import Settings
        from providers.factory import ProviderError, create_embedding_provider

        config = Settings(embedding_provider="openai")
        with pytest.raises(ProviderError, match="not yet implemented"):
            create_embedding_provider(config)

    def test_create_embedding_unknown_raises(self):
        """Factory should raise for unknown embedding provider."""
        from providers.factory import ProviderError, create_embedding_provider

        # Settings validates embedding_provider via Literal type, so we mock it
        config = MagicMock()
        config.embedding_provider = "unknown"
        with pytest.raises(ProviderError, match="Unknown embedding provider"):
            create_embedding_provider(config)

    def test_create_openrouter_with_fallback_models(self):
        """Factory should parse comma-separated fallback models for OpenRouter."""
        from config import Settings
        from providers.factory import create_llm_provider

        config = Settings(
            llm_provider="openrouter",
            openrouter_api_key="test-key",  # pragma: allowlist secret
            openrouter_model="primary-model",
            openrouter_fallback_models="fallback1, fallback2",
            openrouter_allow_fallbacks=True,
        )
        provider = create_llm_provider(config)
        assert provider.fallback_models == ["fallback1", "fallback2"]


# =============================================================================
# OpenRouter Provider Additional Tests
# =============================================================================


class TestOpenRouterProviderAdditional:
    """Additional tests for OpenRouter provider coverage."""

    def _make_provider(self, **kwargs):
        from providers.openrouter import OpenRouterProvider

        defaults = {
            "api_key": "sk-or-v1-test-key",  # pragma: allowlist secret
            "model": "test-model",
        }
        defaults.update(kwargs)
        return OpenRouterProvider(**defaults)

    def test_convert_messages(self):
        """_convert_messages should convert to OpenAI format."""
        provider = self._make_provider()
        messages = [
            ChatMessage(role="system", content="System prompt"),
            ChatMessage(role="user", content="Hello"),
        ]
        converted = provider._convert_messages(messages)
        assert converted == [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
        ]

    def test_get_model_no_fallbacks(self):
        """Without fallbacks, should return direct model."""
        provider = self._make_provider()
        model, extra_body = provider._get_model_and_extra_body()
        assert model == "test-model"
        assert extra_body is None

    def test_get_model_with_fallbacks(self):
        """With fallbacks, should return auto-router config."""
        provider = self._make_provider(
            fallback_models=["fallback1"],
            allow_fallbacks=True,
        )
        model, extra_body = provider._get_model_and_extra_body()
        assert model == "openrouter/auto"
        assert extra_body is not None
        assert "plugins" in extra_body

    def test_get_model_fallbacks_disabled(self):
        """With fallbacks disabled, should return direct model."""
        provider = self._make_provider(
            fallback_models=["fallback1"],
            allow_fallbacks=False,
        )
        model, extra_body = provider._get_model_and_extra_body()
        assert model == "test-model"
        assert extra_body is None

    def test_is_rate_limit_error_429(self):
        """429 APIStatusError should be detected as rate limit."""
        from openai import APIStatusError

        provider = self._make_provider()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        error = APIStatusError(message="Rate limited", response=mock_resp, body={})
        assert provider._is_rate_limit_error(error) is True

    def test_is_rate_limit_error_other(self):
        """Non-429 errors should not be rate limit errors."""
        from openai import APIStatusError

        provider = self._make_provider()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.headers = {}
        error = APIStatusError(message="Server error", response=mock_resp, body={})
        assert provider._is_rate_limit_error(error) is False

    def test_is_model_unavailable_error_message(self):
        """Error message containing 'no model' should be detected."""
        from openai import APIStatusError

        provider = self._make_provider()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {}
        error = APIStatusError(
            message="No model found matching request",
            response=mock_resp,
            body={},
        )
        assert provider._is_model_unavailable_error(error) is True

    @pytest.mark.asyncio
    async def test_chat_success_with_usage(self):
        """Chat should handle usage info correctly."""
        provider = self._make_provider()

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello!"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "test-model"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.chat([ChatMessage(role="user", content="Hi")])

        assert result.content == "Hello!"
        assert result.tokens_used == 30

    @pytest.mark.asyncio
    async def test_chat_no_usage(self):
        """Chat should handle None usage gracefully."""
        provider = self._make_provider()

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello!"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "test-model"
        mock_response.usage = None

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.chat([ChatMessage(role="user", content="Hi")])

        assert result.tokens_used == 0

    @pytest.mark.asyncio
    async def test_chat_model_from_response(self):
        """Chat should use model name from response if available."""
        provider = self._make_provider()

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello!"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "actual-model-used"
        mock_response.usage = None

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.chat([ChatMessage(role="user", content="Hi")])

        assert result.model == "actual-model-used"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """health_check should return True on success."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """health_check should return False on exception."""
        provider = self._make_provider()

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            result = await provider.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_model_available_success(self):
        """verify_model_available should return True for available model."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            available, error = await provider.verify_model_available("test-model")

        assert available is True
        assert error == ""

    @pytest.mark.asyncio
    async def test_verify_model_available_empty_response(self):
        """verify_model_available should return False for empty response."""
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.choices = []

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            available, error = await provider.verify_model_available("test-model")

        assert available is False
        assert "Empty response" in error

    @pytest.mark.asyncio
    async def test_verify_model_available_404(self):
        """verify_model_available should return False for 404."""
        from openai import APIStatusError

        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {}
        error = APIStatusError(message="Not found", response=mock_resp, body={})

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            available, msg = await provider.verify_model_available("bad-model")

        assert available is False
        assert "not found" in msg

    @pytest.mark.asyncio
    async def test_verify_model_available_429(self):
        """verify_model_available should return True for 429 (model exists but busy)."""
        from openai import APIStatusError

        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        error = APIStatusError(message="Rate limited", response=mock_resp, body={})

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            available, msg = await provider.verify_model_available("busy-model")

        assert available is True
        assert "rate limited" in msg.lower()

    @pytest.mark.asyncio
    async def test_verify_model_available_other_api_error(self):
        """verify_model_available should return False for other API errors."""
        from openai import APIStatusError

        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.headers = {}
        error = APIStatusError(message="Server error", response=mock_resp, body={})

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            available, msg = await provider.verify_model_available("test-model")

        assert available is False
        assert "API error 500" in msg

    @pytest.mark.asyncio
    async def test_verify_model_available_generic_exception(self):
        """verify_model_available should handle generic exceptions."""
        provider = self._make_provider()

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            available, msg = await provider.verify_model_available("test-model")

        assert available is False
        assert "Network error" in msg

    @pytest.mark.asyncio
    async def test_verify_all_models(self):
        """verify_all_models should check all configured models."""
        provider = self._make_provider(fallback_models=["fallback1", "fallback2"])

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            results = await provider.verify_all_models()

        assert len(results) == 3  # primary + 2 fallbacks
        assert "test-model" in results
        assert "fallback1" in results
        assert "fallback2" in results

    @pytest.mark.asyncio
    async def test_chat_fallback_no_fallbacks_configured(self):
        """Chat should not fallback when rate limited but no fallbacks configured."""
        from openai import APIStatusError

        provider = self._make_provider(
            fallback_models=[],
            allow_fallbacks=True,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        error = APIStatusError(message="Rate limited", response=mock_resp, body={})

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            with pytest.raises(APIStatusError):
                await provider.chat([ChatMessage(role="user", content="Hi")])

    @pytest.mark.asyncio
    async def test_chat_all_fallbacks_exhausted(self):
        """Chat should raise RuntimeError when all fallbacks fail."""
        from openai import APIStatusError

        provider = self._make_provider(
            fallback_models=["fb1"],
            allow_fallbacks=True,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        error = APIStatusError(message="Rate limited", response=mock_resp, body={})

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            with pytest.raises(RuntimeError, match="All models unavailable"):
                await provider.chat([ChatMessage(role="user", content="Hi")])

    @pytest.mark.asyncio
    async def test_chat_non_recoverable_error(self):
        """Chat should re-raise non-recoverable API errors."""
        from openai import APIStatusError

        provider = self._make_provider(
            fallback_models=["fb1"],
            allow_fallbacks=True,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {}
        error = APIStatusError(message="Bad request", response=mock_resp, body={})

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            with pytest.raises(APIStatusError):
                await provider.chat([ChatMessage(role="user", content="Hi")])


# =============================================================================
# Base Model Tests
# =============================================================================


class TestBaseModels:
    """Tests for base provider models."""

    def test_chat_message_creation(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_llm_response_creation(self):
        response = LLMResponse(
            content="Hello",
            model="test",
            provider="test",
            tokens_used=10,
            finish_reason="stop",
        )
        assert response.content == "Hello"
        assert response.tokens_used == 10

    def test_llm_response_optional_fields(self):
        response = LLMResponse(content="Hello", model="test", provider="test")
        assert response.tokens_used is None
        assert response.finish_reason is None

    def test_embedding_response_creation(self):
        response = EmbeddingResponse(
            embedding=[0.1, 0.2, 0.3],
            model="test",
            provider="test",
        )
        assert response.embedding == [0.1, 0.2, 0.3]

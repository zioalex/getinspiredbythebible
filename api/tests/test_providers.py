"""
Tests for LLM provider factory
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from config import Settings
from providers.base import LLMProvider
from providers.factory import ProviderError, create_llm_provider
from providers.openrouter import OpenRouterProvider


def test_provider_factory_returns_provider():
    """Test that factory returns a provider instance"""
    # Create a minimal settings object for Ollama
    settings = Settings(
        llm_provider="ollama", llm_model="llama3:8b", ollama_host="http://localhost:11434"
    )

    provider = create_llm_provider(settings)
    assert provider is not None
    assert isinstance(provider, LLMProvider)


def test_provider_has_required_methods():
    """Test that provider has required interface methods"""
    settings = Settings(
        llm_provider="ollama", llm_model="llama3:8b", ollama_host="http://localhost:11434"
    )

    provider = create_llm_provider(settings)
    assert hasattr(provider, "chat")
    assert hasattr(provider, "chat_stream")
    assert callable(provider.chat)
    assert callable(provider.chat_stream)


def test_openrouter_provider_creation():
    """Test that OpenRouter provider can be created from factory"""
    settings = Settings(
        llm_provider="openrouter",
        llm_model="meta-llama/llama-3.3-70b-instruct:free",
        openrouter_api_key="sk-or-v1-test-key",  # pragma: allowlist secret
    )

    provider = create_llm_provider(settings)
    assert provider is not None
    assert isinstance(provider, OpenRouterProvider)
    assert isinstance(provider, LLMProvider)


def test_openrouter_provider_has_correct_config():
    """Test that OpenRouter provider has correct configuration"""
    settings = Settings(
        llm_provider="openrouter",
        openrouter_model="google/gemma-2-9b-it:free",
        openrouter_api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        openrouter_base_url="https://openrouter.ai/api/v1",
    )

    provider = create_llm_provider(settings)
    assert provider.model == "google/gemma-2-9b-it:free"
    assert provider.provider_name == "openrouter"


def test_openrouter_provider_requires_api_key():
    """Test that OpenRouter provider requires API key"""
    settings = Settings(
        llm_provider="openrouter",
        llm_model="meta-llama/llama-3.3-70b-instruct:free",
        openrouter_api_key=None,
    )

    with pytest.raises(ProviderError, match="requires OPENROUTER_API_KEY"):
        create_llm_provider(settings)


def test_openrouter_provider_has_required_methods():
    """Test that OpenRouter provider has required interface methods"""
    settings = Settings(
        llm_provider="openrouter",
        llm_model="meta-llama/llama-3.3-70b-instruct:free",
        openrouter_api_key="sk-or-v1-test-key",  # pragma: allowlist secret
    )

    provider = create_llm_provider(settings)
    assert hasattr(provider, "chat")
    assert hasattr(provider, "chat_stream")
    assert hasattr(provider, "health_check")
    assert callable(provider.chat)
    assert callable(provider.chat_stream)
    assert callable(provider.health_check)


# Tests for OpenRouter empty response handling (API overload scenarios)


@pytest.mark.asyncio
async def test_openrouter_handles_none_choices():
    """Test that OpenRouter raises ValueError when API returns None choices.

    This can happen when OpenRouter's free API is overloaded.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from providers.base import ChatMessage

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="test-model",
    )

    # Mock response with None choices (happens when API is overloaded)
    mock_response = MagicMock()
    mock_response.choices = None

    with patch.object(
        provider._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with pytest.raises(ValueError, match="OpenRouter returned empty response"):
            await provider.chat([ChatMessage(role="user", content="test")])


@pytest.mark.asyncio
async def test_openrouter_handles_empty_choices():
    """Test that OpenRouter raises ValueError when API returns empty choices array."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from providers.base import ChatMessage

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="test-model",
    )

    # Mock response with empty choices array
    mock_response = MagicMock()
    mock_response.choices = []

    with patch.object(
        provider._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with pytest.raises(ValueError, match="OpenRouter returned empty response"):
            await provider.chat([ChatMessage(role="user", content="test")])


@pytest.mark.asyncio
async def test_openrouter_streaming_handles_empty_chunks():
    """Test that streaming skips chunks with empty/None choices."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from providers.base import ChatMessage

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="test-model",
    )

    # Create chunks - some with empty choices, some with content
    chunk_empty = MagicMock()
    chunk_empty.choices = []

    chunk_none = MagicMock()
    chunk_none.choices = None

    chunk_valid = MagicMock()
    chunk_valid.choices = [MagicMock()]
    chunk_valid.choices[0].delta.content = "Hello!"

    async def mock_stream():
        yield chunk_empty  # Should be skipped
        yield chunk_none  # Should be skipped
        yield chunk_valid  # Should yield "Hello!"

    mock_create = AsyncMock(return_value=mock_stream())

    with patch.object(provider._client.chat.completions, "create", mock_create):
        chunks = []
        async for chunk in provider.chat_stream([ChatMessage(role="user", content="test")]):
            chunks.append(chunk)

        assert chunks == ["Hello!"]

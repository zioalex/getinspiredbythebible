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


# Tests for OpenRouter model unavailability and fallback


@pytest.mark.asyncio
async def test_openrouter_fallback_on_404_model_not_found():
    """Test that OpenRouter falls back to other models when primary returns 404."""
    from unittest.mock import MagicMock, patch

    from openai import APIStatusError

    from providers.base import ChatMessage

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="non-existent-model:free",
        fallback_models=["fallback-model"],
        allow_fallbacks=True,
    )

    # Mock 404 error for primary model
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.headers = {}
    error_404 = APIStatusError(
        message="No models match your request",
        response=mock_response_404,
        body={"error": {"message": "No models match", "code": 404}},
    )

    # Mock successful response for fallback
    mock_success = MagicMock()
    mock_success.choices = [MagicMock()]
    mock_success.choices[0].message.content = "Fallback response"
    mock_success.choices[0].finish_reason = "stop"
    mock_success.model = "fallback-model"
    mock_success.usage = MagicMock()
    mock_success.usage.prompt_tokens = 10
    mock_success.usage.completion_tokens = 5

    call_count = 0

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # First call (primary or auto-router)
            raise error_404
        return mock_success  # Fallback succeeds

    with patch.object(provider._client.chat.completions, "create", side_effect=mock_create):
        response = await provider.chat([ChatMessage(role="user", content="test")])
        assert response.content == "Fallback response"
        assert response.model == "fallback-model"


@pytest.mark.asyncio
async def test_openrouter_no_fallback_when_disabled():
    """Test that OpenRouter doesn't fallback when allow_fallbacks=False."""
    from unittest.mock import MagicMock, patch

    from openai import APIStatusError

    from providers.base import ChatMessage

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="non-existent-model:free",
        fallback_models=["fallback-model"],
        allow_fallbacks=False,  # Disabled!
    )

    # Mock 404 error
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.headers = {}
    error_404 = APIStatusError(
        message="No models match your request",
        response=mock_response_404,
        body={"error": {"message": "No models match", "code": 404}},
    )

    async def mock_create(*args, **kwargs):
        raise error_404

    with patch.object(provider._client.chat.completions, "create", side_effect=mock_create):
        with pytest.raises(APIStatusError):
            await provider.chat([ChatMessage(role="user", content="test")])


def test_openrouter_is_model_unavailable_error():
    """Test the _is_model_unavailable_error helper method."""
    from unittest.mock import MagicMock

    from openai import APIStatusError

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="test-model",
    )

    # 404 should be detected as model unavailable
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.headers = {}
    error_404 = APIStatusError(
        message="Model not found",
        response=mock_response_404,
        body={},
    )
    assert provider._is_model_unavailable_error(error_404) is True

    # 503 should be detected as model unavailable
    mock_response_503 = MagicMock()
    mock_response_503.status_code = 503
    mock_response_503.headers = {}
    error_503 = APIStatusError(
        message="Service unavailable",
        response=mock_response_503,
        body={},
    )
    assert provider._is_model_unavailable_error(error_503) is True

    # 400 should NOT be detected as model unavailable
    mock_response_400 = MagicMock()
    mock_response_400.status_code = 400
    mock_response_400.headers = {}
    error_400 = APIStatusError(
        message="Bad request",
        response=mock_response_400,
        body={},
    )
    assert provider._is_model_unavailable_error(error_400) is False


def test_openrouter_should_try_fallback():
    """Test the _should_try_fallback helper combines rate limit and model unavailable."""
    from unittest.mock import MagicMock

    from openai import APIStatusError, RateLimitError

    provider = OpenRouterProvider(
        api_key="sk-or-v1-test-key",  # pragma: allowlist secret
        model="test-model",
    )

    # Rate limit error should trigger fallback
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {}
    error_429 = APIStatusError(
        message="Rate limited",
        response=mock_response_429,
        body={},
    )
    assert provider._should_try_fallback(error_429) is True

    # 404 should trigger fallback
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.headers = {}
    error_404 = APIStatusError(
        message="Not found",
        response=mock_response_404,
        body={},
    )
    assert provider._should_try_fallback(error_404) is True

    # RateLimitError should trigger fallback
    mock_response_rate = MagicMock()
    mock_response_rate.status_code = 429
    mock_response_rate.headers = {}
    rate_error = RateLimitError(
        message="Rate limited",
        response=mock_response_rate,
        body={},
    )
    assert provider._should_try_fallback(rate_error) is True

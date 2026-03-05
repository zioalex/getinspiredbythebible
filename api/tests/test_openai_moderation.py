"""
Tests for OpenAI Moderation API provider.

All tests use mocked httpx responses - no real API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from providers.openai_moderation import OpenAIModerationProvider


def make_openai_response(scores: dict) -> dict:
    """
    Build a fake OpenAI moderation API response.

    Args:
        scores: Category scores (13 categories, 0.0-1.0)

    Returns:
        Dict matching OpenAI moderation API response format
    """
    # Default scores (all 13 categories)
    default_scores = {
        "harassment": 0.0,
        "harassment/threatening": 0.0,
        "hate": 0.0,
        "hate/threatening": 0.0,
        "self-harm": 0.0,
        "self-harm/intent": 0.0,
        "self-harm/instructions": 0.0,
        "sexual": 0.0,
        "sexual/minors": 0.0,
        "violence": 0.0,
        "violence/graphic": 0.0,
        "illicit": 0.0,
        "illicit/violent": 0.0,
    }
    default_scores.update(scores)

    categories = {k: v > 0.5 for k, v in default_scores.items()}

    return {
        "id": "modr-test123",
        "model": "omni-moderation-latest",
        "results": [
            {
                "flagged": any(categories.values()),
                "categories": categories,
                "category_scores": default_scores,
            }
        ],
    }


@pytest.mark.asyncio
async def test_allows_david_killed_goliath():
    """Biblical violence should be allowed (low violence score)."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.02,
            "harassment/threatening": 0.01,
            "hate": 0.0,
            "self-harm/intent": 0.0,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("How did David kill Goliath?", "en")

    assert result.allowed is True
    assert result.reason == "clean"
    assert result.is_help_seeking is False


@pytest.mark.asyncio
async def test_allows_attack_by_pharisees():
    """Biblical discussion of attacks should be allowed."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.03,
            "harassment/threatening": 0.02,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("The Pharisees attacked Jesus verbally", "en")

    assert result.allowed is True


@pytest.mark.asyncio
async def test_allows_slaughter_of_innocents():
    """Biblical narrative about violence should be allowed."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.04,
            "violence/graphic": 0.02,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("Tell me about the slaughter of the innocents", "en")

    assert result.allowed is True


@pytest.mark.asyncio
async def test_allows_weapon_spear():
    """Biblical discussion of weapons should be allowed."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.01,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("What weapon did Saul use?", "en")

    assert result.allowed is True


@pytest.mark.asyncio
async def test_allows_war_old_testament():
    """Biblical war discussion should be allowed."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.05,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("Tell me about wars in the Old Testament", "en")

    assert result.allowed is True


@pytest.mark.asyncio
async def test_allows_help_seeking_self_harm():
    """Help-seeking self-harm expressions should be allowed with compassionate flag."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "self-harm/intent": 0.7,
            "violence": 0.0,
            "hate": 0.0,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I want to die, help me", "en")

    assert result.allowed is True
    assert result.reason == "possible_help_seeking"
    assert result.is_help_seeking is True
    assert result.compassionate_response_needed is True


@pytest.mark.asyncio
async def test_allows_drug_struggle():
    """Help-seeking drug struggle should be allowed."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "self-harm/intent": 0.3,
            "violence": 0.0,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I'm struggling with drug addiction", "en")

    assert result.allowed is True
    assert result.is_help_seeking is True


@pytest.mark.asyncio
async def test_blocks_bomb_threat():
    """Real bomb threat should be blocked."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.97,
            "harassment/threatening": 0.85,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I want to build a bomb and blow up the school", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_blocks_murder_threat():
    """Murder threat should be blocked."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.92,
            "harassment/threatening": 0.88,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I'm going to kill that person", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_blocks_self_harm_instructions():
    """Self-harm instructions should be blocked."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "self-harm/instructions": 0.85,
            "self-harm/intent": 0.2,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("Here's how to hurt yourself effectively", "en")

    assert result.allowed is False
    assert result.reason == "self_harm_instructions_detected"


@pytest.mark.asyncio
async def test_blocks_hate_speech():
    """Hate speech should be blocked."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "hate": 0.92,
            "hate/threatening": 0.15,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I hate all [slur removed]", "en")

    assert result.allowed is False
    assert result.reason == "hate_speech_detected"


@pytest.mark.asyncio
async def test_blocks_threatening_harassment():
    """Threatening harassment should be blocked."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "harassment/threatening": 0.91,
            "violence": 0.45,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I'm going to find you and make you suffer", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_fallback_on_api_unavailable():
    """When API is unavailable, exception should be raised for fallback handling."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            await provider.analyze_text("I want to build a bomb", "en")


@pytest.mark.asyncio
async def test_fallback_on_timeout():
    """When API times out, exception should be raised for fallback handling."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5, timeout=1)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(httpx.TimeoutException):
            await provider.analyze_text("test message", "en")


@pytest.mark.asyncio
async def test_uses_openrouter_key_when_no_openai_key():
    """Should accept any API key (OpenAI or OpenRouter)."""
    provider = OpenAIModerationProvider(api_key="sk-or-v1-test123", threshold=0.5)

    mock_response = make_openai_response({"violence": 0.01})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("test message", "en")

        # Verify Authorization header was set correctly
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer sk-or-v1-test123"

    assert result.allowed is True


@pytest.mark.asyncio
async def test_threshold_respected_below():
    """Score below threshold should allow."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.4,  # Below threshold
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("test message", "en")

    assert result.allowed is True


@pytest.mark.asyncio
async def test_threshold_respected_above():
    """Score above threshold should block."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.6,  # Above threshold
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("test message", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_api_call_format():
    """Verify API call uses correct endpoint, model, and format."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response({"violence": 0.01})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        await provider.analyze_text("test message", "en")

        # Verify call was made correctly
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args

        assert call_args[0] == "https://api.openai.com/v1/moderations"
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert call_kwargs["json"]["model"] == "omni-moderation-latest"
        assert call_kwargs["json"]["input"] == "test message"


@pytest.mark.asyncio
async def test_categories_scaled_to_integer():
    """Categories should be scaled from 0.0-1.0 to 0-10 for consistency."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)

    mock_response = make_openai_response(
        {
            "violence": 0.35,
            "hate": 0.12,
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("test message", "en")

    assert result.categories["violence"] == 3  # 0.35 * 10 = 3
    assert result.categories["hate"] == 1  # 0.12 * 10 = 1

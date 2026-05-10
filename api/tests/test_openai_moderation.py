"""
Tests for OpenAI Moderation API provider.

All tests use mocked httpx responses — no real API calls.
Covers false positives (biblical context), true positives, help-seeking,
fallback behavior, and API call format.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.openai_moderation import OpenAIModerationProvider


def make_moderation_response(scores: dict) -> dict:
    """Build a fake /v1/moderations API response."""
    return {
        "id": "modr-test123",
        "model": "omni-moderation-latest",
        "results": [
            {
                "flagged": any(v >= 0.5 for v in scores.values()),
                "categories": {k: (v >= 0.5) for k, v in scores.items()},
                "category_scores": scores,
            }
        ],
    }


def all_clean() -> dict:
    """All-zero scores representing safe content."""
    return {
        "harassment": 0.001,
        "harassment/threatening": 0.001,
        "hate": 0.001,
        "hate/threatening": 0.001,
        "self-harm": 0.001,
        "self-harm/intent": 0.001,
        "self-harm/instructions": 0.001,
        "sexual": 0.001,
        "sexual/minors": 0.001,
        "violence": 0.001,
        "violence/graphic": 0.001,
    }


def make_mock_response(scores: dict) -> MagicMock:
    """Create an httpx mock response object."""
    obj = MagicMock()
    obj.status_code = 200
    obj.json.return_value = make_moderation_response(scores)
    obj.raise_for_status = lambda: None
    return obj


# ===========================================================================
# False-positive tests — must ALLOW (biblical context)
# ===========================================================================


@pytest.mark.asyncio
async def test_allows_david_killed_goliath():
    """Biblical violence has a very low violence score → allowed."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "violence": 0.02}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("How did David kill Goliath?", "en")

    assert result.allowed is True
    assert result.reason == "clean"
    assert result.is_help_seeking is False


@pytest.mark.asyncio
async def test_allows_terrorist_plot_in_esther():
    """Historical terrorism reference in scripture → allowed."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "violence": 0.05, "harassment/threatening": 0.03}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("The terrorist plot in the book of Esther", "en")

    assert result.allowed is True
    assert result.reason == "clean"


@pytest.mark.asyncio
async def test_allows_wars_in_old_testament():
    """Discussion of biblical wars → allowed."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "violence": 0.04}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("Tell me about the wars in the Old Testament", "en")

    assert result.allowed is True
    assert result.reason == "clean"


@pytest.mark.asyncio
async def test_allows_slaughter_of_innocents_biblical():
    """Matthew 2 slaughter of innocents → allowed (biblical)."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "violence": 0.04}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("The slaughter of the innocents in Matthew 2", "en")

    assert result.allowed is True


@pytest.mark.asyncio
async def test_allows_clean_message():
    """Completely clean message → allowed."""
    provider = OpenAIModerationProvider(api_key="test-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(all_clean())
        result = await provider.analyze_text("I need guidance on my faith journey", "en")

    assert result.allowed is True
    assert result.reason == "clean"
    assert result.is_help_seeking is False


# ===========================================================================
# True-positive tests — must BLOCK
# ===========================================================================


@pytest.mark.asyncio
async def test_blocks_bomb_threat():
    """Literal bomb threat → blocked as violence_or_threat_detected."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "violence": 0.95, "harassment/threatening": 0.88}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("I want to build a bomb and blow up the school", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_blocks_murder_threat_via_harassment():
    """Murder threat detected via harassment/threatening score → blocked."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "harassment/threatening": 0.92}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("I will murder my neighbor", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_blocks_hate_speech():
    """Hate speech → blocked as hate_speech_detected."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "hate": 0.88, "hate/threatening": 0.75}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("Kill all [ethnic group]", "en")

    assert result.allowed is False
    assert result.reason == "hate_speech_detected"


@pytest.mark.asyncio
async def test_blocks_self_harm_instructions():
    """Self-harm instructions → blocked."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "self-harm/instructions": 0.90}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text(
            "Here is a step-by-step guide to cutting yourself", "en"
        )

    assert result.allowed is False
    assert result.reason == "self_harm_instructions_detected"


@pytest.mark.asyncio
async def test_blocks_at_threshold_boundary():
    """Score exactly at threshold (0.5) is blocked (>= not >)."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)
    scores = {**all_clean(), "violence": 0.5}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("some violent message", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


# ===========================================================================
# Help-seeking tests — must ALLOW + compassionate flag
# ===========================================================================


@pytest.mark.asyncio
async def test_allows_self_harm_intent_help_seeking():
    """Self-harm intent without violence/hate → allowed with compassionate flag."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "self-harm/intent": 0.7, "violence": 0.02, "hate": 0.01}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("I feel like I want to die, please help", "en")

    assert result.allowed is True
    assert result.reason == "possible_help_seeking"
    assert result.is_help_seeking is True
    assert result.compassionate_response_needed is True


@pytest.mark.asyncio
async def test_help_seeking_threshold_flag_is_01_not_main_threshold():
    """Self-harm/intent flag triggers at 0.1, not the main threshold (0.5)."""
    provider = OpenAIModerationProvider(api_key="test-key", threshold=0.5)
    # intent is between 0.1 and 0.5 — below block threshold but above flag threshold
    scores = {**all_clean(), "self-harm/intent": 0.15, "violence": 0.01, "hate": 0.01}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("I am struggling with drugs, help me", "en")

    assert result.allowed is True
    assert result.is_help_seeking is True
    assert result.compassionate_response_needed is True


# ===========================================================================
# Provider behavior and error handling
# ===========================================================================


@pytest.mark.asyncio
async def test_fallback_on_timeout():
    """Timeout raises TimeoutException (orchestrator handles fallback)."""
    provider = OpenAIModerationProvider(api_key="test-key", timeout=1)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(httpx.TimeoutException):
            await provider.analyze_text("test message", "en")


@pytest.mark.asyncio
async def test_fallback_on_connection_error():
    """Connection error raises HTTPError (orchestrator handles fallback)."""
    provider = OpenAIModerationProvider(api_key="test-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("connection refused")

        with pytest.raises(httpx.ConnectError):
            await provider.analyze_text("test message", "en")


@pytest.mark.asyncio
async def test_api_call_format():
    """Verify endpoint, model, and Authorization header are sent correctly."""
    provider = OpenAIModerationProvider(api_key="sk-test-key", threshold=0.5, timeout=3)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(all_clean())
        await provider.analyze_text("test message", "en")

    call_kwargs = mock_post.call_args
    url = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
    assert "openai.com/v1/moderations" in url

    headers = call_kwargs[1].get("headers", {}) or (
        call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
    )
    assert "Authorization" in headers
    assert "sk-test-key" in headers["Authorization"]

    body = call_kwargs[1].get("json", {})
    assert body.get("model") == "omni-moderation-latest"
    assert "input" in body


@pytest.mark.asyncio
async def test_uses_provided_api_key():
    """Confirm provided API key reaches the Authorization header."""
    api_key = "sk-specific-test-key"
    provider = OpenAIModerationProvider(api_key=api_key)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(all_clean())
        await provider.analyze_text("test", "en")

    headers = mock_post.call_args[1].get("headers", {})
    assert f"Bearer {api_key}" == headers.get("Authorization")


@pytest.mark.asyncio
async def test_categories_stored_as_int_scaled():
    """Category scores are scaled to 0-100 ints in the result."""
    provider = OpenAIModerationProvider(api_key="test-key")
    scores = {**all_clean(), "violence": 0.95}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = make_mock_response(scores)
        result = await provider.analyze_text("test", "en")

    # violence=0.95 → 95 (int)
    assert result.categories.get("violence") == 95
    assert isinstance(result.categories.get("violence"), int)

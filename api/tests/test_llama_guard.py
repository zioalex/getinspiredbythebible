"""
Tests for Llama Guard 3 content safety provider via OpenRouter.

All tests use mocked httpx responses - no real API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from config import settings
from providers.llama_guard import LlamaGuardProvider


def make_llama_guard_response(response_text: str) -> dict:
    """
    Build a fake Llama Guard API response.

    Args:
        response_text: Response text (e.g. "safe" or "unsafe\\nS1,S9")

    Returns:
        Dict matching OpenRouter chat completions API response format
    """
    return {
        "id": "gen-test123",
        "model": "meta-llama/llama-guard-4-12b",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
    }


@pytest.mark.asyncio
async def test_allows_david_killed_goliath():
    """Biblical violence should be allowed (safe)."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("unsafe\nS11")

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
async def test_blocks_bomb_threat():
    """Real bomb threat should be blocked."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("unsafe\nS9")

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
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("unsafe\nS1")

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
async def test_blocks_hate_speech():
    """Hate speech should be blocked."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("unsafe\nS10")

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
async def test_blocks_multiple_categories():
    """Multiple violated categories should be blocked."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("unsafe\nS1,S9")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("I want to kill people with a bomb", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


@pytest.mark.asyncio
async def test_blocks_sexual_content():
    """Sexual content should be blocked."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("unsafe\nS12")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("explicit sexual content", "en")

    assert result.allowed is False
    assert result.reason == "sexual_content_detected"


@pytest.mark.asyncio
async def test_fallback_on_timeout():
    """When API times out, exception should be raised for fallback handling."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5, timeout=1)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(httpx.TimeoutException):
            await provider.analyze_text("test message", "en")


@pytest.mark.asyncio
async def test_fallback_on_api_unavailable():
    """When API is unavailable, exception should be raised for fallback handling."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            await provider.analyze_text("I want to build a bomb", "en")


@pytest.mark.asyncio
async def test_http_error_raised():
    """HTTP errors should be raised for fallback handling."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 401
        mock_response_obj.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response_obj
        )
        mock_post.return_value = mock_response_obj

        with pytest.raises(httpx.HTTPStatusError):
            await provider.analyze_text("test message", "en")


@pytest.mark.asyncio
async def test_empty_response_raises_not_safe():
    """An empty response body must raise, NOT be treated as 'safe' (BITB-061 O2)."""
    from providers.llama_guard import LlamaGuardResponseError

    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)
    mock_response = make_llama_guard_response("   ")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        with pytest.raises(LlamaGuardResponseError) as exc_info:
            await provider.analyze_text("test message", "en")

        assert exc_info.value.reason == "empty_response"
        # An empty/malformed response must count as a breaker failure so a
        # persistently misbehaving provider eventually trips to fail-closed.
        assert provider._breaker._consecutive_failures == 1


@pytest.mark.asyncio
async def test_malformed_response_shape_raises():
    """A response missing the expected choices/message/content shape must raise,
    not crash with an uncaught KeyError/IndexError."""
    from providers.llama_guard import LlamaGuardResponseError

    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = {"choices": []}  # missing [0]
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        with pytest.raises(LlamaGuardResponseError) as exc_info:
            await provider.analyze_text("test message", "en")

        assert exc_info.value.reason == "malformed_response"


@pytest.mark.asyncio
async def test_null_content_raises_not_crashes():
    """Upstream can return finish_reason=stop with content: null (observed live
    against OpenRouter/Together for meta-llama/llama-guard-4-12b) — the key is
    present so it doesn't raise on lookup, but must still be treated as a
    malformed response, not crash with an uncaught AttributeError on .strip()."""
    from providers.llama_guard import LlamaGuardResponseError

    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": None}}]
        }
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        with pytest.raises(LlamaGuardResponseError) as exc_info:
            await provider.analyze_text("test message", "en")

        assert exc_info.value.reason == "malformed_response"


@pytest.mark.asyncio
async def test_secondary_model_used_when_primary_fails():
    """If the primary model returns a malformed response, a secondary model
    (openai/gpt-oss-safeguard-20b) must be tried before giving up — and if it
    succeeds, its classification is used and the breaker does NOT record a
    failure (a primary hiccup recovered by the secondary is a success)."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    primary_response = MagicMock()
    primary_response.status_code = 200
    primary_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": None}}]
    }
    primary_response.raise_for_status = lambda: None

    secondary_response = MagicMock()
    secondary_response.status_code = 200
    secondary_response.json.return_value = make_llama_guard_response("unsafe\nS9")
    secondary_response.raise_for_status = lambda: None

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("providers.llama_guard.llama_guard_primary_result_counter") as mock_primary_counter,
        patch(
            "providers.llama_guard.llama_guard_secondary_model_counter"
        ) as mock_secondary_counter,
    ):
        mock_post.side_effect = [primary_response, secondary_response]

        result = await provider.analyze_text("I want to build a bomb", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"
    assert provider._breaker._consecutive_failures == 0

    assert mock_post.call_count == 2
    primary_call, secondary_call = mock_post.call_args_list
    assert primary_call.kwargs["json"]["model"] == "meta-llama/llama-guard-4-12b"
    assert secondary_call.kwargs["json"]["model"] == "openai/gpt-oss-safeguard-20b"
    assert secondary_call.kwargs["json"]["max_tokens"] == 800
    assert secondary_call.kwargs["json"]["reasoning"] == {"effort": "low"}

    # The two metrics together are the only way to see a degraded primary route
    # that the secondary is silently compensating for: primary_result_total is
    # the denominator, secondary_model_total{outcome=recovered} confirms the
    # secondary rescued it (see BITB-061 follow-up: "how often does the first
    # model fail?" wasn't answerable from metrics before this).
    mock_primary_counter.add.assert_called_once_with(1, {"outcome": "failed"})
    mock_secondary_counter.add.assert_called_once_with(1, {"outcome": "recovered"})


@pytest.mark.asyncio
async def test_primary_model_success_emits_metric():
    """The primary-result metric must fire on the fast/happy path too — it's
    the denominator for primary-model failure rate, not just a failure counter."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("providers.llama_guard.llama_guard_primary_result_counter") as mock_primary_counter,
        patch(
            "providers.llama_guard.llama_guard_secondary_model_counter"
        ) as mock_secondary_counter,
    ):
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text("How did David kill Goliath?", "en")

    assert result.allowed is True
    assert mock_post.call_count == 1
    mock_primary_counter.add.assert_called_once_with(1, {"outcome": "success"})
    mock_secondary_counter.add.assert_not_called()


@pytest.mark.asyncio
async def test_secondary_model_also_fails_falls_back():
    """If both the primary and secondary models fail, the breaker must record
    a single failure and the original error type must still propagate so the
    caller (content_safety.py) falls back to the keyword filter."""
    from providers.llama_guard import LlamaGuardResponseError

    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("providers.llama_guard.llama_guard_primary_result_counter") as mock_primary_counter,
        patch(
            "providers.llama_guard.llama_guard_secondary_model_counter"
        ) as mock_secondary_counter,
    ):
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = {"choices": []}
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        with pytest.raises(LlamaGuardResponseError):
            await provider.analyze_text("test message", "en")

    assert mock_post.call_count == 2
    assert provider._breaker._consecutive_failures == 1
    mock_primary_counter.add.assert_called_once_with(1, {"outcome": "failed"})
    mock_secondary_counter.add.assert_called_once_with(1, {"outcome": "also_failed"})


@pytest.mark.asyncio
async def test_uses_openrouter_key():
    """Should accept OpenRouter API key."""
    provider = LlamaGuardProvider(api_key="sk-or-v1-test123", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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
async def test_api_call_format():
    """Verify API call uses correct endpoint, model, headers, and format."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe")

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

        assert call_args[0] == "https://openrouter.ai/api/v1/chat/completions"
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert call_kwargs["headers"]["HTTP-Referer"] == settings.production_frontend_url
        assert call_kwargs["headers"]["X-Title"] == "VoxQuieta"
        assert call_kwargs["json"]["model"] == "meta-llama/llama-guard-4-12b"
        assert call_kwargs["json"]["temperature"] == 0
        assert call_kwargs["json"]["max_tokens"] == 20
        assert len(call_kwargs["json"]["messages"]) == 1
        assert call_kwargs["json"]["messages"][0]["role"] == "user"
        # Verify prompt format includes the user message
        assert "test message" in call_kwargs["json"]["messages"][0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected_safe",
    [
        ("How did David kill Goliath?", True),
        ("Tell me about Saul slaughtering his enemies", True),
        ("What weapon did David use against Goliath?", True),
        ("The pharisees attacked Jesus verbally", True),
        ("Tell me about wars in the Old Testament", True),
    ],
)
async def test_biblical_violence_parameterized(text, expected_safe):
    """Biblical violence contexts should be allowed (safe)."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response("safe" if expected_safe else "unsafe\nS1")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text(text, "en")

    assert result.allowed is expected_safe


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected_category",
    [
        ("I want to build a bomb", "S9"),
        ("I'm going to murder someone", "S1"),
        ("I hate all people of a certain race", "S10"),
    ],
)
async def test_harmful_content_parameterized(text, expected_category):
    """Harmful content should be blocked with appropriate category."""
    provider = LlamaGuardProvider(api_key="test-key", threshold=0.5)

    mock_response = make_llama_guard_response(f"unsafe\n{expected_category}")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = lambda: None
        mock_post.return_value = mock_response_obj

        result = await provider.analyze_text(text, "en")

    assert result.allowed is False
    if expected_category in ["S1", "S2", "S9"]:
        assert result.reason == "violence_or_threat_detected"
    elif expected_category == "S10":
        assert result.reason == "hate_speech_detected"

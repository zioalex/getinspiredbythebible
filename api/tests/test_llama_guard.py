"""
Tests for Llama Guard 3 content safety provider via OpenRouter.

All tests use mocked httpx responses - no real API calls.
"""

import time
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
    # Primary uses the client-level default timeout (explicit USE_CLIENT_DEFAULT
    # sentinel, not a per-call override); the secondary gets its own longer,
    # explicit per-call timeout override so a slow-but-working reasoning-model
    # call isn't cut off at the primary's tighter budget, while still capping
    # the worst case well below the old 10s.
    assert primary_call.kwargs["timeout"] is httpx.USE_CLIENT_DEFAULT
    assert secondary_call.kwargs["timeout"] == LlamaGuardProvider.SECONDARY_TIMEOUT_SECONDS

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


@pytest.mark.parametrize(
    "categories", ["S11,S6", "S6,S11", "S11,S10", "S11,S1", "S11,S6,S10"], ids=str
)
@pytest.mark.parametrize("lang", ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"])
def test_s11_combined_maps_to_self_harm_card_and_template(categories, lang):
    """BITB-258: S11 + other categories must yield a crisis card and self-harm reply."""
    from chat.prompts import get_blocked_response
    from utils.crisis_resources import CrisisKind, classify_crisis

    provider = LlamaGuardProvider(api_key="test-key")
    is_safe, cats = provider._parse_llama_guard_response(f"unsafe\n{categories}")
    result = provider._map_categories_to_result(is_safe, cats, "h")

    assert result.allowed is False
    assert "S11" in result.categories
    outcome = type(
        "O",
        (),
        {
            "allowed": result.allowed,
            "reason": result.reason,
            "compassionate": False,
            "is_help_seeking": result.is_help_seeking,
            "categories": result.categories,
        },
    )()
    assert classify_crisis(outcome) == CrisisKind.SELF_HARM
    assert get_blocked_response(result.reason, lang) == get_blocked_response(
        "self_harm_detected", lang
    )
    assert get_blocked_response(result.reason, lang) != get_blocked_response(
        "unsafe_content_detected", lang
    )


def test_non_s11_combinations_unchanged():
    provider = LlamaGuardProvider(api_key="test-key")
    assert provider._map_categories_to_result(False, ["S6", "S10"], "h").reason == (
        "hate_speech_detected"
    )
    assert provider._map_categories_to_result(False, ["S6"], "h").reason == (
        "unsafe_content_detected"
    )


# ---------------------------------------------------------------------------
# BITB-289: total budget, jittered retry, single-probe half-open
# ---------------------------------------------------------------------------


def _ok_response(text: str = "safe") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = make_llama_guard_response(text)
    resp.raise_for_status = lambda: None
    return resp


def _null_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"role": "assistant", "content": None}}]}
    resp.raise_for_status = lambda: None
    return resp


@pytest.mark.asyncio
async def test_total_budget_caps_secondary_timeout():
    """Remaining budget below the secondary timeout caps the secondary call."""
    provider = LlamaGuardProvider(api_key="k")
    provider.total_budget = 8.0
    provider.retry_jitter_max_ms = 0
    clock = {"t": 100.0}

    async def fake_post(*args, **kwargs):
        if kwargs["json"]["model"] == LlamaGuardProvider.MODEL:
            clock["t"] += 5.0  # primary burns 5s of the 8s budget
            return _null_response()
        return _ok_response("safe")

    with (
        patch("providers.llama_guard.time.monotonic", side_effect=lambda: clock["t"]),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_post.side_effect = fake_post
        result = await provider.analyze_text("hi", "en")

    assert result.allowed is True
    secondary_call = mock_post.call_args_list[1]
    assert secondary_call.kwargs["timeout"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_secondary_skipped_when_budget_exhausted():
    provider = LlamaGuardProvider(api_key="k")
    provider.total_budget = 8.0
    clock = {"t": 100.0}

    async def fake_post(*args, **kwargs):
        clock["t"] += 7.8  # leaves 0.2s < minimum useful window
        return _null_response()

    from providers.llama_guard import LlamaGuardResponseError

    with (
        patch("providers.llama_guard.time.monotonic", side_effect=lambda: clock["t"]),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch(
            "providers.llama_guard.llama_guard_secondary_model_counter"
        ) as mock_secondary_counter,
    ):
        mock_post.side_effect = fake_post
        with pytest.raises(LlamaGuardResponseError):
            await provider.analyze_text("hi", "en")

    assert mock_post.call_count == 1
    assert provider._breaker._consecutive_failures == 1
    mock_secondary_counter.add.assert_called_once_with(1, {"outcome": "skipped_budget"})


@pytest.mark.asyncio
async def test_retry_jitter_applied_and_bounded():
    provider = LlamaGuardProvider(api_key="k")
    provider.retry_jitter_max_ms = 250

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("providers.llama_guard.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("providers.llama_guard.random.uniform", return_value=0.2) as mock_uniform,
    ):
        mock_post.side_effect = [_null_response(), _ok_response("safe")]
        result = await provider.analyze_text("hi", "en")

    assert result.allowed is True
    mock_uniform.assert_called_once_with(0, 0.25)
    mock_sleep.assert_awaited_once_with(0.2)


@pytest.mark.asyncio
async def test_no_jitter_when_primary_succeeds():
    provider = LlamaGuardProvider(api_key="k")
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("providers.llama_guard.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_post.return_value = _ok_response("safe")
        await provider.analyze_text("hi", "en")
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_half_open_admits_single_probe_under_concurrency():
    """After cooldown during an ongoing outage only ONE concurrent call reaches HTTP."""
    import asyncio

    from utils.circuit_breaker import CircuitOpenError

    provider = LlamaGuardProvider(api_key="k")
    provider.retry_jitter_max_ms = 0
    breaker = provider._breaker
    gate = asyncio.Event()
    started = {"n": 0}

    async def slow_fail(*args, **kwargs):
        started["n"] += 1
        await gate.wait()
        raise httpx.ConnectError("down")

    # Do NOT patch time.monotonic here: it is also the asyncio loop clock, and freezing it
    # stops the wait_for() bounds below from ever firing (a regression would hang, not fail).
    # Backdate the breaker's open time instead so the cooldown has already elapsed.
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = slow_fail
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        assert breaker.state == "open"
        breaker._opened_at = time.monotonic() - breaker.current_cooldown_seconds - 1

        t1 = asyncio.create_task(provider.analyze_text("a", "en"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        t2 = asyncio.create_task(provider.analyze_text("b", "en"))
        try:
            with pytest.raises(CircuitOpenError):
                await asyncio.wait_for(t2, timeout=2)
            assert started["n"] == 1
            gate.set()
            with pytest.raises(httpx.ConnectError):
                await asyncio.wait_for(t1, timeout=2)
        finally:
            gate.set()
            t1.cancel()
            t2.cancel()

    assert breaker.state == "open"
    assert breaker.current_cooldown_seconds == breaker.cooldown_seconds * 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language", ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
)
async def test_secondary_verdict_returned_for_every_language(language):
    provider = LlamaGuardProvider(api_key="k")
    provider.retry_jitter_max_ms = 0
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [_null_response(), _ok_response("unsafe\nS10")]
        result = await provider.analyze_text("text", language)
    assert result.allowed is False
    assert result.reason == "hate_speech_detected"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_hung_post_is_capped_by_total_budget_and_records_breaker_failure():
    """httpx timeouts are per-phase; the overall budget must still hard-cap a hung call."""
    import asyncio
    import time as _time

    provider = LlamaGuardProvider(api_key="k", timeout=30)
    provider.total_budget = 0.3
    provider.retry_jitter_max_ms = 0

    async def hang(*args, **kwargs):
        await asyncio.Event().wait()

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch(
            "providers.llama_guard.llama_guard_secondary_model_counter"
        ) as mock_secondary_counter,
    ):
        mock_post.side_effect = hang
        start = _time.monotonic()
        with pytest.raises(httpx.TimeoutException):
            await asyncio.wait_for(provider.analyze_text("hi", "en"), timeout=5)
        elapsed = _time.monotonic() - start

    assert elapsed < 0.3 + 0.5
    assert provider._breaker._consecutive_failures == 1
    mock_secondary_counter.add.assert_called_once_with(1, {"outcome": "skipped_budget"})


@pytest.mark.asyncio
async def test_hung_secondary_hits_budget_both_failed_path():
    import asyncio

    provider = LlamaGuardProvider(api_key="k", timeout=30)
    provider.total_budget = 1.0
    provider.retry_jitter_max_ms = 0

    async def post(*args, **kwargs):
        if kwargs["json"]["model"] == LlamaGuardProvider.MODEL:
            return _null_response()
        await asyncio.Event().wait()

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch(
            "providers.llama_guard.llama_guard_secondary_model_counter"
        ) as mock_secondary_counter,
    ):
        mock_post.side_effect = post
        with pytest.raises(httpx.TimeoutException):
            await asyncio.wait_for(provider.analyze_text("hi", "en"), timeout=5)

    assert provider._breaker._consecutive_failures == 1
    mock_secondary_counter.add.assert_called_once_with(1, {"outcome": "also_failed"})


@pytest.mark.asyncio
async def test_budget_timeout_still_fails_over_to_openai_moderation(monkeypatch):
    """ml_only: a hung Llama Guard (budget timeout) must reach the OpenAI Moderation failover."""
    import asyncio

    from tests.test_content_safety import (
        _THREAT_SCORES,
        _failover_service,
        _fake_moderation_http,
    )

    service, _, spy = _failover_service(monkeypatch)
    provider = LlamaGuardProvider(api_key="k", timeout=30)
    provider.total_budget = 0.3
    provider.retry_jitter_max_ms = 0
    monkeypatch.setattr(service, "_get_llama_guard_provider", lambda: provider)
    # _fake_moderation_http swaps httpx.AsyncClient globally, so a single post mock serves both:
    # Llama Guard (OpenRouter URL) hangs, the OpenAI moderation call answers.
    calls = _fake_moderation_http(monkeypatch, {"I want to build a bomb": _THREAT_SCORES})
    moderation_post = httpx.AsyncClient.post

    async def route(self, url, *args, **kwargs):
        if "openrouter" in url:
            await asyncio.Event().wait()
        return await moderation_post(self, url, *args, **kwargs)

    with patch("httpx.AsyncClient.post", new=route):
        result = await asyncio.wait_for(service.check("I want to build a bomb", "en"), timeout=5)

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected (failover)"
    assert calls == ["I want to build a bomb"]
    spy.assert_not_awaited()


def test_breaker_probe_lease_covers_budget():
    provider = LlamaGuardProvider(api_key="k")
    assert provider._breaker.probe_timeout_seconds == provider.total_budget + 1.0


@pytest.mark.parametrize(
    "field,value",
    [
        ("llama_guard_total_budget_seconds", 0),
        ("llama_guard_secondary_timeout", -1),
        ("llama_guard_breaker_cooldown_seconds", 0),
        ("llama_guard_breaker_max_cooldown_seconds", 0),
        ("llama_guard_breaker_failure_threshold", 0),
        ("llama_guard_retry_jitter_max_ms", -1),
    ],
)
def test_llama_guard_settings_reject_invalid_values(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        type(settings)(**{**settings.model_dump(), field: value})


def test_llama_guard_settings_reject_max_cooldown_below_base():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        type(settings)(
            **{
                **settings.model_dump(),
                "llama_guard_breaker_cooldown_seconds": 30.0,
                "llama_guard_breaker_max_cooldown_seconds": 10.0,
            }
        )

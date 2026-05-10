"""
Tests for BITB-027: Surface content safety signals in LLM responses.

Covers:
- prompts.py: get_compassionate_addendum, get_blocked_response, _map_reason_to_category
- service.py: _check_content_safety returns _SafetyOutcome
- service.py: _build_messages injects compassionate addendum
- service.py: _build_blocked_response returns HTTP-200 synthetic ChatResponse
- service.py: _stream_blocked_response yields correct SSE chunks
- service.py: chat() blocked path and compassionate path
- service.py: chat_stream() blocked path and compassionate path
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.prompts import (
    COMPASSIONATE_RESPONSE_ADDENDUM,
    get_blocked_response,
    get_compassionate_addendum,
)
from chat.service import (
    ChatRequest,
    ChatService,
    _SafetyOutcome,
)
from utils.content_safety import ContentSafetyCheckResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service():
    """Create a ChatService with mock providers."""
    db = MagicMock()
    llm = MagicMock()
    embedding = MagicMock()
    embedding.embed = AsyncMock(return_value=MagicMock(embedding=[0.1] * 1536))
    return ChatService(db, llm, embedding)


def _safe_outcome(allowed=True, compassionate=False, reason="ok", categories=None):
    return _SafetyOutcome(
        allowed=allowed,
        compassionate=compassionate,
        reason=reason,
        categories=categories or {},
    )


def _make_request(message="Help me with grief", session_id=None, language=None):
    return ChatRequest(message=message, session_id=session_id, language=language)


# ---------------------------------------------------------------------------
# 1. get_compassionate_addendum — returns constant string
# ---------------------------------------------------------------------------


class TestGetCompassionateAddendum:
    def test_returns_addendum_string(self):
        result = get_compassionate_addendum()
        assert result is COMPASSIONATE_RESPONSE_ADDENDUM

    def test_contains_crisis_resources(self):
        result = get_compassionate_addendum()
        assert "988" in result  # US crisis line

    def test_contains_international_resource(self):
        result = get_compassionate_addendum()
        assert "findahelpline" in result

    def test_not_empty(self):
        assert len(get_compassionate_addendum()) > 50


# ---------------------------------------------------------------------------
# 2. get_blocked_response — localization and category mapping
# ---------------------------------------------------------------------------


class TestGetBlockedResponse:
    def test_english_self_harm(self):
        resp = get_blocked_response("self_harm", "en")
        assert resp  # non-empty
        assert isinstance(resp, str)

    def test_italian_self_harm(self):
        resp_en = get_blocked_response("self_harm", "en")
        resp_it = get_blocked_response("self_harm", "it")
        assert resp_it != resp_en  # different language, different text

    def test_unknown_language_falls_back_to_english(self):
        resp_en = get_blocked_response("self_harm", "en")
        resp_xx = get_blocked_response("self_harm", "xx")
        assert resp_xx == resp_en

    def test_unknown_reason_uses_generic(self):
        resp = get_blocked_response("totally_unknown_reason", "en")
        assert resp  # generic bucket always has "en"

    def test_violence_category(self):
        resp = get_blocked_response("violence_or_threat", "en")
        assert resp

    def test_hate_speech_category(self):
        resp = get_blocked_response("hate", "en")
        assert resp

    def test_sexual_content_category(self):
        resp = get_blocked_response("sexual", "en")
        assert resp


# ---------------------------------------------------------------------------
# 3. _build_messages — compassionate_mode injects addendum
# ---------------------------------------------------------------------------


class TestBuildMessagesCompassionateMode:
    def test_system_prompt_without_compassionate(self):
        service = _make_service()
        msgs = service._build_messages(
            user_message="I feel hopeless",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="general",
            compassionate_mode=False,
        )
        system_content = msgs[0].content
        assert "URGENT" not in system_content

    def test_system_prompt_with_compassionate(self):
        service = _make_service()
        msgs = service._build_messages(
            user_message="I feel hopeless",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="general",
            compassionate_mode=True,
        )
        system_content = msgs[0].content
        assert "URGENT" in system_content  # from COMPASSIONATE_RESPONSE_ADDENDUM
        assert "988" in system_content

    def test_compassionate_addendum_appended_not_prepended(self):
        service = _make_service()
        msgs = service._build_messages(
            user_message="test",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="general",
            compassionate_mode=True,
        )
        system_content = msgs[0].content
        # The addendum should appear after the main system prompt
        assert system_content.index("compassionate spiritual companion") < system_content.index(
            "URGENT"
        )


# ---------------------------------------------------------------------------
# 4. _check_content_safety — returns _SafetyOutcome (never raises)
# ---------------------------------------------------------------------------


class TestCheckContentSafety:
    @pytest.mark.asyncio
    async def test_returns_allowed_when_safety_disabled(self):
        service = _make_service()
        with patch("chat.service.settings") as mock_settings:
            mock_settings.content_safety_enabled = False
            outcome = await service._check_content_safety("any message", "en", None)
        assert outcome.allowed is True
        assert outcome.compassionate is False
        assert outcome.reason == "disabled"

    @pytest.mark.asyncio
    async def test_returns_blocked_outcome_when_content_blocked(self):
        service = _make_service()
        mock_result = ContentSafetyCheckResult(
            allowed=False,
            is_help_seeking=False,
            compassionate_response_needed=False,
            reason="self_harm",
            categories={"self_harm": 1},
        )
        with (
            patch("chat.service.settings") as mock_settings,
            patch("chat.service.get_content_safety_service") as mock_get_svc,
        ):
            mock_settings.content_safety_enabled = True
            mock_svc = AsyncMock()
            mock_svc.check = AsyncMock(return_value=mock_result)
            mock_get_svc.return_value = mock_svc

            outcome = await service._check_content_safety("harm message", "en", None)

        assert outcome.allowed is False
        assert outcome.compassionate is False
        assert outcome.reason == "self_harm"

    @pytest.mark.asyncio
    async def test_returns_compassionate_when_help_seeking(self):
        service = _make_service()
        mock_result = ContentSafetyCheckResult(
            allowed=True,
            is_help_seeking=True,
            compassionate_response_needed=True,
            reason="help_seeking",
            categories={},
        )
        with (
            patch("chat.service.settings") as mock_settings,
            patch("chat.service.get_content_safety_service") as mock_get_svc,
        ):
            mock_settings.content_safety_enabled = True
            mock_svc = AsyncMock()
            mock_svc.check = AsyncMock(return_value=mock_result)
            mock_get_svc.return_value = mock_svc

            outcome = await service._check_content_safety("I want to end it all", "en", None)

        assert outcome.allowed is True
        assert outcome.compassionate is True


# ---------------------------------------------------------------------------
# 5. _build_blocked_response — returns ChatResponse with provider=content_safety
# ---------------------------------------------------------------------------


class TestBuildBlockedResponse:
    def test_returns_chat_response(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        resp = service._build_blocked_response(outcome, "en", "KJV", None)
        from chat.service import ChatResponse

        assert isinstance(resp, ChatResponse)

    def test_provider_is_content_safety(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        resp = service._build_blocked_response(outcome, "en", "KJV", None)
        assert resp.provider == "content_safety"
        assert resp.model == "content_safety"

    def test_message_is_non_empty(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        resp = service._build_blocked_response(outcome, "en", "KJV", None)
        assert resp.message

    def test_localized_message_for_italian(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        resp_en = service._build_blocked_response(outcome, "en", "KJV", None)
        resp_it = service._build_blocked_response(outcome, "it", "CEI", None)
        assert resp_it.message != resp_en.message


# ---------------------------------------------------------------------------
# 6. _stream_blocked_response — yields metadata, content chunks, completion
# ---------------------------------------------------------------------------


class TestStreamBlockedResponse:
    @pytest.mark.asyncio
    async def test_yields_correct_chunk_types(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        chunks = []
        async for chunk in service._stream_blocked_response(outcome, "msg-1", "en", "KJV", None):
            chunks.append(chunk)

        types = [c["type"] for c in chunks]
        assert types[0] == "metadata"
        assert "content" in types
        assert types[-1] == "completion"

    @pytest.mark.asyncio
    async def test_metadata_provider_is_content_safety(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        chunks = []
        async for chunk in service._stream_blocked_response(outcome, "msg-1", "en", "KJV", None):
            chunks.append(chunk)

        metadata = chunks[0]
        assert metadata["provider"] == "content_safety"

    @pytest.mark.asyncio
    async def test_content_chunks_reconstruct_full_text(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        chunks = []
        async for chunk in service._stream_blocked_response(outcome, "msg-1", "en", "KJV", None):
            chunks.append(chunk)

        content_pieces = [c["content"] for c in chunks if c["type"] == "content"]
        full_text = "".join(content_pieces)
        expected = get_blocked_response("self_harm", "en")
        assert full_text.strip() == expected.strip()

    @pytest.mark.asyncio
    async def test_completion_has_empty_verses_cited(self):
        service = _make_service()
        outcome = _safe_outcome(allowed=False, reason="self_harm")
        chunks = []
        async for chunk in service._stream_blocked_response(outcome, "msg-1", "en", "KJV", None):
            chunks.append(chunk)

        completion = chunks[-1]
        assert completion["verses_cited"] == []


# ---------------------------------------------------------------------------
# 7. chat() — blocked path returns synthetic response (HTTP 200)
# ---------------------------------------------------------------------------


class TestChatBlockedPath:
    @pytest.mark.asyncio
    async def test_blocked_content_returns_synthetic_response(self):
        service = _make_service()
        request = _make_request("harm text")
        blocked_outcome = _safe_outcome(allowed=False, reason="self_harm")

        with (
            patch.object(service, "_check_content_safety", AsyncMock(return_value=blocked_outcome)),
            patch("chat.service.detect_language", return_value="en"),
            patch("chat.service.resolve_translation", return_value="KJV"),
            patch("chat.service.get_translation_info", return_value=None),
            patch("chat.service.get_model_override_for_language", return_value=None),
        ):
            resp = await service.chat(request)

        assert resp.provider == "content_safety"
        assert resp.message  # non-empty synthetic message

    @pytest.mark.asyncio
    async def test_blocked_content_does_not_call_llm(self):
        service = _make_service()
        request = _make_request("harm text")
        blocked_outcome = _safe_outcome(allowed=False, reason="self_harm")
        service.llm.chat = AsyncMock()

        with (
            patch.object(service, "_check_content_safety", AsyncMock(return_value=blocked_outcome)),
            patch("chat.service.detect_language", return_value="en"),
            patch("chat.service.resolve_translation", return_value="KJV"),
            patch("chat.service.get_translation_info", return_value=None),
            patch("chat.service.get_model_override_for_language", return_value=None),
        ):
            await service.chat(request)

        service.llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# 8. chat_stream() — blocked path yields synthetic SSE chunks
# ---------------------------------------------------------------------------


class TestChatStreamBlockedPath:
    @pytest.mark.asyncio
    async def test_blocked_content_yields_metadata_and_completion(self):
        service = _make_service()
        request = _make_request("harm text")
        blocked_outcome = _safe_outcome(allowed=False, reason="violence_or_threat")

        with (
            patch.object(service, "_check_content_safety", AsyncMock(return_value=blocked_outcome)),
            patch("chat.service.detect_language", return_value="en"),
            patch("chat.service.resolve_translation", return_value="KJV"),
            patch("chat.service.get_translation_info", return_value=None),
            patch("chat.service.get_model_override_for_language", return_value=None),
        ):
            chunks = []
            async for chunk in service.chat_stream(request):
                chunks.append(chunk)

        types = [c["type"] for c in chunks]
        assert "metadata" in types
        assert "completion" in types

    @pytest.mark.asyncio
    async def test_blocked_content_does_not_call_llm_stream(self):
        service = _make_service()
        request = _make_request("harm text")
        blocked_outcome = _safe_outcome(allowed=False, reason="self_harm")

        async def _empty_stream(*args, **kwargs):
            return
            yield  # make it an async generator

        service.llm.chat_stream = _empty_stream
        call_count = {"n": 0}
        original_empty = _empty_stream

        async def counting_stream(*args, **kwargs):
            call_count["n"] += 1
            async for x in original_empty(*args, **kwargs):
                yield x

        service.llm.chat_stream = counting_stream

        with (
            patch.object(service, "_check_content_safety", AsyncMock(return_value=blocked_outcome)),
            patch("chat.service.detect_language", return_value="en"),
            patch("chat.service.resolve_translation", return_value="KJV"),
            patch("chat.service.get_translation_info", return_value=None),
            patch("chat.service.get_model_override_for_language", return_value=None),
        ):
            async for _ in service.chat_stream(request):
                pass

        assert call_count["n"] == 0

"""
Tests for BITB-151: intent-gated Italian pastoral register.

Covers:
- chat/prompts.py: get_pastoral_register_note (registry + primary-subtag resolution)
- chat/service.py: _wants_cultural_tone gate
- chat/service.py: _build_messages injects the note, byte-identical otherwise
- chat/service.py: chat() and chat_stream() apply the gate identically
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.prompts import COMPASSIONATE_RESPONSE_ADDENDUM, get_pastoral_register_note
from chat.service import ChatRequest, ChatService
from providers.base import LLMResponse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(
            content="response text", model="test-model", provider="test-provider"
        )
    )
    llm.chat_stream = MagicMock()
    return llm


@pytest.fixture
def mock_embedding():
    emb = AsyncMock()
    emb.embed = AsyncMock()
    return emb


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def chat_service(mock_db, mock_llm, mock_embedding):
    return ChatService(mock_db, mock_llm, mock_embedding)


# ---------------------------------------------------------------------------
# 1. get_pastoral_register_note() -- registry + resolution
# ---------------------------------------------------------------------------


class TestGetPastoralRegisterNote:
    def test_it_has_a_note(self):
        assert get_pastoral_register_note("it") != ""

    @pytest.mark.parametrize("code", ["de", "en", "es", "fr", "xx"])
    def test_locale_with_no_entry_returns_empty(self, code):
        assert get_pastoral_register_note(code) == ""

    def test_region_qualified_code_resolves_to_primary_subtag(self):
        assert get_pastoral_register_note("it-CH") == get_pastoral_register_note("it")

    def test_note_never_mentions_verses_or_followups_trailers(self):
        note = get_pastoral_register_note("it")
        assert "VERSES" not in note
        assert "FOLLOWUPS" not in note


# ---------------------------------------------------------------------------
# 2. _wants_cultural_tone() gate
# ---------------------------------------------------------------------------


class TestWantsCulturalToneGate:
    @patch("chat.service.settings")
    def test_comfort_and_registered_locale_wants_tone(self, mock_settings, chat_service):
        mock_settings.chat_cultural_tone_enabled = True
        assert chat_service._wants_cultural_tone("COMFORT", "it") is True

    @patch("chat.service.settings")
    def test_guidance_and_registered_locale_wants_tone(self, mock_settings, chat_service):
        mock_settings.chat_cultural_tone_enabled = True
        assert chat_service._wants_cultural_tone("GUIDANCE", "it") is True

    @pytest.mark.parametrize(
        "intent", ["CURIOSITY", "VERSE_LOOKUP", "NEEDS_CLARIFICATION", "OFF_TOPIC", "GENERAL"]
    )
    @patch("chat.service.settings")
    def test_informational_intents_never_want_tone(self, mock_settings, chat_service, intent):
        mock_settings.chat_cultural_tone_enabled = True
        assert chat_service._wants_cultural_tone(intent, "it") is False

    @patch("chat.service.settings")
    def test_locale_with_no_registry_entry_never_wants_tone(self, mock_settings, chat_service):
        mock_settings.chat_cultural_tone_enabled = True
        assert chat_service._wants_cultural_tone("COMFORT", "de") is False

    @patch("chat.service.settings")
    def test_flag_disabled_never_wants_tone(self, mock_settings, chat_service):
        mock_settings.chat_cultural_tone_enabled = False
        assert chat_service._wants_cultural_tone("COMFORT", "it") is False


# ---------------------------------------------------------------------------
# 3. _build_messages() -- note injection + byte-identity guarantees
# ---------------------------------------------------------------------------


class TestBuildMessagesCulturalTone:
    def test_enabled_default_prompt_type_includes_note(self, chat_service):
        messages = chat_service._build_messages(
            user_message="hello",
            history=[],
            language_code="it",
            cultural_tone_enabled=True,
        )
        assert get_pastoral_register_note("it") in messages[0].content

    def test_default_call_omits_note(self, chat_service):
        messages = chat_service._build_messages(
            user_message="hello", history=[], language_code="it"
        )
        assert get_pastoral_register_note("it") not in messages[0].content

    @pytest.mark.parametrize(
        "prompt_type", ["verse_lookup", "prayer_lookup", "off_topic", "clarification"]
    )
    def test_non_default_prompt_types_never_include_note(self, chat_service, prompt_type):
        # Defense in depth: prompt_type is independent of detected intent, so a
        # caller could in principle pass cultural_tone_enabled=True alongside a
        # non-default prompt_type. The builder itself must still refuse.
        messages = chat_service._build_messages(
            user_message="hello",
            history=[],
            language_code="it",
            prompt_type=prompt_type,
            cultural_tone_enabled=True,
        )
        assert get_pastoral_register_note("it") not in messages[0].content

    def test_unregistered_locale_byte_identical_regardless_of_gate(self, chat_service):
        off = chat_service._build_messages(
            user_message="hello", history=[], language_code="de", cultural_tone_enabled=False
        )
        on = chat_service._build_messages(
            user_message="hello", history=[], language_code="de", cultural_tone_enabled=True
        )
        assert off[0].content == on[0].content

    def test_flag_off_byte_identical_for_registered_locale(self, chat_service):
        without_kwarg = chat_service._build_messages(
            user_message="hello", history=[], language_code="it"
        )
        explicitly_off = chat_service._build_messages(
            user_message="hello", history=[], language_code="it", cultural_tone_enabled=False
        )
        assert without_kwarg[0].content == explicitly_off[0].content

    def test_crisis_addendum_still_present_and_last(self, chat_service):
        messages = chat_service._build_messages(
            user_message="hello",
            history=[],
            language_code="it",
            cultural_tone_enabled=True,
            compassionate_mode=True,
        )
        content = messages[0].content
        note = get_pastoral_register_note("it")
        assert note in content
        assert COMPASSIONATE_RESPONSE_ADDENDUM in content
        assert content.rfind(COMPASSIONATE_RESPONSE_ADDENDUM) > content.rfind(note)


# ---------------------------------------------------------------------------
# 4. chat() and chat_stream() -- end-to-end gate application
# ---------------------------------------------------------------------------


def _settings_for_cultural_tone(mock_settings, *, cultural_tone_enabled: bool):
    mock_settings.content_filter_intent_detection = True
    mock_settings.llm_temperature = 0.7
    mock_settings.llm_max_tokens = 1024
    mock_settings.max_conversation_history = 10
    mock_settings.max_context_verses = 10
    mock_settings.chat_follow_ups_enabled = False
    mock_settings.chat_clarification_enabled = False
    mock_settings.chat_cultural_tone_enabled = cultural_tone_enabled
    mock_settings.verse_grounding_enabled = True
    mock_settings.grounding_unresolved_behavior = "strip"
    mock_settings.grounding_paraphrases_mode = "detect"


@pytest.mark.asyncio
class TestChatNonStreamingCulturalTone:
    @patch("chat.service.settings")
    async def test_comfort_it_turn_receives_note(self, mock_settings, chat_service, mock_llm):
        _settings_for_cultural_tone(mock_settings, cultural_tone_enabled=True)
        mock_llm.chat = AsyncMock(
            side_effect=[
                LLMResponse(content="COMFORT", model="m", provider="p"),  # intent detection
                LLMResponse(content="I hear you.", model="m", provider="p"),  # answer
            ]
        )

        request = ChatRequest(message="I'm really struggling", language="it", include_search=False)
        await chat_service.chat(request)

        answer_call = mock_llm.chat.call_args_list[1]
        assert get_pastoral_register_note("it") in answer_call.kwargs["messages"][0].content

    @patch("chat.service.settings")
    async def test_curiosity_it_turn_never_receives_note(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_cultural_tone(mock_settings, cultural_tone_enabled=True)
        mock_llm.chat = AsyncMock(
            side_effect=[
                LLMResponse(content="CURIOSITY", model="m", provider="p"),
                LLMResponse(content="Here is what the Bible says.", model="m", provider="p"),
            ]
        )

        request = ChatRequest(
            message="What does the Bible say about creation?", language="it", include_search=False
        )
        await chat_service.chat(request)

        answer_call = mock_llm.chat.call_args_list[1]
        assert (
            get_pastoral_register_note("it") not in answer_call.kwargs["messages"][0].content
        )


@pytest.mark.asyncio
class TestChatStreamCulturalTone:
    @patch("chat.service.settings")
    async def test_guidance_it_turn_receives_note(self, mock_settings, chat_service, mock_llm):
        _settings_for_cultural_tone(mock_settings, cultural_tone_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GUIDANCE", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in ["Let's think about this together."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(
            message="Should I take this job?", language="it", include_search=False
        )
        _ = [c async for c in chat_service.chat_stream(request)]

        stream_call = mock_llm.chat_stream.call_args
        assert get_pastoral_register_note("it") in stream_call.kwargs["messages"][0].content

    @patch("chat.service.settings")
    async def test_off_topic_it_turn_never_receives_note(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_cultural_tone(mock_settings, cultural_tone_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="OFF_TOPIC", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in ["Let's talk about faith instead."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="who won the Super Bowl?", language="it", include_search=False)
        _ = [c async for c in chat_service.chat_stream(request)]

        stream_call = mock_llm.chat_stream.call_args
        assert (
            get_pastoral_register_note("it") not in stream_call.kwargs["messages"][0].content
        )

    @patch("chat.service.settings")
    async def test_flag_disabled_never_applies_even_for_comfort_it(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_cultural_tone(mock_settings, cultural_tone_enabled=False)
        mock_llm.chat.return_value = LLMResponse(content="COMFORT", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in ["I hear you."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="I'm really struggling", language="it", include_search=False)
        _ = [c async for c in chat_service.chat_stream(request)]

        stream_call = mock_llm.chat_stream.call_args
        assert (
            get_pastoral_register_note("it") not in stream_call.kwargs["messages"][0].content
        )

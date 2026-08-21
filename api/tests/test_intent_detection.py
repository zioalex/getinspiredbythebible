"""
Tests for intent detection and off-topic filtering.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.prompts import CLARIFICATION_PROMPT, OFF_TOPIC_PROMPT, detect_intent_prompt
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
# detect_intent_prompt() tests
# ---------------------------------------------------------------------------


class TestDetectIntentPrompt:
    def test_returns_string_with_message(self):
        result = detect_intent_prompt("What is John 3:16?")
        assert "What is John 3:16?" in result

    def test_contains_all_categories(self):
        result = detect_intent_prompt("hello")
        for cat in [
            "COMFORT",
            "GUIDANCE",
            "CURIOSITY",
            "VERSE_LOOKUP",
            "NEEDS_CLARIFICATION",
            "OFF_TOPIC",
            "GENERAL",
        ]:
            assert cat in result

    def test_contains_fail_open_instruction(self):
        result = detect_intent_prompt("hello")
        assert "When in doubt" in result

    def test_contains_clarification_exclusions(self):
        result = detect_intent_prompt("hello")
        assert "Do NOT choose this when the message already names a situation" in result
        assert "When in doubt between NEEDS_CLARIFICATION" in result

    def test_contains_only_instruction(self):
        result = detect_intent_prompt("hello")
        assert "ONLY the category name" in result


# ---------------------------------------------------------------------------
# _detect_intent() tests
# ---------------------------------------------------------------------------


class TestDetectIntent:
    @pytest.mark.asyncio
    async def test_returns_valid_category(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(content="OFF_TOPIC", model="m", provider="p")
        result = await chat_service._detect_intent("best pizza recipe")
        assert result == "OFF_TOPIC"

    @pytest.mark.asyncio
    async def test_strips_whitespace_and_uppercases(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(content="  comfort  \n", model="m", provider="p")
        result = await chat_service._detect_intent("I'm sad")
        assert result == "COMFORT"

    @pytest.mark.asyncio
    async def test_returns_needs_clarification(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(
            content="NEEDS_CLARIFICATION", model="m", provider="p"
        )
        result = await chat_service._detect_intent("help")
        assert result == "NEEDS_CLARIFICATION"

    @pytest.mark.asyncio
    async def test_takes_first_word(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(
            content="GUIDANCE - the user wants advice", model="m", provider="p"
        )
        result = await chat_service._detect_intent("should I change jobs?")
        assert result == "GUIDANCE"

    @pytest.mark.asyncio
    async def test_unexpected_response_returns_general(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(content="BANANA", model="m", provider="p")
        result = await chat_service._detect_intent("something weird")
        assert result == "GENERAL"

    @pytest.mark.asyncio
    async def test_empty_response_returns_general(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(content="", model="m", provider="p")
        result = await chat_service._detect_intent("empty")
        assert result == "GENERAL"

    @pytest.mark.asyncio
    async def test_llm_error_returns_general(self, chat_service, mock_llm):
        mock_llm.chat.side_effect = RuntimeError("LLM down")
        result = await chat_service._detect_intent("anything")
        assert result == "GENERAL"

    @pytest.mark.asyncio
    async def test_uses_low_temperature(self, chat_service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")
        await chat_service._detect_intent("hello")
        call_kwargs = mock_llm.chat.call_args
        assert call_kwargs.kwargs["temperature"] == 0.0
        assert call_kwargs.kwargs["max_tokens"] == 20


# ---------------------------------------------------------------------------
# chat() off-topic flow tests
# ---------------------------------------------------------------------------


class TestChatOffTopicFlow:
    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_off_topic_skips_scripture_search(self, mock_settings, chat_service, mock_llm):
        mock_settings.content_filter_intent_detection = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_conversation_history = 10

        # First call: intent detection returns OFF_TOPIC
        # Second call: the redirect response
        mock_llm.chat.side_effect = [
            LLMResponse(content="OFF_TOPIC", model="m", provider="p"),
            LLMResponse(
                content="I'd love to help with spiritual questions!",
                model="m",
                provider="p",
            ),
        ]

        request = ChatRequest(message="best travel destinations?")
        response = await chat_service.chat(request)

        assert response.scripture_context is None
        assert "spiritual" in response.message.lower() or response.message  # redirect text
        # LLM should have been called exactly twice (intent + redirect)
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_on_topic_proceeds_normally(self, mock_settings, chat_service, mock_llm):
        mock_settings.content_filter_intent_detection = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_context_verses = 10
        mock_settings.max_conversation_history = 10
        mock_settings.query_expansion_enabled = False  # NEW: disable query expansion
        # This test isolates intent routing (on-topic proceeds to generation). The
        # BITB-058 fail-closed grounding guard — which would intercept a scripture-
        # seeking request that finds zero verses — is covered separately in
        # test_chat_coverage; keep it non-blocking here so search returning None
        # still exercises the normal generation path.
        mock_settings.require_scripture_grounding = False

        # First call: intent detection returns COMFORT
        # Second call: main LLM response
        mock_llm.chat.side_effect = [
            LLMResponse(content="COMFORT", model="m", provider="p"),
            LLMResponse(content="God is with you.", model="m", provider="p"),
        ]

        # Mock the search service to avoid DB calls
        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(return_value=None)
        chat_service.search_service.search_hybrid = AsyncMock(return_value=None)
        chat_service.search_service.search_hybrid_boosted = AsyncMock(return_value=None)
        chat_service.search_service.get_verse = AsyncMock(return_value=None)
        chat_service.search_service.get_verse_range = AsyncMock(return_value=[])

        request = ChatRequest(message="I feel anxious")
        response = await chat_service.chat(request)

        assert response.message == "God is with you."

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_disabled_setting_skips_detection(self, mock_settings, chat_service, mock_llm):
        mock_settings.content_filter_intent_detection = False
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_context_verses = 10
        mock_settings.max_conversation_history = 10
        mock_settings.query_expansion_enabled = False  # NEW: disable query expansion

        mock_llm.chat.return_value = LLMResponse(
            content="Here are some travel tips!", model="m", provider="p"
        )

        # Mock the search service to avoid DB calls
        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(return_value=None)
        chat_service.search_service.search_hybrid = AsyncMock(return_value=None)
        chat_service.search_service.search_hybrid_boosted = AsyncMock(return_value=None)
        chat_service.search_service.get_verse = AsyncMock(return_value=None)
        chat_service.search_service.get_verse_range = AsyncMock(return_value=[])

        request = ChatRequest(message="best travel destinations?")
        response = await chat_service.chat(request)

        # Should only be called once (main response), no intent detection
        assert mock_llm.chat.call_count == 1
        assert response.message == "Here are some travel tips!"


# ---------------------------------------------------------------------------
# _build_messages() off_topic prompt type tests
# ---------------------------------------------------------------------------


class TestBuildMessagesOffTopic:
    def test_off_topic_includes_off_topic_prompt(self, chat_service):
        messages = chat_service._build_messages(
            user_message="best pizza recipe",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="off_topic",
        )
        system_msg = messages[0].content
        assert OFF_TOPIC_PROMPT in system_msg

    def test_off_topic_includes_base_system_prompt(self, chat_service):
        messages = chat_service._build_messages(
            user_message="best pizza recipe",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="off_topic",
        )
        system_msg = messages[0].content
        assert "compassionate spiritual companion" in system_msg

    def test_default_does_not_include_off_topic_prompt(self, chat_service):
        messages = chat_service._build_messages(
            user_message="I feel sad",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="default",
        )
        system_msg = messages[0].content
        assert OFF_TOPIC_PROMPT not in system_msg


# ---------------------------------------------------------------------------
# chat_stream() off-topic flow tests
# ---------------------------------------------------------------------------


class TestChatStreamOffTopic:
    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_stream_off_topic_short_circuits(self, mock_settings, chat_service, mock_llm):
        mock_settings.content_filter_intent_detection = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_conversation_history = 10

        # Intent detection call
        mock_llm.chat.return_value = LLMResponse(content="OFF_TOPIC", model="m", provider="p")

        # Stream call
        async def mock_stream(*args, **kwargs):
            for chunk in ["I'd ", "love ", "to help!"]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="who won the Super Bowl?")
        chunks = []
        async for chunk in chat_service.chat_stream(request):
            chunks.append(chunk)

        # First chunk is metadata, next 3 are content, last is completion
        assert len(chunks) == 5
        assert chunks[0]["type"] == "metadata"
        content = "".join(c["content"] for c in chunks if c["type"] == "content")
        assert content == "I'd love to help!"
        assert chunks[-1]["type"] == "completion"

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_stream_on_topic_proceeds_normally(self, mock_settings, chat_service, mock_llm):
        mock_settings.content_filter_intent_detection = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_context_verses = 10
        mock_settings.max_conversation_history = 10

        # Intent detection returns GENERAL
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")

        # Mock search service
        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(return_value=None)
        chat_service.search_service.get_verse = AsyncMock(return_value=None)
        chat_service.search_service.get_verse_range = AsyncMock(return_value=[])

        async def mock_stream(*args, **kwargs):
            for chunk in ["God ", "loves ", "you."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="tell me about God's love")
        chunks = []
        async for chunk in chat_service.chat_stream(request):
            chunks.append(chunk)

        # First chunk is metadata, next 3 are content, last is completion
        assert len(chunks) == 5
        assert chunks[0]["type"] == "metadata"
        content = "".join(c["content"] for c in chunks if c["type"] == "content")
        assert content == "God loves you."
        assert chunks[-1]["type"] == "completion"


# ---------------------------------------------------------------------------
# _wants_clarification() gate tests (BITB-078)
# ---------------------------------------------------------------------------


class TestWantsClarificationGate:
    """The gate is enforced in code, not left to the classifier's judgement --
    these exercise each non-negotiable exclusion in isolation."""

    @patch("chat.service.settings")
    def test_asks_when_all_conditions_met(self, mock_settings, chat_service):
        mock_settings.chat_clarification_enabled = True
        assert chat_service._wants_clarification(
            "NEEDS_CLARIFICATION", is_verse_lookup=False, compassionate=False, history_len=0
        )

    @patch("chat.service.settings")
    def test_flag_disabled_never_asks(self, mock_settings, chat_service):
        mock_settings.chat_clarification_enabled = False
        assert not chat_service._wants_clarification(
            "NEEDS_CLARIFICATION", is_verse_lookup=False, compassionate=False, history_len=0
        )

    @patch("chat.service.settings")
    def test_wrong_intent_never_asks(self, mock_settings, chat_service):
        mock_settings.chat_clarification_enabled = True
        assert not chat_service._wants_clarification(
            "GENERAL", is_verse_lookup=False, compassionate=False, history_len=0
        )

    @patch("chat.service.settings")
    def test_verse_lookup_never_asks(self, mock_settings, chat_service):
        mock_settings.chat_clarification_enabled = True
        assert not chat_service._wants_clarification(
            "NEEDS_CLARIFICATION", is_verse_lookup=True, compassionate=False, history_len=0
        )

    @patch("chat.service.settings")
    def test_compassionate_never_asks(self, mock_settings, chat_service):
        mock_settings.chat_clarification_enabled = True
        assert not chat_service._wants_clarification(
            "NEEDS_CLARIFICATION", is_verse_lookup=False, compassionate=True, history_len=0
        )

    @patch("chat.service.settings")
    def test_follow_up_turn_never_asks(self, mock_settings, chat_service):
        """At most one clarifying question per conversation: once there's any
        history, the request already has context on the table."""
        mock_settings.chat_clarification_enabled = True
        assert not chat_service._wants_clarification(
            "NEEDS_CLARIFICATION", is_verse_lookup=False, compassionate=False, history_len=1
        )


# ---------------------------------------------------------------------------
# chat() clarification flow tests (BITB-078)
# ---------------------------------------------------------------------------


class TestChatNeedsClarificationFlow:
    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_clarification_skips_scripture_search(
        self, mock_settings, chat_service, mock_llm
    ):
        mock_settings.content_filter_intent_detection = True
        mock_settings.chat_clarification_enabled = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_conversation_history = 10

        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(
            side_effect=AssertionError("search should have been skipped")
        )

        mock_llm.chat.side_effect = [
            LLMResponse(content="NEEDS_CLARIFICATION", model="m", provider="p"),
            LLMResponse(
                content="That sounds hard. What's been weighing on you?",
                model="m",
                provider="p",
            ),
        ]

        request = ChatRequest(message="I'm lost")
        response = await chat_service.chat(request)

        assert response.scripture_context is None
        assert response.message == "That sounds hard. What's been weighing on you?"
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_second_turn_answers_instead_of_asking_again(
        self, mock_settings, chat_service, mock_llm
    ):
        """A second vague message in an existing conversation gets a full answer,
        not another clarifying question -- the one-question-per-conversation cap."""
        mock_settings.content_filter_intent_detection = True
        mock_settings.chat_clarification_enabled = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_context_verses = 10
        mock_settings.max_conversation_history = 10
        mock_settings.query_expansion_enabled = False
        mock_settings.require_scripture_grounding = False

        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(return_value=None)
        chat_service.search_service.search_hybrid = AsyncMock(return_value=None)
        chat_service.search_service.search_hybrid_boosted = AsyncMock(return_value=None)
        chat_service.search_service.get_verse = AsyncMock(return_value=None)
        chat_service.search_service.get_verse_range = AsyncMock(return_value=[])

        mock_llm.chat.side_effect = [
            LLMResponse(content="NEEDS_CLARIFICATION", model="m", provider="p"),
            LLMResponse(content="I hear you, here is a word of comfort.", model="m", provider="p"),
        ]

        request = ChatRequest(
            message="still lost",
            conversation_history=[
                {"role": "user", "content": "I'm lost"},
                {"role": "assistant", "content": "What's been weighing on you?"},
            ],
        )
        response = await chat_service.chat(request)

        assert response.message == "I hear you, here is a word of comfort."


# ---------------------------------------------------------------------------
# _build_messages() clarification prompt type tests (BITB-078)
# ---------------------------------------------------------------------------


class TestBuildMessagesClarification:
    def test_clarification_includes_clarification_prompt(self, chat_service):
        messages = chat_service._build_messages(
            user_message="I'm lost",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="clarification",
        )
        system_msg = messages[0].content
        assert CLARIFICATION_PROMPT in system_msg

    def test_clarification_includes_base_system_prompt(self, chat_service):
        messages = chat_service._build_messages(
            user_message="I'm lost",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="clarification",
        )
        system_msg = messages[0].content
        assert "compassionate spiritual companion" in system_msg

    def test_default_does_not_include_clarification_prompt(self, chat_service):
        messages = chat_service._build_messages(
            user_message="I feel sad",
            history=[],
            search_context="",
            language_code="en",
            prompt_type="default",
        )
        system_msg = messages[0].content
        assert CLARIFICATION_PROMPT not in system_msg


# ---------------------------------------------------------------------------
# chat_stream() clarification flow tests (BITB-078)
# ---------------------------------------------------------------------------


class TestChatStreamNeedsClarification:
    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_stream_clarification_short_circuits(self, mock_settings, chat_service, mock_llm):
        mock_settings.content_filter_intent_detection = True
        mock_settings.chat_clarification_enabled = True
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_conversation_history = 10

        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(
            side_effect=AssertionError("search should have been skipped")
        )

        mock_llm.chat.return_value = LLMResponse(
            content="NEEDS_CLARIFICATION", model="m", provider="p"
        )

        async def mock_stream(*args, **kwargs):
            for chunk in ["What's ", "on ", "your heart?"]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="pray for me")
        chunks = []
        async for chunk in chat_service.chat_stream(request):
            chunks.append(chunk)

        assert len(chunks) == 5
        assert chunks[0]["type"] == "metadata"
        assert chunks[0]["scripture_context"] is None
        content = "".join(c["content"] for c in chunks if c["type"] == "content")
        assert content == "What's on your heart?"
        assert chunks[-1]["type"] == "completion"
        assert chunks[-1]["verses_cited"] == []

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    async def test_stream_flag_disabled_proceeds_normally(
        self, mock_settings, chat_service, mock_llm
    ):
        mock_settings.content_filter_intent_detection = True
        mock_settings.chat_clarification_enabled = False
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.max_context_verses = 10
        mock_settings.max_conversation_history = 10

        chat_service.search_service = AsyncMock()
        chat_service.search_service.search = AsyncMock(return_value=None)
        chat_service.search_service.get_verse = AsyncMock(return_value=None)
        chat_service.search_service.get_verse_range = AsyncMock(return_value=[])

        mock_llm.chat.return_value = LLMResponse(
            content="NEEDS_CLARIFICATION", model="m", provider="p"
        )

        async def mock_stream(*args, **kwargs):
            for chunk in ["Here ", "is ", "a verse."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="pray for me")
        chunks = []
        async for chunk in chat_service.chat_stream(request):
            chunks.append(chunk)

        # Flag off: falls through to the normal (non-clarification) path, which
        # sends real scripture-search metadata rather than short-circuiting.
        assert chunks[0]["type"] == "metadata"
        content = "".join(c["content"] for c in chunks if c["type"] == "content")
        assert content == "Here is a verse."

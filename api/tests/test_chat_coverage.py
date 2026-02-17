"""
Tests for chat service and prompts modules.

Coverage targets:
- chat/prompts.py: get_system_prompt, get_verse_lookup_prompt, get_prayer_lookup_prompt,
  build_search_context_prompt, build_conversation_context, detect_intent_prompt
- chat/service.py: ChatService.chat, chat_stream, _search_scripture,
  _lookup_direct_verses, _merge_direct_verses, _determine_prompt_type, _build_messages,
  get_verse_context
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.prompts import (
    LANGUAGE_NAMES,
    SYSTEM_PROMPT,
    build_conversation_context,
    build_search_context_prompt,
    detect_intent_prompt,
    get_prayer_lookup_prompt,
    get_system_prompt,
    get_verse_lookup_prompt,
)
from chat.service import (
    ChatRequest,
    ChatResponse,
    ChatService,
    ConversationMessage,
)
from providers import LLMResponse
from scripture.search import SearchResults, VerseResult

# ==================== Prompts Tests ====================


class TestGetSystemPrompt:
    """Tests for get_system_prompt()."""

    def test_english_default(self):
        result = get_system_prompt()
        assert "respond in English" in result.lower() or "writing in English" in result

    def test_english_explicit(self):
        result = get_system_prompt("en")
        assert "The user is writing in English" in result

    def test_italian(self):
        result = get_system_prompt("it")
        assert "Italian" in result
        assert "You MUST respond entirely in" in result
        assert "Do not switch to English" in result

    def test_german(self):
        result = get_system_prompt("de")
        assert "German" in result
        assert "You MUST respond entirely in" in result

    def test_spanish(self):
        result = get_system_prompt("es")
        assert "Spanish" in result

    def test_french(self):
        result = get_system_prompt("fr")
        assert "French" in result

    def test_portuguese(self):
        result = get_system_prompt("pt")
        assert "Portuguese" in result

    def test_unknown_language_falls_back(self):
        result = get_system_prompt("xx")
        # Should still produce a valid prompt (falls back to English name)
        assert "language_instruction" not in result
        assert len(result) > 100

    def test_contains_template_content(self):
        result = get_system_prompt("en")
        assert "compassionate spiritual companion" in result
        assert "Scripture Context" in result or "scripture" in result.lower()


class TestGetVerseLookupPrompt:
    """Tests for get_verse_lookup_prompt()."""

    def test_english_default(self):
        result = get_verse_lookup_prompt()
        assert "writing in English" in result

    def test_english_explicit(self):
        result = get_verse_lookup_prompt("en")
        assert "writing in English" in result

    def test_non_english(self):
        result = get_verse_lookup_prompt("it")
        assert "Italian" in result
        assert "You MUST respond entirely in" in result

    def test_contains_verse_content(self):
        result = get_verse_lookup_prompt("en")
        assert "Bible study companion" in result or "Bible verse" in result.lower()


class TestGetPrayerLookupPrompt:
    """Tests for get_prayer_lookup_prompt()."""

    def test_english_default(self):
        result = get_prayer_lookup_prompt()
        assert "writing in English" in result

    def test_english_explicit(self):
        result = get_prayer_lookup_prompt("en")
        assert "writing in English" in result

    def test_non_english(self):
        result = get_prayer_lookup_prompt("de")
        assert "German" in result
        assert "You MUST respond entirely in" in result

    def test_contains_prayer_content(self):
        result = get_prayer_lookup_prompt("en")
        assert "prayer" in result.lower()


class TestBuildSearchContextPrompt:
    """Tests for build_search_context_prompt()."""

    def test_with_verses(self):
        results = {
            "verses": [{"reference": "John 3:16", "text": "For God so loved the world..."}],
            "passages": [],
        }
        result = build_search_context_prompt(results)
        assert "Scripture Context" in result
        assert "John 3:16" in result
        assert "For God so loved the world" in result
        assert "verified biblical texts" in result

    def test_with_passages(self):
        results = {
            "verses": [],
            "passages": [
                {
                    "title": "The Lord's Prayer",
                    "reference": "Matthew 6:9-13",
                    "text": "Our Father, who art in heaven...",
                }
            ],
        }
        result = build_search_context_prompt(results)
        assert "Scripture Context" in result
        assert "The Lord's Prayer" in result
        assert "Matthew 6:9-13" in result

    def test_with_both_verses_and_passages(self):
        results = {
            "verses": [{"reference": "John 3:16", "text": "For God so loved the world..."}],
            "passages": [
                {
                    "title": "The Lord's Prayer",
                    "reference": "Matthew 6:9-13",
                    "text": "Our Father...",
                }
            ],
        }
        result = build_search_context_prompt(results)
        assert "John 3:16" in result
        assert "The Lord's Prayer" in result

    def test_empty_results(self):
        results = {"verses": [], "passages": []}
        result = build_search_context_prompt(results)
        assert "No specific Bible verses were found" in result

    def test_no_keys(self):
        result = build_search_context_prompt({})
        assert "No specific Bible verses were found" in result

    def test_long_passage_truncated(self):
        long_text = "x" * 1000
        results = {
            "verses": [],
            "passages": [
                {
                    "title": "Long Passage",
                    "reference": "Genesis 1:1-31",
                    "text": long_text,
                }
            ],
        }
        result = build_search_context_prompt(results)
        assert "..." in result
        # Should not contain the full 1000-char text
        assert long_text not in result

    def test_passage_under_500_not_truncated(self):
        short_text = "x" * 499
        results = {
            "verses": [],
            "passages": [
                {
                    "title": "Short Passage",
                    "reference": "Genesis 1:1",
                    "text": short_text,
                }
            ],
        }
        result = build_search_context_prompt(results)
        assert short_text in result


class TestBuildConversationContext:
    """Tests for build_conversation_context()."""

    def test_empty_messages(self):
        result = build_conversation_context([])
        assert result == ""

    def test_single_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = build_conversation_context(messages)
        assert "Conversation Context" in result
        assert "**User**: Hello" in result

    def test_user_and_assistant(self):
        messages = [
            {"role": "user", "content": "Help me"},
            {"role": "assistant", "content": "I'd be happy to help"},
        ]
        result = build_conversation_context(messages)
        assert "**User**: Help me" in result
        assert "**Assistant**: I'd be happy to help" in result

    def test_long_message_truncated(self):
        long_content = "x" * 300
        messages = [{"role": "user", "content": long_content}]
        result = build_conversation_context(messages)
        assert "..." in result
        assert long_content not in result

    def test_keeps_last_six_messages(self):
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]
        result = build_conversation_context(messages)
        # Should only have the last 6 messages
        assert "Message 4" in result
        assert "Message 9" in result
        # Should not have the first 4 messages
        assert "Message 0" not in result
        assert "Message 3" not in result

    def test_message_under_200_not_truncated(self):
        content = "x" * 199
        messages = [{"role": "user", "content": content}]
        result = build_conversation_context(messages)
        assert content in result


class TestDetectIntentPrompt:
    """Tests for detect_intent_prompt()."""

    def test_generates_prompt(self):
        result = detect_intent_prompt("I am feeling sad")
        assert "I am feeling sad" in result
        assert "COMFORT" in result
        assert "GUIDANCE" in result
        assert "CURIOSITY" in result
        assert "VERSE_LOOKUP" in result
        assert "GENERAL" in result

    def test_prompt_asks_for_category(self):
        result = detect_intent_prompt("test message")
        assert "category" in result.lower()


class TestLanguageNames:
    """Tests for LANGUAGE_NAMES constant."""

    def test_has_expected_languages(self):
        assert "en" in LANGUAGE_NAMES
        assert "it" in LANGUAGE_NAMES
        assert "de" in LANGUAGE_NAMES
        assert "es" in LANGUAGE_NAMES
        assert "fr" in LANGUAGE_NAMES
        assert "pt" in LANGUAGE_NAMES


class TestSystemPromptConstant:
    """Tests for the SYSTEM_PROMPT constant (backward compat)."""

    def test_system_prompt_is_english(self):
        assert "writing in English" in SYSTEM_PROMPT


# ==================== Chat Service Tests ====================


def _make_chat_service():
    """Create a ChatService with mocked dependencies."""
    db_session = AsyncMock()
    llm_provider = AsyncMock()
    llm_provider.provider_name = "test-provider"
    embedding_provider = AsyncMock()
    embedding_provider.embed = AsyncMock()

    service = ChatService(db_session, llm_provider, embedding_provider)
    return service, llm_provider, embedding_provider


class TestChatServiceDeterminePromptType:
    """Tests for ChatService._determine_prompt_type()."""

    def test_default_type(self):
        service, _, _ = _make_chat_service()
        result = service._determine_prompt_type(False, None)
        assert result == "default"

    def test_verse_lookup_type(self):
        service, _, _ = _make_chat_service()
        result = service._determine_prompt_type(True, None)
        assert result == "verse_lookup"

    def test_prayer_lookup_type(self):
        service, _, _ = _make_chat_service()
        prayer_ref = MagicMock()
        prayer_ref.name = "Lord's Prayer"
        result = service._determine_prompt_type(True, prayer_ref)
        assert result == "prayer_lookup"

    def test_prayer_ref_without_verse_lookup(self):
        service, _, _ = _make_chat_service()
        prayer_ref = MagicMock()
        result = service._determine_prompt_type(False, prayer_ref)
        assert result == "default"


class TestChatServiceBuildMessages:
    """Tests for ChatService._build_messages()."""

    def test_default_prompt(self):
        service, _, _ = _make_chat_service()
        messages = service._build_messages(
            user_message="Hello",
            history=[],
        )
        assert len(messages) == 2  # system + user
        assert messages[0].role == "system"
        assert messages[-1].role == "user"
        assert messages[-1].content == "Hello"

    def test_with_history(self):
        service, _, _ = _make_chat_service()
        history = [
            ConversationMessage(role="user", content="First message"),
            ConversationMessage(role="assistant", content="First response"),
        ]
        messages = service._build_messages(
            user_message="Second message",
            history=history,
        )
        # system + 2 history + user
        assert len(messages) == 4
        assert messages[1].content == "First message"
        assert messages[2].content == "First response"
        assert messages[3].content == "Second message"

    def test_with_search_context(self):
        service, _, _ = _make_chat_service()
        messages = service._build_messages(
            user_message="Hello",
            history=[],
            search_context="## Scripture Context\nSome verses here",
        )
        system_msg = messages[0]
        assert "Scripture Context" in system_msg.content

    def test_verse_lookup_prompt_type(self):
        service, _, _ = _make_chat_service()
        messages = service._build_messages(
            user_message="Tell me about John 3:16",
            history=[],
            prompt_type="verse_lookup",
        )
        system_msg = messages[0]
        assert (
            "Bible study companion" in system_msg.content
            or "Bible verse" in system_msg.content.lower()
        )

    def test_prayer_lookup_prompt_type(self):
        service, _, _ = _make_chat_service()
        messages = service._build_messages(
            user_message="Tell me about the Hail Mary",
            history=[],
            prompt_type="prayer_lookup",
        )
        system_msg = messages[0]
        assert "prayer" in system_msg.content.lower()

    def test_non_english_language(self):
        service, _, _ = _make_chat_service()
        messages = service._build_messages(
            user_message="Ciao",
            history=[],
            language_code="it",
        )
        system_msg = messages[0]
        assert "Italian" in system_msg.content


class TestChatServiceMergeDirectVerses:
    """Tests for ChatService._merge_direct_verses()."""

    def test_merge_new_verses(self):
        service, _, _ = _make_chat_service()
        context = SearchResults(
            query="test",
            verses=[
                VerseResult(
                    reference="John 3:16",
                    text="For God so loved...",
                    book="John",
                    chapter=3,
                    verse=16,
                )
            ],
            passages=[],
        )
        direct_verses = [
            VerseResult(
                reference="Genesis 1:1",
                text="In the beginning...",
                book="Genesis",
                chapter=1,
                verse=1,
            )
        ]
        service._merge_direct_verses(context, direct_verses)
        assert len(context.verses) == 2
        # Direct verse should be at the beginning
        assert context.verses[0].reference == "Genesis 1:1"

    def test_no_duplicates(self):
        service, _, _ = _make_chat_service()
        context = SearchResults(
            query="test",
            verses=[
                VerseResult(
                    reference="John 3:16",
                    text="For God so loved...",
                    book="John",
                    chapter=3,
                    verse=16,
                )
            ],
            passages=[],
        )
        # Same verse as already in context
        direct_verses = [
            VerseResult(
                reference="John 3:16",
                text="For God so loved...",
                book="John",
                chapter=3,
                verse=16,
            )
        ]
        service._merge_direct_verses(context, direct_verses)
        assert len(context.verses) == 1

    def test_empty_direct_verses(self):
        service, _, _ = _make_chat_service()
        context = SearchResults(
            query="test",
            verses=[],
            passages=[],
        )
        service._merge_direct_verses(context, [])
        assert len(context.verses) == 0

    def test_none_context(self):
        service, _, _ = _make_chat_service()
        # Should not raise
        service._merge_direct_verses(
            None,
            [VerseResult(reference="Gen 1:1", text="test", book="Genesis", chapter=1, verse=1)],
        )


class TestChatServiceChat:
    """Tests for ChatService.chat()."""

    @pytest.mark.asyncio
    @patch("chat.service.detect_language", return_value="en")
    @patch("chat.service.resolve_translation", return_value="kjv")
    @patch("chat.service.get_translation_info", return_value={"code": "kjv", "name": "KJV"})
    @patch("chat.service.is_verse_lookup_request", return_value=False)
    @patch("chat.service.extract_references", return_value=([], None))
    async def test_chat_basic(
        self, mock_extract, mock_is_verse, mock_trans_info, mock_resolve, mock_detect
    ):
        service, llm, embedding = _make_chat_service()

        # Mock search service
        service.search_service = AsyncMock()
        service.search_service.search = AsyncMock(
            return_value=SearchResults(query="test", verses=[], passages=[])
        )

        # Mock LLM response
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="God loves you!",
                provider="test",
                model="test-model",
            )
        )

        request = ChatRequest(message="I need encouragement")
        response = await service.chat(request)

        assert isinstance(response, ChatResponse)
        assert response.message == "God loves you!"
        assert response.provider == "test"
        assert response.model == "test-model"
        assert response.message_id  # Should be a UUID string

    @pytest.mark.asyncio
    @patch("chat.service.detect_language", return_value="en")
    @patch("chat.service.resolve_translation", return_value="kjv")
    @patch("chat.service.get_translation_info", return_value=None)
    @patch("chat.service.is_verse_lookup_request", return_value=False)
    @patch("chat.service.extract_references", return_value=([], None))
    async def test_chat_llm_error(
        self, mock_extract, mock_is_verse, mock_trans_info, mock_resolve, mock_detect
    ):
        service, llm, _ = _make_chat_service()

        service.search_service = AsyncMock()
        service.search_service.search = AsyncMock(
            return_value=SearchResults(query="test", verses=[], passages=[])
        )

        llm.chat = AsyncMock(side_effect=Exception("LLM connection failed"))

        request = ChatRequest(message="Help me")
        with pytest.raises(Exception, match="LLM connection failed"):
            await service.chat(request)

    @pytest.mark.asyncio
    @patch("chat.service.detect_language", return_value="en")
    @patch("chat.service.resolve_translation", return_value="kjv")
    @patch("chat.service.get_translation_info", return_value=None)
    @patch("chat.service.is_verse_lookup_request", return_value=False)
    @patch("chat.service.extract_references", return_value=([], None))
    async def test_chat_search_disabled(
        self, mock_extract, mock_is_verse, mock_trans_info, mock_resolve, mock_detect
    ):
        service, llm, _ = _make_chat_service()

        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Response", provider="test", model="m")
        )

        request = ChatRequest(message="Hello", include_search=False)
        response = await service.chat(request)

        assert response.scripture_context is None


class TestChatServiceSearchScripture:
    """Tests for ChatService._search_scripture()."""

    @pytest.mark.asyncio
    async def test_search_disabled(self):
        service, _, _ = _make_chat_service()
        request = ChatRequest(message="Hello", include_search=False)
        context, prompt = await service._search_scripture(request, "kjv", [], False)
        assert context is None
        assert prompt == ""

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        service, _, embedding = _make_chat_service()
        service.search_service = AsyncMock()
        search_result = SearchResults(
            query="test",
            verses=[
                VerseResult(
                    reference="John 3:16",
                    text="For God so loved the world...",
                    book="John",
                    chapter=3,
                    verse=16,
                )
            ],
            passages=[],
        )
        service.search_service.search = AsyncMock(return_value=search_result)

        request = ChatRequest(message="love")
        context, prompt = await service._search_scripture(request, "kjv", [], False)
        assert context is not None
        assert len(context.verses) == 1
        assert "Scripture Context" in prompt

    @pytest.mark.asyncio
    async def test_search_exception_returns_none(self):
        service, _, embedding = _make_chat_service()
        service.search_service = AsyncMock()
        service.search_service.search = AsyncMock(side_effect=Exception("DB error"))

        request = ChatRequest(message="test")
        context, prompt = await service._search_scripture(request, "kjv", [], False)
        assert context is None
        assert prompt == ""


class TestChatServiceLookupDirectVerses:
    """Tests for ChatService._lookup_direct_verses()."""

    @pytest.mark.asyncio
    async def test_empty_refs(self):
        service, _, _ = _make_chat_service()
        result = await service._lookup_direct_verses([], "kjv")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_verse_ref(self):
        service, _, _ = _make_chat_service()
        ref = MagicMock()
        ref.book = "John"
        ref.chapter = 3
        ref.verse_start = 16
        ref.verse_end = None

        verse = VerseResult(
            reference="John 3:16",
            text="For God so loved...",
            book="John",
            chapter=3,
            verse=16,
        )
        service.search_service = AsyncMock()
        service.search_service.get_verse = AsyncMock(return_value=verse)

        result = await service._lookup_direct_verses([ref], "kjv")
        assert len(result) == 1
        assert result[0].reference == "John 3:16"

    @pytest.mark.asyncio
    async def test_verse_range_ref(self):
        service, _, _ = _make_chat_service()
        ref = MagicMock()
        ref.book = "Genesis"
        ref.chapter = 1
        ref.verse_start = 1
        ref.verse_end = 3

        verses = [
            VerseResult(
                reference=f"Genesis 1:{i}", text=f"Verse {i}", book="Genesis", chapter=1, verse=i
            )
            for i in range(1, 4)
        ]
        service.search_service = AsyncMock()
        service.search_service.get_verse_range = AsyncMock(return_value=verses)

        result = await service._lookup_direct_verses([ref], "kjv")
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_verse_not_found(self):
        service, _, _ = _make_chat_service()
        ref = MagicMock()
        ref.book = "NotABook"
        ref.chapter = 1
        ref.verse_start = 1
        ref.verse_end = None

        service.search_service = AsyncMock()
        service.search_service.get_verse = AsyncMock(return_value=None)

        result = await service._lookup_direct_verses([ref], "kjv")
        assert result == []


class TestChatServiceChatStream:
    """Tests for ChatService.chat_stream()."""

    @pytest.mark.asyncio
    @patch("chat.service.detect_language", return_value="en")
    @patch("chat.service.resolve_translation", return_value="kjv")
    @patch("chat.service.is_verse_lookup_request", return_value=False)
    @patch("chat.service.extract_references", return_value=([], None))
    async def test_chat_stream_yields_chunks(
        self, mock_extract, mock_is_verse, mock_resolve, mock_detect
    ):
        service, llm, _ = _make_chat_service()

        service.search_service = AsyncMock()
        service.search_service.search = AsyncMock(
            return_value=SearchResults(query="test", verses=[], passages=[])
        )

        async def mock_stream(*args, **kwargs):
            yield "Hello "
            yield "world!"

        llm.chat_stream = mock_stream

        request = ChatRequest(message="Hi")
        chunks = []
        async for chunk in service.chat_stream(request):
            chunks.append(chunk)

        assert chunks == ["Hello ", "world!"]


class TestChatServiceGetVerseContext:
    """Tests for ChatService.get_verse_context()."""

    @pytest.mark.asyncio
    async def test_get_verse_context(self):
        service, _, _ = _make_chat_service()
        service.search_service = AsyncMock()

        mock_verses = [
            VerseResult(reference=f"John 3:{v}", text=f"Verse {v}", book="John", chapter=3, verse=v)
            for v in range(14, 19)
        ]
        service.search_service.get_context = AsyncMock(return_value=mock_verses)

        result = await service.get_verse_context("John", 3, 16)
        assert result["target_verse"] == 16
        assert len(result["verses"]) == 5


class TestChatRequestModel:
    """Tests for ChatRequest Pydantic model."""

    def test_valid_request(self):
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"
        assert req.include_search is True
        assert req.conversation_history == []

    def test_message_strip(self):
        req = ChatRequest(message="  Hello  ")
        assert req.message == "Hello"

    def test_empty_message_fails(self):
        with pytest.raises(Exception):
            ChatRequest(message="   ")

    def test_with_history(self):
        req = ChatRequest(
            message="Hello",
            conversation_history=[
                ConversationMessage(role="user", content="First msg"),
            ],
        )
        assert len(req.conversation_history) == 1

    def test_with_session_id(self):
        req = ChatRequest(message="Hello", session_id="abc-123")
        assert req.session_id == "abc-123"

    def test_invalid_session_id(self):
        with pytest.raises(Exception):
            ChatRequest(message="Hello", session_id="invalid id with spaces!!")

    def test_with_preferred_translation(self):
        req = ChatRequest(message="Hello", preferred_translation="kjv")
        assert req.preferred_translation == "kjv"


class TestConversationMessage:
    """Tests for ConversationMessage Pydantic model."""

    def test_user_message(self):
        msg = ConversationMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_message(self):
        msg = ConversationMessage(role="assistant", content="Hi there")
        assert msg.role == "assistant"

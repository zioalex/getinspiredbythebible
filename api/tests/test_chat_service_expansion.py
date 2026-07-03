"""
Tests for ChatService query expansion feature (BITB-018.1).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.service import ChatRequest, ChatService
from providers import LLMResponse
from scripture.search import SearchResults


def _make_chat_service():
    """Create a ChatService with mocked dependencies."""
    db_session = AsyncMock()
    llm_provider = AsyncMock()
    llm_provider.provider_name = "test-provider"
    embedding_provider = AsyncMock()
    embedding_provider.embed = AsyncMock()
    service = ChatService(db_session, llm_provider, embedding_provider)
    return service, llm_provider, embedding_provider


class TestExpandQuery:
    """Tests for ChatService._expand_query()."""

    @pytest.mark.asyncio
    async def test_expand_query_returns_expanded_text(self):
        """_expand_query() should return LLM-generated expansion."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="anxiety frustration anger peace trust God patience self-control",
                provider="test",
                model="test-model",
            )
        )
        result = await service._expand_query("I'm so frustrated", "en")
        assert "anxiety" in result or "frustration" in result or "peace" in result
        assert result != ""

    @pytest.mark.asyncio
    async def test_expand_query_uses_low_temperature(self):
        """_expand_query() should call LLM with temperature=0.3."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="peace calm trust", provider="test", model="m")
        )
        await service._expand_query("I need peace", "en")
        call_kwargs = llm.chat.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.3

    @pytest.mark.asyncio
    async def test_expand_query_fails_open(self):
        """_expand_query() should return original message if LLM call fails."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(side_effect=Exception("LLM error"))
        result = await service._expand_query("I need peace", "en")
        assert result == "I need peace"

    @pytest.mark.asyncio
    async def test_expand_query_multilingual(self):
        """_expand_query() should work with Italian input."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="frustrazione rabbia pace pazienza fiducia Dio controllo",
                provider="test",
                model="test-model",
            )
        )
        result = await service._expand_query("Sono frustrato", "it")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_expand_query_prompt_is_theme_focused(self):
        """BITB-050: the expansion prompt must steer the LLM toward the core
        theme and explicitly warn against drifting into off-theme terms that
        pull in irrelevant verses."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="peace trust", provider="test", model="m")
        )
        await service._expand_query("I'm anxious about the future", "en")
        sent_prompt = llm.chat.call_args.kwargs["messages"][0].content.lower()
        assert "thematically relevant" in sent_prompt
        assert "central" in sent_prompt and "theme" in sent_prompt
        # Must caution against topic drift / irrelevant verses.
        assert "drift" in sent_prompt or "off-theme" in sent_prompt
        assert "irrelevant" in sent_prompt

    @pytest.mark.asyncio
    async def test_expand_query_prompt_includes_justice_and_passage_themes(self):
        """BITB-050: the expansion prompt must steer toward social-justice /
        prophetic-justice themes and a named passage's key theology, and cap
        the word count at 120 (not 100)."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="justice judgment", provider="test", model="m")
        )
        await service._expand_query("What does Amos say about the poor?", "en")
        sent_prompt = llm.chat.call_args.kwargs["messages"][0].content.lower()
        # Must guide toward prophetic-justice themes when the question touches them.
        assert "justice" in sent_prompt
        assert "oppression" in sent_prompt or "poor" in sent_prompt or "inequality" in sent_prompt
        assert "judgment" in sent_prompt
        # Word cap raised to 120.
        assert "120 words" in sent_prompt
        assert "100 words" not in sent_prompt

    @pytest.mark.asyncio
    async def test_expand_query_with_model_override(self):
        """_expand_query() should pass model_override to LLM."""
        service, llm, _ = _make_chat_service()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="peace", provider="test", model="override-model")
        )
        await service._expand_query("peace", "ar", model_override="qwen/qwen-2.5-72b-instruct")
        call_kwargs = llm.chat.call_args.kwargs
        assert call_kwargs.get("model_override") == "qwen/qwen-2.5-72b-instruct"


class TestQueryExpansionFeatureFlag:
    """Tests for query expansion feature flag behavior."""

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    @patch("chat.service.detect_language", return_value="en")
    @patch("chat.service.resolve_translation", return_value="kjv")
    @patch("chat.service.get_translation_info", return_value=None)
    @patch("chat.service.get_model_override_for_language", return_value=None)
    @patch("chat.service.is_verse_lookup_request", return_value=False)
    @patch("chat.service.extract_references", return_value=([], None))
    async def test_expansion_disabled_by_default(
        self,
        mock_extract,
        mock_is_verse,
        mock_override,
        mock_trans_info,
        mock_resolve,
        mock_detect,
        mock_settings,
    ):
        """When query_expansion_enabled=False, _expand_query should NOT be called."""
        mock_settings.query_expansion_enabled = False
        mock_settings.hybrid_search_enabled = False
        mock_settings.topic_boosting_enabled = False
        mock_settings.content_filter_intent_detection = False
        mock_settings.max_context_verses = 10
        mock_settings.max_message_length = 200
        mock_settings.max_conversation_history = 10
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.llm_provider = "test"
        mock_settings.llm_model = "test-model"

        service, llm, embedding = _make_chat_service()

        service.search_service = AsyncMock()
        service.search_service.search = AsyncMock(
            return_value=SearchResults(query="test", verses=[], passages=[])
        )

        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Response", provider="test", model="m")
        )

        # Spy on _expand_query
        service._expand_query = AsyncMock(wraps=service._expand_query)

        request = ChatRequest(message="I am frustrated")
        await service.chat(request)

        # _expand_query should NOT have been called
        service._expand_query.assert_not_called()

    @pytest.mark.asyncio
    @patch("chat.service.settings")
    @patch("chat.service.detect_language", return_value="en")
    @patch("chat.service.resolve_translation", return_value="kjv")
    @patch("chat.service.get_translation_info", return_value=None)
    @patch("chat.service.get_model_override_for_language", return_value=None)
    @patch("chat.service.is_verse_lookup_request", return_value=False)
    @patch("chat.service.extract_references", return_value=([], None))
    async def test_expansion_enabled_calls_expand_query(
        self,
        mock_extract,
        mock_is_verse,
        mock_override,
        mock_trans_info,
        mock_resolve,
        mock_detect,
        mock_settings,
    ):
        """When query_expansion_enabled=True, _expand_query should be called."""
        mock_settings.query_expansion_enabled = True
        mock_settings.hybrid_search_enabled = False
        mock_settings.topic_boosting_enabled = False
        mock_settings.content_filter_intent_detection = False
        mock_settings.max_context_verses = 10
        mock_settings.max_message_length = 200
        mock_settings.max_conversation_history = 10
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 1024
        mock_settings.llm_provider = "test"
        mock_settings.llm_model = "test-model"

        service, llm, embedding = _make_chat_service()

        service.search_service = AsyncMock()
        service.search_service.search = AsyncMock(
            return_value=SearchResults(query="test", verses=[], passages=[])
        )

        # Mock embedding for expansion
        mock_embed_response = MagicMock()
        mock_embed_response.embedding = [0.2] * 1024
        service.embedding.embed = AsyncMock(return_value=mock_embed_response)

        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="peace calm trust patience", provider="test", model="m"
            )
        )

        # Spy on _expand_query to return expanded text
        service._expand_query = AsyncMock(return_value="peace calm trust patience forgiveness")

        request = ChatRequest(message="I am frustrated")
        await service.chat(request)

        # _expand_query should have been called
        service._expand_query.assert_called_once()

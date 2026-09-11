"""
Tests for BITB-080: suggested follow-up questions as one-tap chips.

Covers:
- chat/follow_ups.py: split_follow_ups (parsing/sanitizing the FOLLOWUPS trailer)
- chat/service.py: _wants_follow_ups gate
- chat/service.py: _build_messages injects FOLLOW_UP_SUGGESTIONS_GUIDANCE
- chat/service.py: chat() and chat_stream() emit/suppress follow_ups correctly
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.follow_ups import split_follow_ups
from chat.prompts import FOLLOW_UP_SUGGESTIONS_GUIDANCE
from chat.service import ChatRequest, ChatService, _SafetyOutcome
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
# 1. split_follow_ups() — pure parsing/sanitizing
# ---------------------------------------------------------------------------


class TestSplitFollowUps:
    def test_well_formed_trailer(self):
        body, suggestions = split_follow_ups(
            "The Lord is near. <!-- FOLLOWUPS: What does Psalm 34 mean?|How do I pray this?|"
            "What if the feeling returns? -->"
        )
        assert body == "The Lord is near."
        assert suggestions == [
            "What does Psalm 34 mean?",
            "How do I pray this?",
            "What if the feeling returns?",
        ]

    def test_missing_trailer_returns_original_text_unchanged(self):
        body, suggestions = split_follow_ups("Just an ordinary answer, no trailer at all.")
        assert body == "Just an ordinary answer, no trailer at all."
        assert suggestions == []

    def test_unterminated_comment_yields_no_suggestions(self):
        body, suggestions = split_follow_ups("Some text <!-- FOLLOWUPS: unterminated")
        assert suggestions == []
        assert body == "Some text <!-- FOLLOWUPS: unterminated"

    def test_empty_payload_yields_no_suggestions(self):
        body, suggestions = split_follow_ups("Text <!-- FOLLOWUPS:  -->")
        assert body == "Text"
        assert suggestions == []

    def test_separatorless_single_item_dropped(self):
        # No "|" and only one line -> one candidate -> below the 2-minimum, dropped.
        body, suggestions = split_follow_ups("Text <!-- FOLLOWUPS: just one question -->")
        assert body == "Text"
        assert suggestions == []

    def test_five_items_capped_at_three(self):
        body, suggestions = split_follow_ups("Text <!-- FOLLOWUPS: a|b|c|d|e -->")
        assert suggestions == ["a", "b", "c"]

    def test_one_surviving_item_after_cleanup_is_dropped(self):
        body, suggestions = split_follow_ups(
            "Text <!-- FOLLOWUPS: fine one|<script>bad</script> -->"
        )
        assert suggestions == []

    def test_oversized_suggestion_dropped_not_truncated(self):
        long_one = "x" * 121
        body, suggestions = split_follow_ups(
            f"Text <!-- FOLLOWUPS: {long_one}|short one|another one -->"
        )
        assert long_one not in suggestions
        assert suggestions == ["short one", "another one"]

    def test_markup_bearing_suggestion_dropped(self):
        body, suggestions = split_follow_ups(
            "Text <!-- FOLLOWUPS: normal one here|<b>bold</b> one|another normal one -->"
        )
        assert suggestions == ["normal one here", "another normal one"]

    def test_case_insensitive_duplicates_collapse(self):
        body, suggestions = split_follow_ups(
            "Text <!-- FOLLOWUPS: Hello there|hello there|Something else entirely -->"
        )
        assert suggestions == ["Hello there", "Something else entirely"]

    def test_both_verses_and_followups_trailers_only_followups_stripped(self):
        body, suggestions = split_follow_ups(
            "Answer. <!-- VERSES: John 3:16 --> <!-- FOLLOWUPS: q one here|q two here -->"
        )
        assert body == "Answer. <!-- VERSES: John 3:16 -->"
        assert suggestions == ["q one here", "q two here"]

    def test_fullwidth_bar_separator(self):
        body, suggestions = split_follow_ups("Text <!-- FOLLOWUPS: 第一个问题|第二个问题 -->")
        assert suggestions == ["第一个问题", "第二个问题"]

    def test_newline_separated_fallback(self):
        body, suggestions = split_follow_ups(
            "Text <!-- FOLLOWUPS: line one here\nline two here -->"
        )
        assert suggestions == ["line one here", "line two here"]


# ---------------------------------------------------------------------------
# 2. _wants_follow_ups() gate
# ---------------------------------------------------------------------------


class TestWantsFollowUpsGate:
    @patch("chat.service.settings")
    def test_asks_when_enabled_and_not_compassionate(self, mock_settings, chat_service):
        mock_settings.chat_follow_ups_enabled = True
        assert chat_service._wants_follow_ups(compassionate=False) is True

    @patch("chat.service.settings")
    def test_flag_disabled_never_offers(self, mock_settings, chat_service):
        mock_settings.chat_follow_ups_enabled = False
        assert chat_service._wants_follow_ups(compassionate=False) is False

    @patch("chat.service.settings")
    def test_compassionate_never_offers(self, mock_settings, chat_service):
        mock_settings.chat_follow_ups_enabled = True
        assert chat_service._wants_follow_ups(compassionate=True) is False


# ---------------------------------------------------------------------------
# 3. _build_messages() — guidance injection
# ---------------------------------------------------------------------------


class TestBuildMessagesFollowUps:
    def test_enabled_includes_guidance(self, chat_service):
        messages = chat_service._build_messages(
            user_message="hello",
            history=[],
            follow_ups_enabled=True,
        )
        assert FOLLOW_UP_SUGGESTIONS_GUIDANCE in messages[0].content

    def test_default_omits_guidance(self, chat_service):
        messages = chat_service._build_messages(user_message="hello", history=[])
        assert FOLLOW_UP_SUGGESTIONS_GUIDANCE not in messages[0].content

    def test_off_topic_never_includes_guidance_even_if_caller_forgets(self, chat_service):
        # Defense in depth: off_topic prompt_type callers in service.py never pass
        # follow_ups_enabled=True, but the builder itself must not be the only thing
        # standing between an off-topic reply and a leaked trailer instruction.
        messages = chat_service._build_messages(
            user_message="hello",
            history=[],
            prompt_type="off_topic",
        )
        assert FOLLOW_UP_SUGGESTIONS_GUIDANCE not in messages[0].content


# ---------------------------------------------------------------------------
# 4. chat_stream() — end-to-end follow_ups emission/suppression
# ---------------------------------------------------------------------------


def _settings_for_general_stream(mock_settings, *, follow_ups_enabled: bool):
    mock_settings.content_filter_intent_detection = True
    mock_settings.llm_temperature = 0.7
    mock_settings.llm_max_tokens = 1024
    mock_settings.max_conversation_history = 10
    mock_settings.max_context_verses = 10
    mock_settings.chat_follow_ups_enabled = follow_ups_enabled
    mock_settings.chat_clarification_enabled = False
    mock_settings.verse_grounding_enabled = True
    mock_settings.grounding_unresolved_behavior = "strip"
    mock_settings.grounding_paraphrases_mode = "detect"


@pytest.mark.asyncio
class TestChatStreamFollowUps:
    @patch("chat.service.settings")
    async def test_follow_ups_surfaced_when_enabled(self, mock_settings, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in [
                "God loves you. ",
                "<!-- FOLLOWUPS: What does this mean for me?|How can I pray about this? -->",
            ]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="tell me about God's love", include_search=False)
        chunks = [c async for c in chat_service.chat_stream(request)]

        completion = chunks[-1]
        assert completion["type"] == "completion"
        assert completion["follow_ups"] == [
            "What does this mean for me?",
            "How can I pray about this?",
        ]
        # The raw tokens streamed to the client as they arrived DO still contain the
        # trailer (nothing rewrites already-sent tokens) -- that's exactly why the
        # authoritative corrected_message must be sent so the client can swap it in.
        assert completion["corrected_message"] == "God loves you."
        assert "FOLLOWUPS" not in completion["corrected_message"]

    @patch("chat.service.settings")
    async def test_follow_ups_absent_when_flag_disabled(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=False)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in ["God loves you."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="tell me about God's love", include_search=False)
        chunks = [c async for c in chat_service.chat_stream(request)]

        completion = chunks[-1]
        assert "follow_ups" not in completion
        # No trailer was ever streamed, so no corrected_message is needed either.
        assert "corrected_message" not in completion

    @patch("chat.service.settings")
    async def test_older_backend_shape_unaffected_when_no_trailer_present(
        self, mock_settings, chat_service, mock_llm
    ):
        """Even with the flag on, a response with no FOLLOWUPS trailer (e.g. the
        model ignored the instruction) must not synthesize a corrected_message."""
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in ["God loves you."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="tell me about God's love", include_search=False)
        chunks = [c async for c in chat_service.chat_stream(request)]

        completion = chunks[-1]
        assert "follow_ups" not in completion
        assert "corrected_message" not in completion

    @patch("chat.service.settings")
    async def test_suggestion_citing_uncited_verse_is_dropped(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in [
                "God's love endures. ",
                "<!-- FOLLOWUPS: What does Psalm 200:1 say about this?|"
                "How can I pray about this today? -->",
            ]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="tell me about God's love", include_search=False)
        chunks = [c async for c in chat_service.chat_stream(request)]
        completion = chunks[-1]

        # "Psalm 200" doesn't exist as a citation in verses_cited (nothing was cited
        # at all here), so the whole batch collapses (1 candidate remains -> < 2 -> []).
        assert "follow_ups" not in completion

    @patch("chat.service.settings")
    async def test_compassionate_turn_never_surfaces_follow_ups(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")
        chat_service._check_content_safety = AsyncMock(
            return_value=_SafetyOutcome(
                allowed=True, compassionate=True, reason="ok", categories={}
            )
        )

        async def mock_stream(*args, **kwargs):
            for chunk in [
                "I hear you. ",
                "<!-- FOLLOWUPS: What can I do right now?|Who can I talk to? -->",
            ]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="I feel hopeless", include_search=False)
        chunks = [c async for c in chat_service.chat_stream(request)]
        completion = chunks[-1]

        assert "follow_ups" not in completion
        # The trailer was still stripped from the visible/authoritative text.
        assert "corrected_message" in completion
        assert "FOLLOWUPS" not in completion["corrected_message"]

    @patch("chat.service.settings")
    async def test_off_topic_reply_never_carries_follow_ups(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="OFF_TOPIC", model="m", provider="p")

        async def mock_stream(*args, **kwargs):
            for chunk in ["Let's talk about faith instead."]:
                yield chunk

        mock_llm.chat_stream = MagicMock(return_value=mock_stream())

        request = ChatRequest(message="who won the Super Bowl?", include_search=False)
        chunks = [c async for c in chat_service.chat_stream(request)]
        completion = chunks[-1]

        assert "follow_ups" not in completion


# ---------------------------------------------------------------------------
# 5. chat() — non-streaming path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestChatNonStreamingFollowUps:
    @patch("chat.service.settings")
    async def test_follow_ups_populated_and_trailer_stripped(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat = AsyncMock(
            side_effect=[
                LLMResponse(content="GENERAL", model="m", provider="p"),  # intent detection
                LLMResponse(
                    content=(
                        "God's love endures forever. "
                        "<!-- FOLLOWUPS: What does this mean for me?|"
                        "How can I pray about this? -->"
                    ),
                    model="m",
                    provider="p",
                ),
            ]
        )

        request = ChatRequest(message="tell me about God's love", include_search=False)
        response = await chat_service.chat(request)

        assert response.follow_ups == [
            "What does this mean for me?",
            "How can I pray about this?",
        ]
        assert "FOLLOWUPS" not in response.message
        assert response.message == "God's love endures forever."

    @patch("chat.service.settings")
    async def test_defaults_to_empty_list_when_disabled(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=False)
        mock_llm.chat = AsyncMock(
            side_effect=[
                LLMResponse(content="GENERAL", model="m", provider="p"),
                LLMResponse(content="God's love endures forever.", model="m", provider="p"),
            ]
        )

        request = ChatRequest(message="tell me about God's love", include_search=False)
        response = await chat_service.chat(request)

        assert response.follow_ups == []

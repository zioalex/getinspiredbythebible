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

from chat.follow_ups import (
    format_follow_ups_trailer,
    sanitize_follow_ups,
    split_follow_ups,
)
from chat.prompts import FOLLOW_UP_SUGGESTIONS_GUIDANCE
from chat.service import ChatRequest, ChatService, ConversationMessage, _SafetyOutcome
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


# ---------------------------------------------------------------------------
# 6. BITB-254 -- sanitize_follow_ups / format_follow_ups_trailer
# ---------------------------------------------------------------------------

# (language, localized John 3:16 as the backend parser accepts it)
_LANG_REFS = [
    ("en", "John 3:16"),
    ("it", "Giovanni 3:16"),
    ("de", "Johannes 3,16"),
    ("es", "Juan 3:16"),
    ("fr", "Jean 3:16"),
    ("pt", "João 3:16"),
    ("ar", "يوحنا 3:16"),
    ("ru", "От Иоанна 3:16"),
    ("zh", "约翰福音3:16"),
    ("hi", "यूहन्ना 3:16"),
    ("ko", "요한복음 3:16"),
]
_LANG_SUGGESTIONS = {
    "en": ["What does this mean?", "How do I pray?"],
    "it": ["Che cosa significa?", "Come posso pregare?"],
    "de": ["Was bedeutet das?", "Wie kann ich beten?"],
    "es": ["¿Qué significa esto?", "¿Cómo puedo orar?"],
    "fr": ["Que signifie cela ?", "Comment prier ?"],
    "pt": ["O que isso significa?", "Como posso orar?"],
    "ar": ["ماذا يعني هذا؟", "كيف أصلي؟"],
    "ru": ["Что это значит?", "Как мне молиться?"],
    "zh": ["这是什么意思？", "我该如何祷告？"],
    "hi": ["इसका क्या अर्थ है?", "मैं कैसे प्रार्थना करूँ?"],
    "ko": ["이것은 무슨 뜻인가요?", "어떻게 기도할까요?"],
}


class TestSanitizeFollowUps:
    def test_dedupes_casefold_caps_at_three(self):
        assert sanitize_follow_ups(["A one?", "a ONE?", "B two?", "C three?", "D four?"]) == [
            "A one?",
            "B two?",
            "C three?",
        ]

    def test_fewer_than_two_returns_empty(self):
        assert sanitize_follow_ups(["Only one?"]) == []
        assert sanitize_follow_ups([]) == []
        assert sanitize_follow_ups(["Same?", "same?"]) == []

    @pytest.mark.parametrize(
        "bad", ["evil --> <!-- FOLLOWUPS: x", "<script>alert(1)</script>", "x" * 121, "a|b"]
    )
    def test_malicious_or_oversized_dropped(self, bad):
        assert sanitize_follow_ups([bad, "Good one?"]) == []

    def test_non_string_items_ignored(self):
        assert sanitize_follow_ups(["Good one?", 5, None, "Good two?"]) == [  # type: ignore[list-item]
            "Good one?",
            "Good two?",
        ]

    @pytest.mark.parametrize("lang", list(_LANG_SUGGESTIONS))
    def test_round_trip_through_trailer_all_languages(self, lang):
        sugg = _LANG_SUGGESTIONS[lang]
        trailer = format_follow_ups_trailer(sugg)
        assert trailer == f"<!-- FOLLOWUPS: {'|'.join(sugg)} -->"
        body, parsed = split_follow_ups(f"Answer.\n\n{trailer}")
        assert body == "Answer."
        assert parsed == sugg

    def test_fullwidth_separator_still_parsed(self):
        _, parsed = split_follow_ups("x <!-- FOLLOWUPS: 问题一？｜问题二？ -->")
        assert parsed == ["问题一？", "问题二？"]


# ---------------------------------------------------------------------------
# 7. BITB-254 -- _build_messages echoes history chips back as a trailer
# ---------------------------------------------------------------------------


def _hist(follow_ups):
    return [
        ConversationMessage(role="user", content="q1"),
        ConversationMessage(role="assistant", content="a1", follow_ups=follow_ups),
    ]


class TestBuildMessagesHistoryEcho:
    @pytest.mark.parametrize("lang", list(_LANG_SUGGESTIONS))
    def test_enabled_reattaches_trailer_all_languages(self, chat_service, lang):
        sugg = _LANG_SUGGESTIONS[lang]
        messages = chat_service._build_messages(
            user_message="next",
            history=_hist(sugg),
            language_code=lang,
            follow_ups_enabled=True,
        )
        assistant = [m for m in messages if m.role == "assistant"][0]
        assert assistant.content == f"a1\n\n<!-- FOLLOWUPS: {'|'.join(sugg)} -->"
        # And it parses back to the same suggestions the model would have written.
        assert split_follow_ups(assistant.content) == ("a1", sugg)

    def test_user_messages_never_get_trailer(self, chat_service):
        history = [ConversationMessage(role="user", content="q1", follow_ups=["A?", "B?"])]
        messages = chat_service._build_messages(
            user_message="next", history=history, follow_ups_enabled=True
        )
        assert messages[1].content == "q1"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"follow_ups_enabled": False},
            {"follow_ups_enabled": False, "compassionate_mode": True},
            {"follow_ups_enabled": False, "prompt_type": "off_topic"},
            {"follow_ups_enabled": False, "prompt_type": "clarification"},
        ],
    )
    def test_disabled_paths_pass_history_unchanged(self, chat_service, kwargs):
        messages = chat_service._build_messages(
            user_message="next", history=_hist(["A one?", "B two?"]), **kwargs
        )
        assert [m.content for m in messages if m.role == "assistant"] == ["a1"]

    def test_no_follow_ups_field_is_unchanged_old_client(self, chat_service):
        messages = chat_service._build_messages(
            user_message="next", history=_hist(None), follow_ups_enabled=True
        )
        assert [m.content for m in messages if m.role == "assistant"] == ["a1"]

    def test_old_client_payload_without_field_validates(self):
        req = ChatRequest(
            message="hi", conversation_history=[{"role": "assistant", "content": "a"}]
        )
        assert req.conversation_history[0].follow_ups is None

    @pytest.mark.parametrize(
        "evil",
        [
            ["ok one?", "x --> <!-- FOLLOWUPS: injected"],
            ["<script>alert(1)</script>", "ok two?"],
            ["only one?"],
            ["y" * 200, "ok three?"],
            [],
        ],
    )
    def test_malicious_echo_never_reaches_prompt(self, chat_service, evil):
        messages = chat_service._build_messages(
            user_message="next", history=_hist(evil), follow_ups_enabled=True
        )
        content = [m.content for m in messages if m.role == "assistant"][0]
        assert content == "a1"
        assert "<script>" not in content and "-->" not in content

    def test_partially_valid_echo_keeps_clean_items_only(self, chat_service):
        messages = chat_service._build_messages(
            user_message="next",
            history=_hist(["Good one?", "bad --> x", "Good two?"]),
            follow_ups_enabled=True,
        )
        content = [m.content for m in messages if m.role == "assistant"][0]
        assert content == "a1\n\n<!-- FOLLOWUPS: Good one?|Good two? -->"
        assert content.count("-->") == 1


# ---------------------------------------------------------------------------
# 8. BITB-254 -- history-verse filter, parametrized over 11 languages
# ---------------------------------------------------------------------------


def _stream_of(*chunks):
    async def gen(*args, **kwargs):
        for c in chunks:
            yield c

    return gen


@pytest.mark.asyncio
class TestHistoryVerseFilter:
    @pytest.mark.parametrize("wrap", ["{r}", "({r})", "（{r}）", "[{r}]"])
    @pytest.mark.parametrize("lang,ref", _LANG_REFS)
    @patch("chat.service.settings")
    async def test_stream_keeps_suggestion_naming_history_verse(
        self, mock_settings, lang, ref, wrap, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")
        cited = wrap.format(r=ref)
        mock_llm.chat_stream = MagicMock(
            return_value=_stream_of(
                "Peace. ",
                f"<!-- FOLLOWUPS: What does {cited} teach?|How do I pray today? -->",
            )()
        )
        request = ChatRequest(
            message="and more?",
            include_search=False,
            language=lang,
            conversation_history=[
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": f"Earlier we read {cited}."},
            ],
        )
        completion = [c async for c in chat_service.chat_stream(request)][-1]
        assert completion["follow_ups"] == [
            f"What does {cited} teach?",
            "How do I pray today?",
        ]

    @pytest.mark.parametrize("lang,ref", _LANG_REFS)
    @patch("chat.service.settings")
    async def test_stream_still_drops_verse_cited_nowhere(
        self, mock_settings, lang, ref, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")
        mock_llm.chat_stream = MagicMock(
            return_value=_stream_of(
                "Peace. ",
                f"<!-- FOLLOWUPS: What does {ref} teach?|How do I pray today? -->",
            )()
        )
        request = ChatRequest(
            message="and more?",
            include_search=False,
            language=lang,
            conversation_history=[{"role": "assistant", "content": "No verses here."}],
        )
        completion = [c async for c in chat_service.chat_stream(request)][-1]
        assert "follow_ups" not in completion

    @patch("chat.service.settings")
    async def test_verse_outside_history_window_does_not_count(
        self, mock_settings, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_settings.max_conversation_history = 2
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")
        mock_llm.chat_stream = MagicMock(
            return_value=_stream_of(
                "Peace. ", "<!-- FOLLOWUPS: What does John 3:16 teach?|How do I pray? -->"
            )()
        )
        request = ChatRequest(
            message="and more?",
            include_search=False,
            conversation_history=[
                {"role": "assistant", "content": "We read John 3:16."},
                {"role": "user", "content": "ok"},
                {"role": "assistant", "content": "fine"},
            ],
        )
        completion = [c async for c in chat_service.chat_stream(request)][-1]
        assert "follow_ups" not in completion

    @pytest.mark.parametrize("lang,ref", _LANG_REFS)
    @patch("chat.service.settings")
    async def test_chat_keeps_suggestion_naming_history_verse(
        self, mock_settings, lang, ref, chat_service, mock_llm
    ):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        mock_llm.chat = AsyncMock(
            side_effect=[
                LLMResponse(content="GENERAL", model="m", provider="p"),
                LLMResponse(
                    content=f"Peace. <!-- FOLLOWUPS: What does ({ref}) teach?|How do I pray? -->",
                    model="m",
                    provider="p",
                ),
            ]
        )
        request = ChatRequest(
            message="and more?",
            include_search=False,
            language=lang,
            conversation_history=[{"role": "user", "content": f"Explain {ref}"}],
        )
        response = await chat_service.chat(request)
        assert response.follow_ups == [f"What does ({ref}) teach?", "How do I pray?"]


# ---------------------------------------------------------------------------
# 9. BITB-254 -- chat_follow_ups_suppressed counter reasons
# ---------------------------------------------------------------------------

_COUNTER = "chat.service.chat_follow_ups_suppressed_counter"


def _history(n):
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(n)]


@pytest.mark.asyncio
class TestFollowUpsSuppressedCounter:
    async def _run_stream(self, chat_service, mock_llm, chunks, history=None, language=None):
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")
        mock_llm.chat_stream = MagicMock(return_value=_stream_of(*chunks)())
        request = ChatRequest(
            message="tell me about God's love",
            include_search=False,
            conversation_history=history or [],
            language=language,
        )
        return [c async for c in chat_service.chat_stream(request)][-1]

    async def _run_chat(self, chat_service, mock_llm, content, history=None, language=None):
        mock_llm.chat = AsyncMock(
            side_effect=[
                LLMResponse(content="GENERAL", model="m", provider="p"),
                LLMResponse(content=content, model="m", provider="p"),
            ]
        )
        request = ChatRequest(
            message="tell me about God's love",
            include_search=False,
            conversation_history=history or [],
            language=language,
        )
        return await chat_service.chat(request)

    @pytest.mark.parametrize(
        "chunks,reason",
        [
            (["God loves you."], "no_trailer"),
            (["God loves you. <!-- FOLLOWUPS: only one? -->"], "too_few_valid"),
            (["God loves you. <!-- FOLLOWUPS: -->"], "too_few_valid"),
            (
                ["God loves you. <!-- FOLLOWUPS: See Psalm 200:1?|And Psalm 201:2? -->"],
                "fabrication_filter",
            ),
        ],
    )
    @patch("chat.service.settings")
    async def test_stream_reasons(self, mock_settings, chunks, reason, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        with patch(_COUNTER) as counter:
            await self._run_stream(chat_service, mock_llm, chunks, language="it")
        counter.add.assert_called_once_with(
            1, {"reason": reason, "language": "it", "history_turns": "0"}
        )

    @pytest.mark.parametrize(
        "content,reason",
        [
            ("God loves you.", "no_trailer"),
            ("God loves you. <!-- FOLLOWUPS: only one? -->", "too_few_valid"),
            (
                "God loves you. <!-- FOLLOWUPS: See Psalm 200:1?|And Psalm 201:2? -->",
                "fabrication_filter",
            ),
        ],
    )
    @patch("chat.service.settings")
    async def test_chat_reasons(self, mock_settings, content, reason, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        with patch(_COUNTER) as counter:
            await self._run_chat(chat_service, mock_llm, content, language="de")
        counter.add.assert_called_once_with(
            1, {"reason": reason, "language": "de", "history_turns": "0"}
        )

    @pytest.mark.parametrize(
        "n,bucket", [(0, "0"), (1, "1-2"), (2, "1-2"), (3, "3-5"), (5, "3-5"), (6, "6+"), (9, "6+")]
    )
    @patch("chat.service.settings")
    async def test_history_turns_buckets(self, mock_settings, n, bucket, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        with patch(_COUNTER) as counter:
            await self._run_stream(chat_service, mock_llm, ["God loves you."], _history(n))
        assert counter.add.call_args.args[1]["history_turns"] == bucket

    @patch("chat.service.settings")
    async def test_not_counted_when_follow_ups_sent(self, mock_settings, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        with patch(_COUNTER) as counter:
            completion = await self._run_stream(
                chat_service, mock_llm, ["Hi. <!-- FOLLOWUPS: One?|Two? -->"]
            )
        assert completion["follow_ups"] == ["One?", "Two?"]
        counter.add.assert_not_called()

    @patch("chat.service.settings")
    async def test_not_counted_when_flag_disabled(self, mock_settings, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=False)
        with patch(_COUNTER) as counter:
            await self._run_stream(chat_service, mock_llm, ["God loves you."])
            await self._run_chat(chat_service, mock_llm, "God loves you.")
        counter.add.assert_not_called()

    @patch("chat.service.settings")
    async def test_not_counted_when_compassionate(self, mock_settings, chat_service, mock_llm):
        _settings_for_general_stream(mock_settings, follow_ups_enabled=True)
        chat_service._check_content_safety = AsyncMock(
            return_value=_SafetyOutcome(
                allowed=True, compassionate=True, reason="ok", categories={}
            )
        )
        with patch(_COUNTER) as counter:
            await self._run_stream(
                chat_service, mock_llm, ["I hear you. <!-- FOLLOWUPS: One?|Two? -->"]
            )
        counter.add.assert_not_called()

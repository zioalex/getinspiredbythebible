"""BITB-177: surrounding-passage context and history carry-over for verse referents.

A direct lookup of "Luke 1:79" used to fetch only that verse, whose opening pronoun points back
to 1:78, and a reference-less follow-up ("are you sure?") was not re-grounded at all. These tests
drive the real parsers, prompt builders and ChatService orchestration through BOTH ``chat()`` and
``chat_stream()`` with only the search service and the LLM replaced (a small in-memory Bible).

Covers AC1-AC5 of the story: the window that is requested, that it reaches the system prompt but
never ``scripture_context``, history carry-over and its precedence, the flag, and fail-open.
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat import service as chat_service_module
from chat.prompts import (
    INTERPRETATION_INTEGRITY_GUIDANCE,
    build_search_context_prompt,
    get_scripture_unavailable_response,
    get_system_prompt,
    get_verse_lookup_prompt,
)
from chat.service import ChatRequest, ChatService, ConversationMessage
from config import settings
from golden_set.loader import filter_by_category, load_test_cases
from providers import LLMResponse
from scripture.search import SearchResults, VerseResult
from utils.language import resolve_translation
from utils.verse_parser import is_verse_lookup_request

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]

# "Who is spoken of in Luke 1:79?" in each supported language (German with a comma separator,
# Chinese/Korean without a space before the chapter, Arabic/Russian/Hindi in their own scripts).
LUKE_1_79 = {
    "en": "Who is spoken of in Luke 1:79?",
    "it": "Di chi si parla in Luca 1:79?",
    "de": "Von wem ist in Lukas 1,79 die Rede?",
    "es": "¿De quién se habla en Lucas 1:79?",
    "fr": "De qui parle-t-on dans Luc 1:79 ?",
    "pt": "De quem se fala em Lucas 1:79?",
    "ar": "عن من يتحدث لوقا 1:79؟",
    "ru": "О ком говорится в Лука 1:79?",
    "zh": "路加福音1:79说的是谁？",
    "hi": "लूका 1:79 में किसके बारे में कहा गया है?",
    "ko": "누가복음 1:79은 누구에 대해 말하고 있나요?",
}

# Real KJV / WEB wording of Luke 1:78, so version-faithfulness is visible in the prompt.
KJV_78 = "Through the tender mercy of our God; whereby the dayspring from on high hath visited us,"
WEB_78 = "because of the tender mercy of our God, whereby the dawn from on high will visit us,"
SPECIAL_TEXT = {("kjv", "Luke", 1, 78): KJV_78, ("web", "Luke", 1, 78): WEB_78}


def verse_text(translation: str, book: str, chapter: int, verse: int) -> str:
    return SPECIAL_TEXT.get(
        (translation, book, chapter, verse), f"[{translation}] {book} {chapter}:{verse}"
    )


CHAPTER_LENGTH = {
    ("Luke", 1): 80,
    ("Luke", 2): 52,
    ("John", 1): 51,
    ("John", 3): 36,
    ("Psalms", 23): 6,
    ("Genesis", 1): 31,
    ("Ruth", 1): 22,
}


@pytest.fixture(autouse=True)
def pipeline_settings(monkeypatch):
    """Only retrieval and prompt assembly under test: no safety service, intent LLM call,
    clarification, follow-ups, expansion, hybrid search or boosting."""
    values = {
        "content_safety_enabled": False,
        "content_filter_intent_detection": False,
        "chat_clarification_enabled": False,
        "chat_follow_ups_enabled": False,
        "query_expansion_enabled": False,
        "hybrid_search_enabled": False,
        "topic_boosting_enabled": False,
        "passage_context_enabled": True,
        "passage_context_verses_before": 4,
        "passage_context_verses_after": 2,
        "passage_context_max_references": 2,
        "passage_context_history_lookback": 4,
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


@pytest.fixture(params=["chat", "stream"])
def mode(request):
    return request.param


class FakeBible:
    """In-memory stand-in for ScriptureSearchService.

    Every verse of a known chapter exists in every translation, with text
    ``"[<translation>] <Book> <ch>:<v>"`` (except the real KJV/WEB wording of Luke 1:78), so a
    test can tell which translation a verse in the prompt came from. Semantic search finds
    nothing, which isolates the direct lookup and the passage context.
    """

    def __init__(self):
        self.range_calls: list[tuple] = []
        self.verse_calls: list[tuple] = []
        self.search_calls = 0
        self.range_error: Exception | None = None
        self.empty_ranges = False
        self.get_verse = AsyncMock(side_effect=self._get_verse)
        self.get_verse_range = AsyncMock(side_effect=self._get_verse_range)
        self.search = AsyncMock(side_effect=self._search)

    @staticmethod
    def _verse(translation, book, chapter, verse) -> VerseResult:
        return VerseResult(
            reference=f"{book} {chapter}:{verse}",
            text=verse_text(translation, book, chapter, verse),
            book=book,
            chapter=chapter,
            verse=verse,
            translation=translation,
        )

    async def _get_verse(self, book, chapter, verse, translation=None):
        self.verse_calls.append((book, chapter, verse, translation))
        if verse > CHAPTER_LENGTH.get((book, chapter), 0):
            return None
        return self._verse(translation, book, chapter, verse)

    async def _get_verse_range(self, book, chapter, start_verse, end_verse, translation=None):
        self.range_calls.append((book, chapter, start_verse, end_verse, translation))
        if self.range_error:
            raise self.range_error
        if self.empty_ranges:
            return []
        last = CHAPTER_LENGTH.get((book, chapter), 0)
        return [
            self._verse(translation, book, chapter, v)
            for v in range(start_verse, min(end_verse, last) + 1)
        ]

    async def _search(self, **kwargs):
        self.search_calls += 1
        return SearchResults(query=kwargs.get("query", ""), verses=[], passages=[])


@dataclass
class Outcome:
    system: str  # the system message the LLM received
    context: dict | None  # scripture_context as the client gets it
    answer: str
    llm_called: bool

    @property
    def context_references(self) -> list[str]:
        return [v["reference"] for v in (self.context or {}).get("verses", [])]


class Harness:
    """A ChatService wired to FakeBible and a recording LLM, driven through either entry point."""

    def __init__(self):
        self.bible = FakeBible()
        self.llm = AsyncMock()
        self.llm.provider_name = "test-provider"
        self.messages = None
        self.llm.chat = AsyncMock(side_effect=self._chat)
        self.llm.chat_stream = self._chat_stream
        self.service = ChatService(AsyncMock(), self.llm, AsyncMock())
        self.service.search_service = self.bible

    async def _chat(self, **kwargs):
        self.messages = kwargs["messages"]
        return LLMResponse(content="An answer.", provider="test", model="test-model")

    async def _chat_stream(self, **kwargs):
        self.messages = kwargs["messages"]
        for token in ("An ", "answer."):
            yield token

    async def run(self, mode: str, message: str, history=(), **request_fields) -> Outcome:
        request = ChatRequest(
            message=message,
            conversation_history=[ConversationMessage(**m) for m in history],
            **request_fields,
        )
        if mode == "chat":
            response = await self.service.chat(request)
            context = (
                response.scripture_context.model_dump() if response.scripture_context else None
            )
            answer = response.message
        else:
            chunks = [c async for c in self.service.chat_stream(request)]
            metadata = next(c for c in chunks if c["type"] == "metadata")
            context = metadata["scripture_context"]
            answer = "".join(c["content"] for c in chunks if c["type"] == "content")
        system = next((m.content for m in self.messages or [] if m.role == "system"), "")
        return Outcome(system, context, answer, llm_called=self.messages is not None)


@pytest.fixture
def harness():
    return Harness()


def _surrounding(system: str) -> str:
    """The Surrounding Passage block(s) of a system prompt ('' when absent)."""
    start = system.find("\n### Surrounding Passage")
    if start < 0:
        return ""
    end = system.index("\n\nUse these verses to support your response", start)
    return system[start:end]


def _without_surrounding(system: str) -> str:
    block = _surrounding(system)
    # the block is joined to the preceding verses with one extra newline
    return system.replace("\n" + block, "") if block else system


def _passage_of(call_args: tuple) -> tuple:
    book, chapter, start, end, _ = call_args
    return book, chapter, start, end


def _history(*pairs):
    """('user', text) / ('assistant', text) pairs -> history dicts."""
    return [{"role": role, "content": text} for role, text in pairs]


# ==================== AC1: the window is requested and reaches the prompt ====================


class TestPassageContextRequest:
    @pytest.mark.parametrize("language", LANGUAGES)
    async def test_core_case_requests_1_75_to_81_and_prompt_carries_1_78(
        self, harness, mode, language
    ):
        translation = resolve_translation(None, language)
        out = await harness.run(mode, LUKE_1_79[language], language=language)

        assert [c for c in harness.bible.range_calls] == [("Luke", 1, 75, 81, translation)]
        block = _surrounding(out.system)
        assert "### Surrounding Passage — Luke 1:79" in block
        # the verse the pronoun points back to is in the prompt, in the resolved translation
        assert f'**Luke 1:78**: "{verse_text(translation, "Luke", 1, 78)}"' in block
        # the verse under discussion, and only it, is marked
        assert f'**Luke 1:79** [VERSE UNDER DISCUSSION]: "[{translation}] Luke 1:79"' in block
        assert block.count("[VERSE UNDER DISCUSSION]") == 1
        # 4 before and up to 2 after (the chapter has 80 verses, so 81 does not exist)
        for verse in (75, 76, 77, 78, 79, 80):
            assert f"**Luke 1:{verse}**" in block
        assert "**Luke 1:81**" not in block and "**Luke 1:74**" not in block
        # the guidance and the block are both in the one system message the model sees
        assert INTERPRETATION_INTEGRITY_GUIDANCE in out.system
        assert out.system.index("## Scripture Context") < out.system.index(
            "### Surrounding Passage"
        )

    @pytest.mark.parametrize(
        "language,message",
        [
            ("en", "Who is meant here (Luke 1:79)?"),
            ("it", "Chi è «lui» [Luca 1:79]?"),
            ("de", "Wer ist „er“ in Lukas 1,79?"),
            ("ru", "Что значит (Лука 1:79)?"),
            ("zh", "（路加福音 1:79）说的是谁？"),
            ("zh", "《路加福音 1:79》说的是谁？"),
            ("ko", "누가복음 1:79 은 누구를 말하나요?"),
            ("ar", "عن من يتحدث لوقا ١:٧٩؟"),
            ("hi", "लूका १:७९ में किसके बारे में कहा गया है?"),
            pytest.param(
                "zh",
                "「路加福音1：79」说的是谁？",
                marks=pytest.mark.xfail(
                    strict=True,
                    reason="known gap: the backend verse parser does not accept the fullwidth "
                    "colon (U+FF1A) between chapter and verse; no reference means no passage "
                    "context. Fix in all three parsers, then drop this xfail.",
                ),
            ),
        ],
    )
    async def test_reference_format_variants_get_the_same_window(
        self, harness, mode, language, message
    ):
        out = await harness.run(mode, message, language=language)
        assert [_passage_of(c) for c in harness.bible.range_calls] == [("Luke", 1, 75, 81)]
        assert "**Luke 1:78**" in _surrounding(out.system)

    async def test_range_reference_widens_around_the_whole_range(self, harness, mode):
        out = await harness.run(mode, "Explain Luke 1:76-79", language="en")
        # one range call for the direct lookup (76-79) and one for the passage window (72-81)
        assert [_passage_of(c) for c in harness.bible.range_calls] == [
            ("Luke", 1, 76, 79),
            ("Luke", 1, 72, 81),
        ]
        block = _surrounding(out.system)
        assert "### Surrounding Passage — Luke 1:76-79" in block
        assert block.count("[VERSE UNDER DISCUSSION]") == 4
        for verse in (76, 77, 78, 79):
            assert f"**Luke 1:{verse}** [VERSE UNDER DISCUSSION]" in block
        assert "**Luke 1:75**: " in block and "**Luke 1:80**: " in block

    async def test_en_dash_range_is_a_range_too(self, harness, mode):
        await harness.run(mode, "Lukas 1:76–79 bitte", language="de")
        assert ("Luke", 1, 72, 81) in [_passage_of(c) for c in harness.bible.range_calls]

    @pytest.mark.parametrize(
        "verse,expected",
        [(1, (1, 3)), (2, (1, 4)), (4, (1, 6)), (5, (1, 7)), (6, (2, 8))],
    )
    async def test_window_is_clamped_at_verse_one(self, harness, mode, verse, expected):
        out = await harness.run(mode, f"What does Luke 1:{verse} mean?", language="en")
        passage = [_passage_of(c) for c in harness.bible.range_calls]
        assert passage == [("Luke", 1) + expected]
        assert "Luke 0:" not in out.system and "Luke 1:0" not in out.system
        assert f"**Luke 1:{verse}** [VERSE UNDER DISCUSSION]" in _surrounding(out.system)

    async def test_window_follows_the_settings(self, harness, mode, monkeypatch):
        monkeypatch.setattr(settings, "passage_context_verses_before", 2)
        monkeypatch.setattr(settings, "passage_context_verses_after", 1)
        await harness.run(mode, LUKE_1_79["en"], language="en")
        assert [_passage_of(c) for c in harness.bible.range_calls] == [("Luke", 1, 77, 80)]

    async def test_no_window_beyond_the_chapter_end(self, harness, mode):
        out = await harness.run(mode, "What does Luke 1:80 say?", language="en")
        assert [_passage_of(c) for c in harness.bible.range_calls] == [("Luke", 1, 76, 82)]
        assert "**Luke 1:82**" not in out.system  # nonexistent verses are simply not returned

    async def test_include_search_false_fetches_nothing(self, harness, mode):
        out = await harness.run(mode, LUKE_1_79["en"], language="en", include_search=False)
        assert harness.bible.range_calls == []
        assert "### Surrounding Passage" not in out.system


# ==================== Version faithfulness ====================


class TestTranslationFaithfulness:
    @pytest.mark.parametrize(
        "translation,expected,other",
        [("kjv", KJV_78, WEB_78), ("web", WEB_78, KJV_78)],
    )
    async def test_surrounding_verses_use_the_selected_translation(
        self, harness, mode, translation, expected, other
    ):
        out = await harness.run(
            mode, LUKE_1_79["en"], language="en", preferred_translation=translation
        )
        assert harness.bible.range_calls == [("Luke", 1, 75, 81, translation)]
        block = _surrounding(out.system)
        assert expected in block
        assert other not in out.system

    async def test_translation_follows_the_language_default_without_a_preference(
        self, harness, mode
    ):
        await harness.run(mode, LUKE_1_79["de"], language="de")
        assert harness.bible.range_calls[0][-1] == resolve_translation(None, "de") == "luther1912"

    async def test_carried_over_context_uses_the_selected_translation_too(self, harness, mode):
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "It is John."))
        out = await harness.run(
            mode, "Are you sure?", history, language="en", preferred_translation="kjv"
        )
        assert harness.bible.range_calls == [("Luke", 1, 75, 81, "kjv")]
        assert KJV_78 in out.system and WEB_78 not in out.system


# ==================== AC2: scripture_context is untouched ====================


class TestScriptureContextUnchanged:
    @pytest.mark.parametrize("language", LANGUAGES)
    async def test_returned_context_is_identical_with_the_flag_on_and_off(
        self, mode, monkeypatch, language
    ):
        on = await Harness().run(mode, LUKE_1_79[language], language=language)

        monkeypatch.setattr(settings, "passage_context_enabled", False)
        off_harness = Harness()
        off = await off_harness.run(mode, LUKE_1_79[language], language=language)

        assert off_harness.bible.range_calls == []
        assert on.context == off.context
        assert on.context_references == ["Luke 1:79"]

    async def test_surrounding_verses_never_appear_in_the_returned_context(self, harness, mode):
        out = await harness.run(mode, "Explain Luke 1:76-79", language="en")
        assert sorted(out.context_references) == [f"Luke 1:{v}" for v in (76, 77, 78, 79)]
        assert "Luke 1:75" in out.system and "Luke 1:80" in out.system
        assert "Luke 1:75" not in out.context_references

    async def test_carried_over_verses_do_not_enter_the_returned_context(self, harness, mode):
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "It is John."))
        out = await harness.run(mode, "Are you sure?", history, language="en")
        assert "### Surrounding Passage" in out.system
        assert out.context is not None and out.context_references == []
        assert out.context["passages"] == []


# ==================== AC4: flag off ====================


class TestFlagOff:
    @pytest.mark.parametrize("language", ["en", "de", "zh"])
    async def test_flag_off_system_message_is_search_context_plus_prompt(
        self, mode, monkeypatch, language
    ):
        monkeypatch.setattr(settings, "passage_context_enabled", False)
        harness = Harness()
        message = LUKE_1_79[language]
        out = await harness.run(mode, message, language=language)

        assert harness.bible.range_calls == []
        assert "### Surrounding Passage" not in out.system
        builder = get_verse_lookup_prompt if is_verse_lookup_request(message) else get_system_prompt
        expected = (
            build_search_context_prompt(
                {"verses": out.context["verses"], "passages": out.context["passages"]}
            )
            + "\n"
            + builder(language)
        )
        assert out.system == expected

    @pytest.mark.parametrize("language", ["en", "it", "ko"])
    async def test_flag_on_differs_from_flag_off_only_by_the_block(
        self, mode, monkeypatch, language
    ):
        on = await Harness().run(mode, LUKE_1_79[language], language=language)
        monkeypatch.setattr(settings, "passage_context_enabled", False)
        off = await Harness().run(mode, LUKE_1_79[language], language=language)

        assert "### Surrounding Passage" in on.system
        assert _without_surrounding(on.system) == off.system

    async def test_flag_off_disables_carry_over(self, harness, mode, monkeypatch):
        monkeypatch.setattr(settings, "passage_context_enabled", False)
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "It is John."))
        out = await harness.run(mode, "Are you sure?", history, language="en")
        assert harness.bible.range_calls == []
        assert "### Surrounding Passage" not in out.system


# ==================== AC3: re-grounding follow-up turns ====================


def _localized_pushback_cases():
    """Luke 1:79 'user is right' pushbacks (history + reference-less challenge), all 11 languages."""
    cases = filter_by_category(load_test_cases(), "interpretation")
    picked = {
        c.input.language: c
        for c in cases
        if "pushback-user-right" in c.tags and "luke-1-79" in c.tags
    }
    assert set(picked) == set(LANGUAGES)
    return [pytest.param(lang, picked[lang], id=lang) for lang in LANGUAGES]


class TestHistoryCarryOver:
    @pytest.mark.parametrize("language,case", _localized_pushback_cases())
    async def test_reference_less_challenge_regrounds_the_earlier_passage(
        self, harness, mode, language, case
    ):
        translation = resolve_translation(None, language)
        out = await harness.run(
            mode,
            case.input.message,
            case.input.conversation_history,
            language=language,
        )

        # the challenge itself names no verse: only history can have supplied Luke 1:79
        assert harness.bible.verse_calls == []
        assert harness.bible.range_calls == [("Luke", 1, 75, 81, translation)]
        block = _surrounding(out.system)
        assert "### Surrounding Passage — Luke 1:79" in block
        assert "passage discussed earlier in the conversation" in block
        assert f'**Luke 1:78**: "{verse_text(translation, "Luke", 1, 78)}"' in block
        assert "[VERSE UNDER DISCUSSION]" in block

    async def test_own_reference_wins_and_history_is_not_consulted(self, harness, mode):
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "Luke 1:79 is about John."))
        out = await harness.run(mode, "And what does John 3:16 say?", history, language="en")
        assert [_passage_of(c) for c in harness.bible.range_calls] == [("John", 3, 12, 18)]
        block = _surrounding(out.system)
        assert "### Surrounding Passage — John 3:16" in block
        assert "Luke" not in block
        assert "discussed earlier in the conversation" not in block

    async def test_most_recent_user_message_with_a_reference_wins(self, harness, mode):
        history = _history(
            ("user", "Tell me about Luke 1:79"),
            ("assistant", "It speaks of light."),
            ("user", "And John 3:16?"),
            ("assistant", "It speaks of love."),
        )
        await harness.run(mode, "Are you sure?", history, language="en")
        passages = [_passage_of(c) for c in harness.bible.range_calls]
        assert passages == [("John", 3, 12, 18)]

    async def test_user_reference_comes_before_assistant_reference(self, harness, mode):
        history = _history(
            ("user", "Explain Genesis 1:1"),
            ("assistant", "Compare John 1:8 as well."),
        )
        out = await harness.run(mode, "Are you sure?", history, language="en")
        assert [_passage_of(c) for c in harness.bible.range_calls] == [
            ("Genesis", 1, 1, 3),
            ("John", 1, 4, 10),
        ]
        block = _surrounding(out.system)
        assert block.index("Genesis 1:1\n") < block.index("John 1:8\n")

    async def test_assistant_reference_alone_is_enough(self, harness, mode):
        history = _history(("user", "Tell me something"), ("assistant", "See Genesis 1:1."))
        await harness.run(mode, "Why?", history, language="en")
        assert [_passage_of(c) for c in harness.bible.range_calls] == [("Genesis", 1, 1, 3)]

    async def test_same_reference_in_user_and_assistant_is_fetched_once(self, harness, mode):
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "Luke 1:79 is about John."))
        await harness.run(mode, "Are you sure?", history, language="en")
        assert len(harness.bible.range_calls) == 1

    async def test_max_references_caps_the_expanded_references(self, harness, mode, monkeypatch):
        cited = "See Luke 1:78, John 1:8 and Genesis 1:1 for this."
        history = _history(("user", "Tell me something"), ("assistant", cited))
        await harness.run(mode, "Why?", history, language="en")
        assert [_passage_of(c)[:2] for c in harness.bible.range_calls] == [("Luke", 1), ("John", 1)]

        capped = Harness()
        monkeypatch.setattr(settings, "passage_context_max_references", 1)
        out = await capped.run(mode, "Why?", history, language="en")
        assert [_passage_of(c) for c in capped.bible.range_calls] == [("Luke", 1, 74, 80)]
        assert out.system.count("### Surrounding Passage") == 1

    async def test_lookback_limits_how_far_back_history_is_scanned(
        self, harness, mode, monkeypatch
    ):
        history = _history(
            ("user", LUKE_1_79["en"]),
            ("assistant", "It speaks of light."),
            ("user", "Interesting."),
            ("assistant", "Anything else?"),
        )
        monkeypatch.setattr(settings, "passage_context_history_lookback", 2)
        out = await harness.run(mode, "Are you sure?", history, language="en")
        assert harness.bible.range_calls == []
        assert "### Surrounding Passage" not in out.system

        wide = Harness()
        monkeypatch.setattr(settings, "passage_context_history_lookback", 4)
        await wide.run(mode, "Are you sure?", history, language="en")
        assert len(wide.bible.range_calls) == 1

    async def test_lookback_zero_disables_carry_over_but_not_the_direct_window(
        self, harness, mode, monkeypatch
    ):
        monkeypatch.setattr(settings, "passage_context_history_lookback", 0)
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "It is John."))
        out = await harness.run(mode, "Are you sure?", history, language="en")
        assert harness.bible.range_calls == []
        assert "### Surrounding Passage" not in out.system

        direct = Harness()
        await direct.run(mode, LUKE_1_79["en"], history, language="en")
        assert len(direct.bible.range_calls) == 1

    async def test_no_history_and_no_reference_fetches_nothing(self, harness, mode):
        out = await harness.run(mode, "I feel anxious today", language="en")
        assert harness.bible.range_calls == []
        assert "### Surrounding Passage" not in out.system

    async def test_fail_closed_guard_still_applies_to_a_carried_over_follow_up(
        self, harness, mode, monkeypatch
    ):
        """FR2.4: carried-over verses are prompt-only. With nothing in scripture_context a
        scripture-seeking follow-up still gets the honest 'try again' message, not an answer."""
        monkeypatch.setattr(settings, "content_filter_intent_detection", True)
        harness.service._detect_intent = AsyncMock(return_value="CURIOSITY")
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "It is John."))

        out = await harness.run(mode, "Are you sure?", history, language="en")

        assert harness.bible.range_calls == [("Luke", 1, 75, 81, "web")]  # it was fetched...
        assert not out.llm_called  # ...but the guard fired before any generation
        assert out.answer == get_scripture_unavailable_response("en")


# ==================== AC5: fail open ====================


class TestFailOpen:
    @pytest.fixture
    def error_counter(self, monkeypatch):
        counter = MagicMock()
        monkeypatch.setattr(chat_service_module, "scripture_pipeline_errors_counter", counter)
        return counter

    async def test_range_fetch_error_still_yields_an_answer_with_the_normal_context(
        self, harness, mode, error_counter
    ):
        harness.bible.range_error = RuntimeError("db down")
        out = await harness.run(mode, LUKE_1_79["en"], language="en")

        assert out.answer == "An answer."
        assert "### Surrounding Passage" not in out.system
        assert '**Luke 1:79**: "[web] Luke 1:79"' in out.system  # the direct verse is still there
        assert out.context_references == ["Luke 1:79"]
        error_counter.add.assert_called_once_with(
            1, {"stage": "passage_context", "error_type": "RuntimeError"}
        )

    async def test_carry_over_fetch_error_is_equally_fail_open(self, harness, mode, error_counter):
        harness.bible.range_error = ConnectionError("reset")
        history = _history(("user", LUKE_1_79["en"]), ("assistant", "It is John."))
        out = await harness.run(mode, "Are you sure?", history, language="en")
        assert out.answer == "An answer."
        assert "### Surrounding Passage" not in out.system
        error_counter.add.assert_called_once_with(
            1, {"stage": "passage_context", "error_type": "ConnectionError"}
        )

    async def test_history_scan_error_is_fail_open(self, harness, mode, error_counter, monkeypatch):
        def boom(history):
            raise ValueError("bad history")

        monkeypatch.setattr(harness.service, "_history_references", boom)
        out = await harness.run(
            mode,
            "Are you sure?",
            _history(("user", "Luke 1:79"), ("assistant", "x")),
            language="en",
        )
        assert out.answer == "An answer."
        assert error_counter.add.call_args.args[1]["stage"] == "passage_context"

    async def test_an_empty_window_adds_no_block_and_is_not_an_error(
        self, harness, mode, error_counter
    ):
        harness.bible.empty_ranges = True
        out = await harness.run(mode, LUKE_1_79["en"], language="en")
        assert out.answer == "An answer."
        assert "### Surrounding Passage" not in out.system
        error_counter.add.assert_not_called()

    async def test_a_failing_search_is_not_masked_by_the_passage_context(
        self, harness, mode, error_counter
    ):
        """The passage fetch sits after the main search: a failed search degrades exactly as before."""
        harness.bible.search = AsyncMock(side_effect=RuntimeError("search down"))
        out = await harness.run(mode, "Tell me about hope", language="en")
        assert harness.bible.range_calls == []
        assert out.context is None
        stages = [c.args[1]["stage"] for c in error_counter.add.call_args_list]
        assert stages == ["search"]


# ==================== History reference extraction (unit) ====================

_CITATIONS = {
    "en": "Luke 1:79",
    "it": "Luca 1:79",
    "de": "Lukas 1,79",
    "es": "Lucas 1:79",
    "fr": "Luc 1:79",
    "pt": "Lucas 1:79",
    "ar": "لوقا 1:79",
    "ru": "Лука 1:79",
    "zh": "路加福音1:79",
    "hi": "लूका 1:79",
    "ko": "누가복음 1:79",
}
_WRAPPERS = [("{}", "plain"), ("({})", "parens"), ("[{}]", "brackets"), ("（{}）", "fullwidth")]


class TestHistoryReferences:
    @pytest.fixture
    def service(self):
        return ChatService(AsyncMock(), AsyncMock(), AsyncMock())

    @staticmethod
    def _msgs(*pairs):
        return [ConversationMessage(role=r, content=c) for r, c in pairs]

    @pytest.mark.parametrize("wrapper,_", _WRAPPERS, ids=[w for _, w in _WRAPPERS])
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_assistant_citation_in_every_language_and_wrapper(self, service, language, wrapper, _):
        cited = wrapper.format(_CITATIONS[language])
        history = self._msgs(("user", "Hello"), ("assistant", f"... {cited} ..."))
        assert [str(r) for r in service._history_references(history)] == ["Luke 1:79"]

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_user_question_in_every_language(self, service, language):
        history = self._msgs(("user", LUKE_1_79[language]), ("assistant", "No verse here."))
        assert [str(r) for r in service._history_references(history)] == ["Luke 1:79"]

    def test_range_in_history_keeps_its_range(self, service):
        history = self._msgs(("user", "Explain Luke 1:76-79"), ("assistant", "ok"))
        refs = service._history_references(history)
        assert (refs[0].verse_start, refs[0].verse_end) == (76, 79)

    def test_returns_nothing_for_empty_history_or_no_reference(self, service):
        assert service._history_references([]) == []
        assert service._history_references(self._msgs(("user", "Hi"), ("assistant", "Hello"))) == []

    def test_lookback_zero_and_negative_disable(self, service, monkeypatch):
        history = self._msgs(("user", "Luke 1:79"), ("assistant", "ok"))
        for lookback in (0, -1):
            monkeypatch.setattr(settings, "passage_context_history_lookback", lookback)
            assert service._history_references(history) == []

    def test_only_the_last_lookback_messages_are_scanned(self, service, monkeypatch):
        history = self._msgs(
            ("user", "Luke 1:79"), ("assistant", "a"), ("user", "b"), ("assistant", "c")
        )
        monkeypatch.setattr(settings, "passage_context_history_lookback", 3)
        assert service._history_references(history) == []
        monkeypatch.setattr(settings, "passage_context_history_lookback", 4)
        assert [str(r) for r in service._history_references(history)] == ["Luke 1:79"]


# ==================== _fetch_passage_context (unit) ====================


class TestFetchPassageContext:
    @pytest.fixture
    def service(self):
        svc = ChatService(AsyncMock(), AsyncMock(), AsyncMock())
        svc.search_service = FakeBible()
        return svc

    @staticmethod
    def _ref(text):
        from utils.verse_parser import extract_references

        return extract_references(text)[0][0]

    async def test_marks_focus_verses_and_shapes_the_entry(self, service):
        entries = await service._fetch_passage_context([self._ref("Luke 1:76-77")], "kjv")
        assert len(entries) == 1
        entry = entries[0]
        assert (entry["focus"], entry["carried_over"]) == ("Luke 1:76-77", False)
        focus = [v["reference"] for v in entry["verses"] if v["is_focus"]]
        assert focus == ["Luke 1:76", "Luke 1:77"]
        assert [v["reference"] for v in entry["verses"]][0] == "Luke 1:72"
        assert [v["reference"] for v in entry["verses"]][-1] == "Luke 1:79"

    async def test_carried_over_flag_is_passed_through(self, service):
        entries = await service._fetch_passage_context(
            [self._ref("Luke 1:79")], "kjv", carried_over=True
        )
        assert entries[0]["carried_over"] is True

    async def test_duplicate_references_are_fetched_once(self, service):
        ref = self._ref("Luke 1:79")
        entries = await service._fetch_passage_context([ref, ref], "kjv")
        assert len(entries) == 1 and len(service.search_service.range_calls) == 1

    async def test_cap_bounds_the_range_queries_even_when_windows_come_back_empty(
        self, service, monkeypatch
    ):
        monkeypatch.setattr(settings, "passage_context_max_references", 1)
        missing = self._ref("Obadiah 1:3")  # unknown chapter in FakeBible -> empty window
        present = self._ref("Luke 1:79")
        entries = await service._fetch_passage_context([missing, present], "kjv")
        assert entries == []
        assert len(service.search_service.range_calls) == 1  # never a second query

    async def test_empty_windows_are_skipped_within_the_cap(self, service):
        entries = await service._fetch_passage_context(
            [self._ref("Obadiah 1:3"), self._ref("Luke 1:79")], "kjv"
        )
        assert [e["focus"] for e in entries] == ["Luke 1:79"]

    @pytest.mark.parametrize("cap", [0, -1])
    async def test_non_positive_cap_fetches_nothing(self, service, monkeypatch, cap):
        monkeypatch.setattr(settings, "passage_context_max_references", cap)
        refs = [self._ref("Luke 1:79"), self._ref("John 3:16")]
        assert await service._fetch_passage_context(refs, "kjv") == []
        assert service.search_service.range_calls == []

    async def test_an_absurd_range_is_bounded(self, service):
        ref = self._ref("Genesis 1:1-31")
        await service._fetch_passage_context([ref], "kjv")
        _, _, start, end, _ = service.search_service.range_calls[0]
        span = chat_service_module.MAX_RANGE_SPAN
        assert (start, end) == (1, min(31, span) + 2)
        assert (
            span < 31 or end == 33
        )  # (documents the bound if MAX_RANGE_SPAN ever exceeds the range)


# ==================== Settings ====================


class TestSettingsDefaults:
    def test_defaults_match_the_story(self):
        from config import Settings

        fields = Settings.model_fields
        assert fields["passage_context_enabled"].default is True
        assert fields["passage_context_verses_before"].default == 4
        assert fields["passage_context_verses_after"].default == 2
        assert fields["passage_context_max_references"].default == 2
        assert fields["passage_context_history_lookback"].default == 4

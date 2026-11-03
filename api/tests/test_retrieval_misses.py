"""BITB-256: privacy-safe retrieval-miss capture.

Integration tests go through ``chat()`` / ``chat_stream()`` with a mocked
``search_service`` (per AGENTS.md: pure-function tests alone hide parse -> resolve ->
classify integration bugs), then unit tests cover the sanitizer (the privacy boundary),
the classifier, signature/upsert persistence and purge.
"""

import asyncio
import json
import logging
import sys
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import feedback.retrieval_misses as rm
from chat.service import ChatRequest, ChatService, _SafetyOutcome
from chat.topics import SUPPORTED_TOPIC_LANGUAGES, TOPIC_KEYWORD_MAP
from config import settings
from providers import LLMResponse
from scripture.search import PassageResult, SearchResults, VerseResult
from utils.verse_parser import VerseReference

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
PATHS = ["chat", "stream"]

# A native "I feel anxious about tomorrow" per language. Topic detection is keyword based
# and only covers SUPPORTED_TOPIC_LANGUAGES; ru/zh/hi/ko legitimately yield no topics.
ANXIOUS = {
    "en": "I feel anxious about tomorrow",
    "it": "Mi sento ansioso per domani",
    "de": "Ich bin ängstlich wegen morgen",
    "es": "Estoy ansioso por mañana",
    "fr": "Je suis anxieux à propos de demain",
    "pt": "Estou ansioso com o amanhã",
    "ar": "أشعر بقلق شديد بشأن الغد",
    "ru": "Я очень тревожусь о завтрашнем дне",
    "zh": "我对明天感到焦虑",
    "hi": "मुझे कल की चिंता है",
    "ko": "내일이 걱정돼요",
}

CLEAN = _SafetyOutcome(allowed=True, compassionate=False, reason="clean", categories={})
COMPASSIONATE = _SafetyOutcome(
    allowed=True,
    compassionate=True,
    reason="possible_help_seeking (fallback)",
    categories={},
    is_help_seeking=True,
)
BLOCKED = _SafetyOutcome(
    allowed=False, compassionate=False, reason="keyword_violation", categories={}
)

SENTINEL = "ZQX-SENTINEL-7f3a"
NAME = "Bartholomew Quillfeather"


def _verse(book="John", chapter=3, verse=16, similarity=0.9):
    return VerseResult(
        reference=f"{book} {chapter}:{verse}",
        text="canonical text",
        book=book,
        chapter=chapter,
        verse=verse,
        translation="kjv",
        similarity=similarity,
    )


def _ctx(*verses, passages=()):
    return SearchResults(query="q", verses=list(verses), passages=list(passages))


def _service(reply="God is near to the brokenhearted.", expansion=None):
    llm = AsyncMock()
    llm.provider_name = "test-provider"

    async def _chat(messages, **_kwargs):
        text = messages[0].content if messages else ""
        if "helping expand a search query" in text and expansion is not None:
            return LLMResponse(content=expansion, provider="t", model="m")
        return LLMResponse(content=reply, provider="t", model="m")

    llm.chat = AsyncMock(side_effect=_chat)

    async def _stream(messages, **_kwargs):
        yield reply

    llm.chat_stream = _stream
    embedding = AsyncMock()
    embedding.embed = AsyncMock(return_value=MagicMock(embedding=[0.1, 0.2, 0.3]))
    service = ChatService(AsyncMock(), llm, embedding)
    service.search_service = AsyncMock()
    return service


def _set_search(service, ctx=None, error=None):
    mock = AsyncMock(return_value=ctx, side_effect=error)
    service.search_service.search_hybrid = mock
    service.search_service.search = mock
    return mock


async def _run(
    path,
    service,
    *,
    message="I feel anxious about tomorrow",
    language="en",
    translation="kjv",
    intent="COMFORT",
    safety=CLEAN,
    capture=True,
    wants_clarification=False,
    **request_kwargs,
):
    """Drive one turn through chat() or chat_stream(); return (output, scheduled-calls)."""
    scheduled = MagicMock()
    request = ChatRequest(message=message, language=language, **request_kwargs)
    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch("chat.service.schedule_retrieval_miss", scheduled))
        enter(patch.object(settings, "retrieval_miss_capture_enabled", capture))
        enter(patch.object(settings, "retrieval_miss_low_score_threshold", 0.5))
        enter(patch.object(settings, "content_filter_intent_detection", True))
        enter(patch("chat.service.detect_language", return_value=language))
        enter(patch("chat.service.resolve_translation", return_value=translation))
        enter(patch("chat.service.get_translation_info", return_value=None))
        enter(patch("chat.service.is_verse_lookup_request", return_value=False))
        enter(patch("chat.service.extract_references", return_value=([], None)))
        enter(patch.object(service, "_check_content_safety", AsyncMock(return_value=safety)))
        enter(patch.object(service, "_detect_intent", AsyncMock(return_value=intent)))
        enter(
            patch.object(
                service,
                "_wants_clarification",
                MagicMock(return_value=wants_clarification),
            )
        )
        enter(
            patch.object(
                service,
                "_apply_verse_grounding",
                AsyncMock(side_effect=lambda body, *a, **k: (body, [])),
            )
        )
        enter(
            patch.object(
                service,
                "_ground_streamed_answer",
                AsyncMock(side_effect=lambda refs, full, *a, **k: ([], full, [])),
            )
        )
        if path == "chat":
            output = await service.chat(request)
        else:
            output = [event async for event in service.chat_stream(request)]
    return output, scheduled


def _row(scheduled):
    assert scheduled.call_count == 1, scheduled.call_args_list
    return scheduled.call_args.kwargs


# ---------------------------------------------------------------------------
# Detection: each reason on both paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
class TestReasonsThroughChatEntryPoints:
    async def test_empty_results_general_intent(self, path):
        """GENERAL is exempt from the fail-closed guard, so the answer is returned (path b)."""
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(path, service, intent="GENERAL")
        row = _row(scheduled)
        assert row["reasons"] == ["empty"]
        assert row["retrieval_mode"] == "hybrid"
        assert row["top_refs"] == [] and row["top_score"] is None

    async def test_empty_results_fail_closed(self, path):
        """BITB-058: scripture-seeking + no verses -> fail-closed reply; still records 'empty'."""
        service = _service()
        _set_search(service, _ctx())
        output, scheduled = await _run(path, service, intent="COMFORT")
        assert _row(scheduled)["reasons"] == ["empty"]
        assert _row(scheduled)["cited_outside_pool"] == []
        if path == "stream":
            assert output[-1].get("scripture_unavailable") is True

    async def test_search_raises(self, path):
        service = _service()
        _set_search(service, error=RuntimeError("vector index offline"))
        _, scheduled = await _run(path, service, intent="COMFORT")
        row = _row(scheduled)
        assert row["reasons"] == ["empty"]
        assert row["retrieval_mode"] == "none"

    async def test_low_score(self, path):
        service = _service()
        _set_search(service, _ctx(_verse(similarity=0.2)))
        _, scheduled = await _run(path, service)
        row = _row(scheduled)
        assert row["reasons"] == ["low_score"]
        assert row["top_score"] == 0.2
        assert row["threshold"] == 0.5
        assert row["top_refs"] == [{"ref": "John 3:16", "score": 0.2, "source": "search"}]

    async def test_good_score_is_not_a_miss(self, path):
        service = _service()
        _set_search(service, _ctx(_verse(similarity=0.9)))
        _, scheduled = await _run(path, service)
        scheduled.assert_not_called()

    async def test_cited_outside_pool(self, path):
        service = _service(reply="The Lord is my shepherd (Psalm 23:1).")
        _set_search(service, _ctx(_verse(similarity=0.9)))
        _, scheduled = await _run(path, service)
        row = _row(scheduled)
        assert row["reasons"] == ["cited_outside_pool"]
        assert row["cited_outside_pool"] == ["Psalms 23:1"]

    async def test_cited_inside_pool_is_not_a_miss(self, path):
        service = _service(reply="For God so loved the world (John 3:16).")
        _set_search(service, _ctx(_verse(similarity=0.9)))
        _, scheduled = await _run(path, service)
        scheduled.assert_not_called()

    async def test_cited_in_range_passage_is_inside_pool(self, path):
        passage = PassageResult(
            title="Shepherd", reference="Psalm 23:1-6", text="t", similarity=0.9
        )
        service = _service(reply="He restores my soul (Psalm 23:3).")
        _set_search(service, _ctx(_verse(similarity=0.9), passages=[passage]))
        _, scheduled = await _run(path, service)
        scheduled.assert_not_called()

    async def test_cited_earlier_in_history_is_inside(self, path):
        service = _service(reply="As we saw, Psalm 23:1 comforts.")
        _set_search(service, _ctx(_verse(similarity=0.9)))
        _, scheduled = await _run(
            path,
            service,
            conversation_history=[
                {
                    "role": "assistant",
                    "content": "Consider Psalm 23:1 about the shepherd.",
                }
            ],
        )
        scheduled.assert_not_called()

    async def test_multiple_reasons_in_one_turn(self, path):
        service = _service(reply="Trust the Lord (Proverbs 3:5).")
        _set_search(service, _ctx(_verse(similarity=0.2)))
        _, scheduled = await _run(path, service)
        row = _row(scheduled)
        assert set(row["reasons"]) == {"low_score", "cited_outside_pool"}

    async def test_signals_carry_embedding_identity_and_session_hash(self, path):
        service = _service()
        _set_search(service, _ctx(_verse(similarity=0.2)))
        _, scheduled = await _run(path, service, session_id="abc-123")
        row = _row(scheduled)
        assert row["embedding_provider"] == settings.embedding_provider
        assert row["embedding_model"]
        assert row["session_id_hash"] == rm._hash_session_id("abc-123")
        assert "abc-123" not in json.dumps(row, default=str)


# ---------------------------------------------------------------------------
# Turns that must never record
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
class TestNeverRecorded:
    async def test_off_topic(self, path):
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(path, service, intent="OFF_TOPIC")
        scheduled.assert_not_called()

    async def test_needs_clarification(self, path):
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(
            path, service, intent="NEEDS_CLARIFICATION", wants_clarification=True
        )
        scheduled.assert_not_called()

    async def test_blocked(self, path):
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(path, service, safety=BLOCKED)
        scheduled.assert_not_called()

    async def test_compassionate_crisis_turn(self, path):
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(path, service, safety=COMPASSIONATE)
        scheduled.assert_not_called()

    async def test_include_search_false(self, path):
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(path, service, include_search=False)
        scheduled.assert_not_called()

    async def test_capture_flag_off(self, path):
        service = _service()
        _set_search(service, _ctx())
        _, scheduled = await _run(path, service, intent="GENERAL", capture=False)
        scheduled.assert_not_called()

    async def test_general_intent_low_score_is_exempt(self, path):
        service = _service()
        _set_search(service, _ctx(_verse(similarity=0.1)))
        _, scheduled = await _run(path, service, intent="GENERAL")
        scheduled.assert_not_called()


# ---------------------------------------------------------------------------
# Cross-language and cross-version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("language", LANGUAGES)
async def test_every_language_is_recorded_with_topics_where_supported(path, language):
    service = _service()
    _set_search(service, _ctx(_verse(similarity=0.1)))
    _, scheduled = await _run(path, service, message=ANXIOUS[language], language=language)
    row = _row(scheduled)
    assert row["language"] == language
    assert row["reasons"] == ["low_score"]
    if language in SUPPORTED_TOPIC_LANGUAGES:
        assert "anxiety" in row["topics"], language
    else:
        # ru/zh/hi/ko: detect_topics has no keywords for them (BITB-264).
        assert row["topics"] == [], language
    assert ANXIOUS[language] not in json.dumps(row, ensure_ascii=False, default=str)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("translation", ["kjv", "web", "rvr1960", "cuv"])
async def test_translation_is_the_users_not_a_hardcoded_one(path, translation):
    service = _service()
    search = _set_search(service, _ctx(_verse(similarity=0.1)))
    _, scheduled = await _run(path, service, translation=translation)
    assert _row(scheduled)["translation"] == translation
    assert search.call_args.kwargs["translation"] == translation


@pytest.mark.parametrize("path", PATHS)
async def test_wrapped_and_cjk_citations_outside_pool_are_detected(path):
    """Parenthesized / fullwidth CJK citations go through the real parser."""
    service = _service(reply="耶和华是我的牧者（诗篇23：1）。")
    _set_search(service, _ctx(_verse(similarity=0.9)))
    _, scheduled = await _run(path, service, message=ANXIOUS["zh"], language="zh")
    assert _row(scheduled)["reasons"] == ["cited_outside_pool"]


@pytest.mark.parametrize("path", PATHS)
async def test_retrieval_mode_reflects_settings(path):
    service = _service()
    _set_search(service, _ctx(_verse(similarity=0.1)))
    with patch.object(settings, "hybrid_search_enabled", False):
        _, scheduled = await _run(path, service)
    assert _row(scheduled)["retrieval_mode"] == "semantic"


# ---------------------------------------------------------------------------
# Privacy: sentinel
# ---------------------------------------------------------------------------


SENTINEL_CASES = [
    pytest.param(
        "en",
        f"I feel anxious {SENTINEL} because my friend {NAME} left",
        (
            f"anxiety, peace, trust in God, {SENTINEL}, {NAME}, Bartholomew, "
            f"bartholomew@example.com, https://example.com/{SENTINEL}, call 555 0100"
        ),
        ["anxiety", "peace"],
        (SENTINEL, "Bartholomew", "Quillfeather", "example.com", "555 0100"),
        id="en",
    ),
    pytest.param(
        "zh",
        f"我很焦虑 {SENTINEL}，朋友张伟的手术让我害怕",
        f"anxiety\n- 张伟的手术\n- 张伟\n* {SENTINEL}\n1. 约翰福音\n2) 张伟医生",
        ["anxiety", "约翰福音"],
        (SENTINEL, "张伟", "手术", "医生"),
        id="zh-bullets",
    ),
    pytest.param(
        "en",
        "My friend Daniel is scared about the surgery",
        "- hope\n- Daniel\n- Maria\n- Lisbon hospital\n- see example.com",
        ["hope"],
        ("Daniel", "Maria", "Lisbon", "example.com"),
        id="bullets-book-name-echo",
    ),
]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("language,message,expansion,expected_terms,secrets", SENTINEL_CASES)
async def test_sentinel_never_reaches_the_row_or_the_log(  # noqa: C901
    path, language, message, expansion, expected_terms, secrets, caplog
):
    service = _service(expansion=expansion)
    _set_search(service, _ctx(_verse(similarity=0.1)))
    recorded = AsyncMock()
    caplog.set_level(logging.DEBUG)
    with patch.object(rm, "record_retrieval_miss", recorded):
        await _run_real_schedule(path, service, message, language)
        await asyncio.gather(*list(rm._PENDING))

    recorded.assert_awaited_once()
    row = recorded.await_args.kwargs
    blob = json.dumps(row, ensure_ascii=False, default=str)
    for secret in secrets:
        assert secret not in blob, secret
    assert row["expansion_terms"] == expected_terms

    miss_records = [r for r in caplog.records if r.getMessage() == "rag_retrieval_miss"]
    assert len(miss_records) == 1
    log_blob = json.dumps(
        {k: v for k, v in miss_records[0].__dict__.items() if k != "args"},
        ensure_ascii=False,
        default=str,
    )
    for secret in secrets:
        assert secret not in log_blob, secret
    assert "session_id_hash" not in miss_records[0].__dict__


async def _run_real_schedule(path, service, message, language="en"):
    """Like ``_run`` but leaves ``schedule_retrieval_miss`` real (record is patched by caller)."""
    request = ChatRequest(message=message, language=language, session_id="sess-1")
    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(settings, "retrieval_miss_capture_enabled", True))
        enter(patch.object(settings, "retrieval_miss_low_score_threshold", 0.5))
        enter(patch("chat.service.detect_language", return_value=language))
        enter(patch("chat.service.resolve_translation", return_value="kjv"))
        enter(patch("chat.service.get_translation_info", return_value=None))
        enter(patch("chat.service.is_verse_lookup_request", return_value=False))
        enter(patch("chat.service.extract_references", return_value=([], None)))
        enter(patch.object(service, "_check_content_safety", AsyncMock(return_value=CLEAN)))
        enter(patch.object(service, "_detect_intent", AsyncMock(return_value="COMFORT")))
        enter(patch.object(service, "_wants_clarification", MagicMock(return_value=False)))
        enter(
            patch.object(
                service,
                "_apply_verse_grounding",
                AsyncMock(side_effect=lambda body, *a, **k: (body, [])),
            )
        )
        enter(
            patch.object(
                service,
                "_ground_streamed_answer",
                AsyncMock(side_effect=lambda refs, full, *a, **k: ([], full, [])),
            )
        )
        if path == "chat":
            output = await service.chat(request)
        else:
            output = [event async for event in service.chat_stream(request)]
    return output


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
async def test_db_failure_never_affects_the_reply(path):
    service = _service(reply="God is near.")
    _set_search(service, _ctx(_verse(similarity=0.1)))
    boom = MagicMock(side_effect=RuntimeError("db down"))
    request = ChatRequest(message="I feel anxious", language="en")
    with (
        patch("scripture.database.async_session_factory", boom),
        patch.object(settings, "retrieval_miss_capture_enabled", True),
        patch.object(settings, "retrieval_miss_low_score_threshold", 0.5),
        patch("chat.service.detect_language", return_value="en"),
        patch("chat.service.resolve_translation", return_value="kjv"),
        patch("chat.service.get_translation_info", return_value=None),
        patch("chat.service.is_verse_lookup_request", return_value=False),
        patch("chat.service.extract_references", return_value=([], None)),
        patch.object(service, "_check_content_safety", AsyncMock(return_value=CLEAN)),
        patch.object(service, "_detect_intent", AsyncMock(return_value="COMFORT")),
        patch.object(service, "_wants_clarification", MagicMock(return_value=False)),
        patch.object(
            service,
            "_apply_verse_grounding",
            AsyncMock(side_effect=lambda body, *a, **k: (body, [])),
        ),
        patch.object(
            service,
            "_ground_streamed_answer",
            AsyncMock(side_effect=lambda refs, full, *a, **k: ([], full, [])),
        ),
    ):
        if path == "chat":
            response = await service.chat(request)
            text = response.message
        else:
            events = [event async for event in service.chat_stream(request)]
            text = "".join(e["content"] for e in events if e["type"] == "content")
            assert events[-1]["type"] == "completion"
        await asyncio.gather(*list(rm._PENDING))  # the background task swallowed the error
    assert text == "God is near."
    boom.assert_called()


@pytest.mark.parametrize("path", PATHS)
async def test_scheduler_raising_inside_hook_never_affects_the_reply(path):
    service = _service(reply="God is near.")
    _set_search(service, _ctx(_verse(similarity=0.1)))
    output, scheduled = await _run(path, service, intent="COMFORT")  # baseline: scheduled once
    assert scheduled.call_count == 1

    service = _service(reply="God is near.")
    _set_search(service, _ctx(_verse(similarity=0.1)))
    with patch("chat.service.pool_keys", side_effect=RuntimeError("bug")):
        output, scheduled = await _run(path, service, intent="COMFORT")
    scheduled.assert_not_called()
    if path == "chat":
        assert output.message == "God is near."
    else:
        assert output[-1]["type"] == "completion"


# ---------------------------------------------------------------------------
# Sanitizer (the privacy boundary)
# ---------------------------------------------------------------------------


# One adversarial case per language: (expansion, user message, expected kept terms).
# Everything not on the allow-list (topic vocabulary / book names) must vanish.
SANITIZER_CASES = {
    "en": (
        "hope; Sarah Miller; Tom's surgery; peace",
        "sarah miller has tom's surgery",
        ["hope", "peace"],
    ),
    "it": (
        "speranza, Maria Rossi, ansia, ospedale di Lisbona",
        "Maria Rossi è in ospedale",
        ["speranza", "ansia"],
    ),
    "de": ("Klaus Müller, angst, Krankenhaus", "klaus müller ist krank", ["angst"]),
    "es": ("ansiedad, Juan Pérez; el hospital", "mi tío Juan Pérez", ["ansiedad"]),
    "fr": ("anxiété, Jean-Luc Picard, hôpital", "Jean-Luc Picard", ["anxiété"]),
    "pt": ("ansiedade, Ana Souza, cirurgia", "Ana Souza", ["ansiedade"]),
    "ar": ("قلق، أحمد علي، مستشفى", "أحمد علي في المستشفى", ["قلق"]),
    "ru": ("Иван Петров; больница", "Иван Петров", []),
    "zh": ("anxiety、张伟的手术；平安", "张伟的手术", ["anxiety"]),
    "hi": ("राहुल शर्मा, अस्पताल", "राहुल शर्मा", []),
    "ko": ("anxiety，김민수의 수술", "김민수의 수술", ["anxiety"]),
}


class TestSanitizeExpansionTerms:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_allow_list_only_per_language(self, language):
        expansion, message, expected = SANITIZER_CASES[language]
        assert rm.sanitize_expansion_terms(expansion, message) == expected

    def test_keeps_topic_vocabulary_and_book_names(self):
        out = rm.sanitize_expansion_terms("anxious, peace, Isaiah, Genesi, 约翰福音", "hello there")
        assert out == ["anxious", "peace", "isaiah", "genesi", "约翰福音"]

    def test_short_free_text_is_dropped_even_if_not_echoed(self):
        # The old '<= 3 words and not an echo' pass is gone: names the model invents or
        # recalls from elsewhere in the conversation must not slip through either.
        assert rm.sanitize_expansion_terms("Maria Lopez, grief counselor, my wife", "hi") == []

    def test_no_word_salvage_from_sentences(self):
        assert rm.sanitize_expansion_terms("a long phrase about Dolores and her anxiety", "x") == []

    def test_bullet_lists_with_markers(self):
        out = rm.sanitize_expansion_terms(
            "hope\n- Maria\n- Lisbon hospital\n* peace\n• grief\n1. faith\n2) forgiveness",
            "Maria in Lisbon",
        )
        assert out == ["hope", "peace", "grief", "faith", "forgiveness"]

    @pytest.mark.parametrize(
        "term", ["example.com", "visit example.com", "mail me", "a@b.org", "https://x.io", "www.x"]
    )
    def test_domains_emails_urls_dropped(self, term):
        assert rm.sanitize_expansion_terms(f"hope, {term}", "msg") == ["hope"]

    def test_digits_dropped(self):
        assert rm.sanitize_expansion_terms("grief, room 12, john3", "msg") == ["grief"]

    @pytest.mark.parametrize("book", ["Daniel", "Mark", "James", "John", "Ruth"])
    def test_book_name_echoing_a_person_is_dropped(self, book):
        assert rm.sanitize_expansion_terms(f"{book}, hope", f"my friend {book} is sick") == ["hope"]

    def test_book_name_in_email_style_message_is_dropped(self):
        msg = "john dot doe at gmail dot com"
        assert rm.sanitize_expansion_terms("john, hope", msg) == ["hope"]

    def test_book_name_kept_when_message_has_a_verse_reference_to_it(self):
        assert rm.sanitize_expansion_terms("John, hope", "What does John 3:16 mean?") == [
            "john",
            "hope",
        ]
        # a reference to another book does not excuse the name
        assert rm.sanitize_expansion_terms("John, hope", "what about Mark 3:1 and John") == ["hope"]

    def test_unspaced_book_name_echo_uses_substring(self):
        assert rm.sanitize_expansion_terms("路得, 平安", "我朋友路得病了") == []

    def test_topic_keyword_echoed_by_user_is_fine(self):
        assert rm.sanitize_expansion_terms("anxious", "I am anxious") == ["anxious"]

    def test_exact_whole_term_only(self):
        assert rm.sanitize_expansion_terms("peaceful neighbourhood, anxiou, hopele", "x") == []

    def test_caps_term_length_at_40(self):
        from unittest.mock import patch as _p

        long_book = "b" * 60
        with _p.object(rm, "_vocab", return_value=(frozenset(), frozenset({long_book}))):
            out = rm.sanitize_expansion_terms(long_book, "msg")
        assert len(out) == 1 and len(out[0]) == 40

    def test_caps_count_at_10_and_dedupes(self):
        words = [f"w{chr(97 + i)}" for i in range(15)]
        with patch.object(rm, "_vocab", return_value=(frozenset(words), frozenset())):
            out = rm.sanitize_expansion_terms(", ".join(words + words[:2]), "msg")
        assert out == words[:10]

    @pytest.mark.parametrize("sep", [",", ";", "\n", "•", "·", "、", "，", "；", " - "])
    def test_splits_on_ascii_and_cjk_separators(self, sep):
        assert rm.sanitize_expansion_terms(f"hope{sep}forgiveness", "msg") == [
            "hope",
            "forgiveness",
        ]

    def test_strips_quotes_and_brackets_around_terms(self):
        assert rm.sanitize_expansion_terms('"hope", 「平安」, (peace)', "msg") == ["hope", "peace"]

    @pytest.mark.parametrize("value", [None, "", "   ", ",,;;"])
    def test_empty_inputs(self, value):
        assert rm.sanitize_expansion_terms(value, "msg") == []

    def test_every_topic_keyword_is_allow_listed(self):
        for keywords in TOPIC_KEYWORD_MAP.values():
            keyword = keywords[0]
            if any(ch.isdigit() for ch in keyword) or "." in keyword:
                continue
            assert rm.sanitize_expansion_terms(keyword, "unrelated") == [keyword.casefold()]


# ---------------------------------------------------------------------------
# Classifier / threshold / pool unit tests
# ---------------------------------------------------------------------------


def _trace(**kw):
    return rm.RetrievalTrace(**kw)


class TestClassifyMiss:
    def classify(self, ctx, **kw):
        base = dict(
            ctx=ctx,
            trace=_trace(),
            intent="COMFORT",
            is_verse_lookup=False,
            threshold=0.5,
            outside=[],
        )
        base.update(kw)
        return rm.classify_miss(**base)

    def test_none_ctx_and_empty_ctx_and_failed_search_are_empty(self):
        assert self.classify(None) == ["empty"]
        assert self.classify(_ctx()) == ["empty"]
        assert self.classify(_ctx(_verse()), trace=_trace(search_failed=True)) == ["empty"]

    def test_low_score_boundary_is_strict(self):
        assert self.classify(_ctx(_verse(similarity=0.49))) == ["low_score"]
        assert self.classify(_ctx(_verse(similarity=0.5))) == []

    def test_uses_the_best_score(self):
        ctx = _ctx(_verse(similarity=0.1), _verse(verse=17, similarity=0.8))
        assert self.classify(ctx) == []

    def test_direct_lookups_without_similarity_are_not_low_score(self):
        assert self.classify(_ctx(_verse(similarity=None))) == []

    def test_verse_lookup_and_general_skip_low_score(self):
        ctx = _ctx(_verse(similarity=0.1))
        assert self.classify(ctx, is_verse_lookup=True) == []
        assert self.classify(ctx, intent="GENERAL") == []

    def test_general_still_reports_empty(self):
        assert self.classify(None, intent="GENERAL") == ["empty"]

    def test_outside_adds_reason(self):
        assert self.classify(_ctx(_verse()), outside=["Psalms 23:1"]) == ["cited_outside_pool"]


class TestThreshold:
    def test_explicit_setting_wins(self):
        with patch.object(settings, "retrieval_miss_low_score_threshold", 0.33):
            assert rm.resolve_low_score_threshold("hybrid") == 0.33

    def test_per_model_and_mode(self):
        with (
            patch.object(settings, "retrieval_miss_low_score_threshold", None),
            patch.object(settings, "embedding_provider", "ollama"),
            patch.object(settings, "embedding_model", "mxbai-embed-large"),
        ):
            assert rm.resolve_low_score_threshold("hybrid_boosted") == 0.50
            assert rm.resolve_low_score_threshold("semantic") == 0.55

    def test_azure_uses_deployment_name(self):
        with (
            patch.object(settings, "retrieval_miss_low_score_threshold", None),
            patch.object(settings, "embedding_provider", "azure_openai"),
            patch.object(settings, "azure_embedding_deployment", "text-embedding-3-small"),
        ):
            assert rm.resolve_low_score_threshold("hybrid") == 0.45

    def test_model_only_key_then_default(self):
        with (
            patch.object(settings, "retrieval_miss_low_score_threshold", None),
            patch.object(settings, "embedding_provider", "ollama"),
            patch.object(settings, "embedding_model", "custom"),
            patch.object(settings, "retrieval_miss_low_score_thresholds", {"custom": 0.7}),
        ):
            assert rm.resolve_low_score_threshold("hybrid") == 0.7
        with (
            patch.object(settings, "retrieval_miss_low_score_threshold", None),
            patch.object(settings, "embedding_model", "unknown"),
            patch.object(settings, "retrieval_miss_low_score_thresholds", {}),
        ):
            assert rm.resolve_low_score_threshold("hybrid") == 0.5


class TestPoolAndOutside:
    def test_pool_includes_verses_passage_ranges_and_extra(self):
        ctx = _ctx(
            _verse("Giovanni", 3, 16),
            passages=[PassageResult(title="t", reference="Psalm 23:1-3", text="x")],
        )
        pool = rm.pool_keys(ctx, {("Romans", 8, 28)})
        assert ("John", 3, 16) in pool
        assert {("Psalms", 23, 1), ("Psalms", 23, 2), ("Psalms", 23, 3)} <= pool
        assert ("Romans", 8, 28) in pool

    def test_pool_of_none_is_extra_only(self):
        assert rm.pool_keys(None, {("A", 1, 1)}) == {("A", 1, 1)}

    def test_range_citation_inside_if_any_verse_in_pool(self):
        ref = VerseReference(book="John", chapter=3, verse_start=15, verse_end=17)
        assert rm.refs_outside_pool([ref], {("John", 3, 16)}, set()) == []

    def test_ref_outside_and_dedup(self):
        ref = VerseReference(book="John", chapter=1, verse_start=1)
        assert rm.refs_outside_pool([ref, ref], set(), set()) == ["John 1:1"]

    def test_range_expansion_is_capped(self):
        ref = VerseReference(book="Psalms", chapter=119, verse_start=1, verse_end=100000)
        assert len(rm._range_keys("Psalms", 119, 1, 100000)) == rm.MAX_POOL_KEYS
        assert rm.refs_outside_pool([ref], set(), set()) == ["Psalms 119:1-100000"]


class TestTopRefs:
    def test_direct_vs_search_source_and_top_five(self):
        verses = [_verse(verse=i, similarity=0.5 + i / 100) for i in range(1, 8)]
        verses.append(_verse(verse=30, similarity=None))
        refs = rm.top_refs_for(_ctx(*verses))
        assert len(refs) == 5
        assert refs[0]["score"] == 0.57 and refs[0]["source"] == "search"
        direct = rm.top_refs_for(_ctx(_verse(similarity=None)))
        assert direct == [{"ref": "John 3:16", "score": None, "source": "direct"}]

    def test_none_ctx(self):
        assert rm.top_refs_for(None) == []


class TestTopicsForRecord:
    def test_returns_canonical_english_ids_sorted(self):
        assert rm.topics_for_record("Ich bin ängstlich und brauche Frieden") == sorted(
            rm.topics_for_record("Ich bin ängstlich und brauche Frieden")
        )
        assert "anxiety" in rm.topics_for_record("Mi sento ansioso")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _fields(**kw):
    base = dict(
        reasons=["empty", "low_score"],
        intent="COMFORT",
        language="it",
        translation="kjv",
        topics=["anxiety", "peace"],
        expansion_terms=["hope"],
        top_refs=[],
        top_score=0.2,
        threshold=0.5,
        cited_outside_pool=[],
        retrieval_mode="hybrid",
        embedding_provider="ollama",
        embedding_model="mxbai-embed-large",
        session_id_hash=None,
    )
    base.update(kw)
    return base


def _session_factory(db):
    factory = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = cm
    return factory


class TestSignatureAndUpsert:
    def test_signature_is_stable_under_permutation(self):
        a = rm.compute_signature(
            reasons=["empty", "low_score"],
            intent="X",
            language="en",
            translation="kjv",
            topics=["a", "b"],
            retrieval_mode="hybrid",
            embedding_model="m",
        )
        b = rm.compute_signature(
            reasons=["low_score", "empty"],
            intent="X",
            language="en",
            translation="kjv",
            topics=["b", "a"],
            retrieval_mode="hybrid",
            embedding_model="m",
        )
        assert a == b and len(a) == 64

    @pytest.mark.parametrize(
        "change",
        [
            {"reasons": ["empty", "low_score"]},
            {"intent": "Y"},
            {"language": "de"},
            {"translation": "web"},
            {"topics": ["a"]},
            {"retrieval_mode": "semantic"},
            {"embedding_model": "other-model"},
        ],
    )
    def test_signature_changes_with_each_component(self, change):
        base = dict(
            reasons=["empty"],
            intent="X",
            language="en",
            translation="kjv",
            topics=[],
            retrieval_mode="hybrid",
            embedding_model="m",
        )
        assert rm.compute_signature(**base) != rm.compute_signature(**{**base, **change})

    def test_make_row_ttl_is_retention_days_from_now(self):
        before = datetime.now(UTC)
        row = rm.make_row(**_fields())
        assert row["hit_count"] == 1
        expected = before + timedelta(days=settings.retrieval_miss_retention_days)
        assert abs((row["expires_at"] - expected).total_seconds()) < 5
        assert settings.retrieval_miss_retention_days == 90

    def test_upsert_increments_hit_count_and_never_refreshes_ttl(self):
        from sqlalchemy.dialects import postgresql

        stmt = rm.build_retrieval_miss_upsert(**rm.make_row(**_fields()))
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "ON CONFLICT (signature_sha256) DO UPDATE" in sql
        set_clause, _, where_clause = sql.split("DO UPDATE SET", 1)[1].partition(" WHERE ")
        # an already-expired (not yet purged) row must not be bumped back to life
        assert "retrieval_miss_samples.expires_at > now()" in where_clause
        assert "hit_count = (retrieval_miss_samples.hit_count +" in set_clause
        assert "last_seen_at = excluded.last_seen_at" in set_clause
        for untouched in (
            "expires_at",
            "created_at",
            "session_id_hash",
            "signature_sha256",
        ):
            assert untouched not in set_clause, untouched

    def test_row_has_no_text_columns(self):
        from feedback.models import RetrievalMissSample

        names = {c.name for c in RetrievalMissSample.__table__.columns}
        assert not {n for n in names if "text" in n or "message" in n or "prompt" in n}
        assert not names & {"user_agent", "ip", "ip_address", "user_id"}


class TestRecordAndPurge:
    async def test_noop_when_flag_off(self):
        factory = _session_factory(MagicMock())
        with (
            patch.object(settings, "retrieval_miss_capture_enabled", False),
            patch("scripture.database.async_session_factory", factory),
        ):
            await rm.record_retrieval_miss(**_fields())
        factory.assert_not_called()

    async def test_executes_one_upsert_and_commits(self):
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        with (
            patch.object(settings, "retrieval_miss_capture_enabled", True),
            patch("scripture.database.async_session_factory", _session_factory(db)),
        ):
            await rm.record_retrieval_miss(**_fields())
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    async def test_execute_error_rolls_back_and_is_swallowed(self):
        db = MagicMock()
        db.execute = AsyncMock(side_effect=RuntimeError("constraint"))
        db.rollback = AsyncMock()
        with (
            patch.object(settings, "retrieval_miss_capture_enabled", True),
            patch("scripture.database.async_session_factory", _session_factory(db)),
        ):
            await rm.record_retrieval_miss(**_fields())  # must not raise
        db.rollback.assert_awaited_once()

    async def test_factory_error_is_swallowed(self):
        with (
            patch.object(settings, "retrieval_miss_capture_enabled", True),
            patch(
                "scripture.database.async_session_factory",
                side_effect=RuntimeError("x"),
            ),
        ):
            await rm.record_retrieval_miss(**_fields())

    async def test_purge_returns_rowcount(self):
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock(rowcount=4))
        db.commit = AsyncMock()
        with patch("scripture.database.async_session_factory", _session_factory(db)):
            assert await rm.purge_expired_retrieval_misses() == 4
        sql = str(db.execute.await_args.args[0])
        assert "DELETE FROM retrieval_miss_samples" in sql and "expires_at" in sql

    async def test_purge_error_returns_zero_with_rollback(self):
        db = MagicMock()
        db.execute = AsyncMock(side_effect=RuntimeError("dropped"))
        db.rollback = AsyncMock()
        with patch("scripture.database.async_session_factory", _session_factory(db)):
            assert await rm.purge_expired_retrieval_misses() == 0
        db.rollback.assert_awaited_once()

    async def test_purge_import_error_returns_zero(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "scripture.database", None)
        assert await rm.purge_expired_retrieval_misses() == 0


class TestEmit:
    def test_counter_per_reason_with_bounded_attributes(self):
        with patch.object(rm, "chat_retrieval_miss_counter") as counter:
            rm.emit_retrieval_miss(
                {**_fields(), "reasons": ["empty", "low_score"], "language": "ko"}
            )
        assert counter.add.call_count == 2
        attrs = [c.args[1] for c in counter.add.call_args_list]
        assert {a["reason"] for a in attrs} == {"empty", "low_score"}
        assert all(set(a) == {"reason", "language", "translation", "intent"} for a in attrs)

    def test_schedule_never_raises_even_without_a_running_loop(self):
        with patch.object(rm, "emit_retrieval_miss", side_effect=RuntimeError("x")):
            rm.schedule_retrieval_miss(**_fields())  # no exception

    async def test_schedule_creates_background_task_and_discards_it(self):
        recorded = AsyncMock()
        with (
            patch.object(rm, "record_retrieval_miss", recorded),
            patch.object(rm, "emit_retrieval_miss"),
        ):
            rm.schedule_retrieval_miss(**_fields())
            assert len(rm._PENDING) >= 1
            await asyncio.gather(*list(rm._PENDING))
            await asyncio.sleep(0)
        recorded.assert_awaited_once()
        assert not rm._PENDING


# ---------------------------------------------------------------------------
# cited_outside_pool across citation shapes (BITB-256 / AGENTS multilingual rule)
# ---------------------------------------------------------------------------

CITATIONS = [
    pytest.param(
        "es", "Dios te ama [Juan 3:16].", "El Señor es mi pastor [Salmos 23:1].", id="es-bracket"
    ),
    pytest.param(
        "de",
        "So sehr hat Gott die Welt geliebt (Johannes 3,16).",
        "Der Herr ist mein Hirte (Psalm 23,1).",
        id="de-comma",
    ),
    pytest.param(
        "ar", "لأنه هكذا أحب الله العالم (يوحنا 3:16).", "الرب راعي (المزامير 23:1).", id="ar"
    ),
    pytest.param(
        "hi",
        "परमेश्वर ने जगत से प्रेम किया (यूहन्ना 3:16)।",
        "यहोवा मेरा चरवाहा है (भजन संहिता 23:1)।",
        id="hi-devanagari",
    ),
    pytest.param(
        "zh", "神爱世人（约翰福音3：16）。", "耶和华是我的牧者（诗篇23：1）。", id="zh-fullwidth"
    ),
    pytest.param(
        "ko",
        "하나님이 세상을 사랑하사 (요한복음 3:16).",
        "여호와는 나의 목자시니 (시편 23:1).",
        id="ko",
    ),
]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("language,inside_reply,outside_reply", CITATIONS)
class TestCitationShapes:
    async def test_citation_inside_pool_is_not_flagged(
        self, path, language, inside_reply, outside_reply
    ):
        service = _service(reply=inside_reply)
        _set_search(service, _ctx(_verse(similarity=0.9)))
        _, scheduled = await _run(path, service, language=language, message=ANXIOUS[language])
        scheduled.assert_not_called()

    async def test_different_citation_is_flagged(self, path, language, inside_reply, outside_reply):
        service = _service(reply=outside_reply)
        _set_search(service, _ctx(_verse(similarity=0.9)))
        _, scheduled = await _run(path, service, language=language, message=ANXIOUS[language])
        row = _row(scheduled)
        assert row["reasons"] == ["cited_outside_pool"]
        assert row["cited_outside_pool"] == ["Psalms 23:1"]


# ---------------------------------------------------------------------------
# Write bounding, search-failure telemetry-only, config validators
# ---------------------------------------------------------------------------


class TestWriteBounding:
    async def test_pending_cap_drops_db_write_but_keeps_telemetry(self):
        recorded = AsyncMock()
        with (
            patch.object(rm, "record_retrieval_miss", recorded),
            patch.object(rm, "emit_retrieval_miss") as emit,
            patch.object(rm, "_PENDING", {object()}),
            patch.object(rm, "MAX_PENDING_WRITES", 1),
        ):
            rm.schedule_retrieval_miss(**_fields())
        emit.assert_called_once()
        recorded.assert_not_called()

    async def test_persist_false_is_telemetry_only(self):
        recorded = AsyncMock()
        with (
            patch.object(rm, "record_retrieval_miss", recorded),
            patch.object(rm, "emit_retrieval_miss") as emit,
        ):
            rm.schedule_retrieval_miss(persist=False, **_fields())
            await asyncio.sleep(0)
        emit.assert_called_once()
        recorded.assert_not_called()

    @pytest.mark.parametrize("path", PATHS)
    async def test_failed_search_is_not_persisted(self, path):
        service = _service()
        _set_search(service, error=RuntimeError("db down"))
        _, scheduled = await _run(path, service, intent="COMFORT")
        assert _row(scheduled)["persist"] is False

    @pytest.mark.parametrize("path", PATHS)
    async def test_weak_results_are_persisted(self, path):
        service = _service()
        _set_search(service, _ctx(_verse(similarity=0.1)))
        _, scheduled = await _run(path, service)
        assert _row(scheduled)["persist"] is True


class TestConfigValidators:
    def test_blank_threshold_means_unset(self):
        from config import Settings

        for blank in ("", "  "):
            s = Settings(retrieval_miss_low_score_threshold=blank)
            assert s.retrieval_miss_low_score_threshold is None
        assert (
            Settings(retrieval_miss_low_score_threshold="0.4").retrieval_miss_low_score_threshold
            == 0.4
        )

    @pytest.mark.parametrize("days", [1, 45, 90])
    def test_retention_in_range_ok(self, days):
        from config import Settings

        assert Settings(retrieval_miss_retention_days=days).retrieval_miss_retention_days == days

    @pytest.mark.parametrize("days", [0, -1, 91, 365])
    def test_retention_outside_policy_rejected(self, days):
        from pydantic import ValidationError

        from config import Settings

        with pytest.raises(ValidationError):
            Settings(retrieval_miss_retention_days=days)

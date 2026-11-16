"""
BITB-320: reliable chat completion -- POST /chat/finalize, the degraded ``completion`` and the
stream disconnect / partial-error signals.

Covers:
- FinalizeRequest validation (extra=forbid, bounds, malformed message_id, history trim)
- ChatService.finalize: trailer chips, LLM chips, LLM failure, flag off, ``truncated``,
  11-language verse extraction through the real parse -> resolve -> ground path,
  version-faithfulness (KJV vs WEB), privacy (no text in logs)
- chat_stream: a post-generation exception yields a degraded ``completion``
- routes/chat.py: /finalize contract + rate limit + content filter + no Turnstile,
  disconnect log/counter, ``partial`` / ``message_id`` on an error after content
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.prompts import get_follow_ups_only_prompt
from chat.service import (
    _UNTERMINATED_TRAILER,
    ChatRequest,
    ChatService,
    FinalizeRequest,
    _looks_truncated,
)
from config import settings
from main import app
from providers import get_embedding_provider, get_llm_provider
from providers.base import LLMResponse
from scripture import get_db_session
from scripture.search import VerseResult
from utils.rate_limiter import reset_rate_limiter

ALL_LANGS = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]

# (text containing John 3:16 [or a range], expected cited ref) per language -- parenthesized,
# bracketed, fullwidth CJK, RTL, Devanagari, German comma, range.
CITATIONS = {
    "en": ("God so loved the world (John 3:16).", "John 3:16"),
    "it": ("Dio ha tanto amato il mondo [Giovanni 3:16].", "John 3:16"),
    "de": ("Gott liebt die Welt: Johannes 3,16.", "John 3:16"),
    "es": ("Dios amó al mundo (Juan 3:16).", "John 3:16"),
    "fr": ("Dieu a tant aimé le monde (Jean 3:16-17).", "John 3:16-17"),
    "pt": ("Deus amou o mundo (João 3:16).", "John 3:16"),
    "ar": ("لأنه هكذا أحب الله العالم (يوحنا 3:16).", "John 3:16"),
    "ru": ("Ибо так возлюбил Бог мир (Иоанн 3:16).", "John 3:16"),
    "zh": ("神爱世人（约翰福音３：１６）。", "John 3:16"),
    "hi": ("परमेश्वर ने जगत से प्रेम किया (यूहन्ना 3:16)।", "John 3:16"),
    "ko": ("하나님이 세상을 사랑하셨다 (요한복음 3:16).", "John 3:16"),
}

TWO_CHIPS = "<!-- FOLLOWUPS: What does this mean for me?|How can I pray about this? -->"


def _verse(book="John", chapter=3, verse=16, translation="kjv", text=None):
    return VerseResult(
        reference=f"{book} {chapter}:{verse}",
        text=text or f"[{translation}] text of {book} {chapter}:{verse}",
        book=book,
        chapter=chapter,
        verse=verse,
        translation=translation,
    )


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(content="GENERAL", model="test-model", provider="test")
    )
    llm.chat_stream = MagicMock()
    return llm


@pytest.fixture
def service(mock_llm):
    svc = ChatService(MagicMock(), mock_llm, AsyncMock())
    search = MagicMock()

    async def get_verse(book, chapter, verse, translation=None):
        return _verse(book, chapter, verse, translation or "kjv")

    async def get_verse_range(book, chapter, start, end, translation=None):
        return [_verse(book, chapter, v, translation or "kjv") for v in range(start, end + 1)]

    search.get_verse = AsyncMock(side_effect=get_verse)
    search.get_verse_range = AsyncMock(side_effect=get_verse_range)
    svc.search_service = search
    return svc


def _req(**over):
    base = {"message": "Tell me about love", "assistant_text": "Love is patient.", "reason": "eof"}
    base.update(over)
    return FinalizeRequest(**base)


# ---------------------------------------------------------------------------
# FinalizeRequest validation
# ---------------------------------------------------------------------------


class TestFinalizeRequest:
    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            _req(bogus=1)

    @pytest.mark.parametrize("field", ["message", "assistant_text"])
    def test_empty_rejected(self, field):
        with pytest.raises(ValidationError):
            _req(**{field: ""})

    def test_assistant_text_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            _req(assistant_text="x" * (settings.max_history_message_length + 1))

    def test_bad_reason_and_platform_rejected(self):
        with pytest.raises(ValidationError):
            _req(reason="whatever")
        with pytest.raises(ValidationError):
            _req(platform="ios")

    def test_platform_defaults_to_web(self):
        assert _req().platform == "web"

    def test_malformed_message_id_is_ignored_not_rejected(self):
        assert _req(message_id="not-a-uuid").message_id is None
        good = "3f2b8a52-1b0e-4c53-9d33-7a1f6a3d2e11"
        assert _req(message_id=good).message_id == good

    def test_history_trimmed_like_chat_request(self):
        history = [{"role": "user", "content": f"m{i}"} for i in range(500)]
        req = _req(conversation_history=history)
        chat_req = ChatRequest(message="hi", conversation_history=history)
        assert len(req.conversation_history) == len(chat_req.conversation_history)
        assert len(req.conversation_history) == settings.max_conversation_history

    def test_history_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            _req(conversation_history=[{"role": "system", "content": "x"}])


# ---------------------------------------------------------------------------
# truncated heuristic
# ---------------------------------------------------------------------------


class TestLooksTruncated:
    @pytest.mark.parametrize(
        "text",
        [
            "It ends here.",
            "Does it end?",
            "Wow!",
            "Trailing ellipsis…",
            "中文句子。",
            "全角感叹！",
            "全角问号？",
            "هل هذا؟",
            "यह वाक्य है।",
            "Quoted: “It is finished.”",
            "Parenthesized (see John 3:16.)",
            "Bold **end.**",
            "「完了。」",
            "Trailing spaces.   \n",
        ],
    )
    def test_complete_sentences_are_not_truncated(self, text):
        assert _looks_truncated(text) is False

    @pytest.mark.parametrize(
        "text",
        ["It ends mid", "cut off, and", "中文句子没有", "   ", "و", "यह वाक्य"],
    )
    def test_cut_off_text_is_truncated(self, text):
        assert _looks_truncated(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Cut off <!-- VERSES: John 3:16 -->",
            "Cut off <!-- FOLLOWUPS: a|b -->",
            "Cut off <!-- FOLLOWUPS: a|b",
        ],
    )
    def test_trailer_marker_means_complete(self, text):
        assert _looks_truncated(text) is False

    @pytest.mark.parametrize("lang", ALL_LANGS)
    def test_language_sentence_final_punctuation(self, lang):
        finals = {"zh": "。", "hi": "।", "ar": "؟"}
        done = f"{CITATIONS[lang][0].rstrip('.。।')}{finals.get(lang, '.')}"
        assert _looks_truncated(done) is False
        assert _looks_truncated(done[:-3]) is True


class TestUnterminatedTrailerRule:
    """Shared trailer-stripping table -- mirrored in streamRecovery.test.ts / AnswerTrailerTest.kt."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Plain text.", "Plain text."),
            ("Peace.\n<!-- FOLLOWUPS: What does this me", "Peace."),
            ("Peace. <!-- FOLLOW", "Peace."),
            ("Peace.\n<!--", "Peace."),
            ("Peace. <!-- note that", "Peace."),
            ("Peace. <!-", "Peace."),
            ("Peace. <!", "Peace."),
            ("Peace. <", "Peace."),
            ("A <!-- note --> B.", "A <!-- note --> B."),
            ("神爱世人（约翰福音3:16）。<!-- FOLLOW", "神爱世人（约翰福音3:16）。"),
            ("神爱世人。<", "神爱世人。"),
            ("الرب راعيّ. <!-", "الرب راعيّ."),
            ("الرب راعيّ. <!-- FOLLOWUPS: ماذا تعني", "الرب راعيّ."),
        ],
    )
    def test_table(self, text, expected):
        assert _UNTERMINATED_TRAILER.sub("", text) == expected

    @pytest.mark.parametrize("text", ["Cut off <!-- FOLLOW", "Cut off <!-", "Cut off <"])
    def test_partial_marker_only_text_is_truncated(self, text):
        assert _looks_truncated(text) is True

    @pytest.mark.asyncio
    async def test_finalize_strips_partial_opener(self, service):
        with patch.object(settings, "chat_follow_ups_enabled", False):
            result = await service.finalize(_req(assistant_text="Answer ends. <!-- FOLLOW"))
        assert result["corrected_message"] == "Answer ends."
        assert result["truncated"] is True  # only a partial marker => no complete marker seen


# ---------------------------------------------------------------------------
# finalize(): no double counting (metrics / safety samples)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFinalizeDoesNotDoubleCount:
    async def test_finalize_does_not_record_follow_up_outcome(self, service):
        with (
            patch.object(settings, "chat_follow_ups_enabled", False),
            patch("chat.service.chat_follow_ups_suppressed_counter") as counter,
            patch.object(ChatService, "_record_follow_ups_outcome") as record,
        ):
            await service.finalize(_req(assistant_text="God loves you."))
        record.assert_not_called()
        counter.add.assert_not_called()

    async def test_finalize_does_not_log_verse_extraction(self, service, caplog):
        with (
            caplog.at_level(logging.INFO),
            patch.object(settings, "chat_follow_ups_enabled", False),
        ):
            await service.finalize(_req(assistant_text="God loves you."))
        assert not [r for r in caplog.records if r.getMessage() == "Verse extraction completed"]

    async def test_build_completion_records_metrics_by_default(self, service):
        kwargs = {
            "request_history": [],
            "scripture_context": None,
            "translation": "kjv",
            "language": "en",
            "compassionate": False,
        }
        with (
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(ChatService, "_record_follow_ups_outcome") as record,
        ):
            await service._build_completion("God loves you.", **kwargs)
            assert record.call_count == 1
            await service._build_completion("God loves you.", record_metrics=False, **kwargs)
            assert record.call_count == 1

    async def test_finalize_safety_recheck_stores_no_sample_and_logs_info(self, service, caplog):
        blocked = MagicMock(
            allowed=False,
            reason="violence",
            categories={"Violence": 6},
            is_help_seeking=False,
            violated_categories=[],
            compassionate_response_needed=False,
        )
        safety_service = MagicMock()
        safety_service.check = AsyncMock(return_value=blocked)
        with (
            caplog.at_level(logging.INFO),
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(settings, "content_safety_enabled", True),
            patch("chat.service.get_content_safety_service", return_value=safety_service),
            patch("feedback.blocked_samples.record_blocked_sample", new=AsyncMock()) as record,
        ):
            result = await service.finalize(_req(assistant_text="Hope is a gift."))
        record.assert_not_awaited()
        assert "follow_ups" not in result
        assert not [r for r in caplog.records if "Content safety violation" in r.getMessage()]
        assert [
            r
            for r in caplog.records
            if r.levelno == logging.INFO and "Content safety re-check blocked" in r.getMessage()
        ]

    async def test_normal_safety_check_still_records_sample_and_warns(self, service, caplog):
        blocked = MagicMock(
            allowed=False,
            reason="violence",
            categories={"Violence": 6},
            is_help_seeking=False,
            violated_categories=[],
        )
        safety_service = MagicMock()
        safety_service.check = AsyncMock(return_value=blocked)
        with (
            caplog.at_level(logging.INFO),
            patch.object(settings, "content_safety_enabled", True),
            patch("chat.service.get_content_safety_service", return_value=safety_service),
            patch("feedback.blocked_samples.record_blocked_sample", new=AsyncMock()) as record,
        ):
            outcome = await service._check_content_safety("bad", "en", None)
        assert outcome.allowed is False
        record.assert_awaited_once()
        assert [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "Content safety violation" in r.getMessage()
        ]


# ---------------------------------------------------------------------------
# finalize(): verses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFinalizeVerses:
    @pytest.mark.parametrize("lang", ALL_LANGS)
    async def test_cross_language_verse_extraction_resolves_from_db(self, service, lang):
        text, expected = CITATIONS[lang]
        result = await service.finalize(_req(assistant_text=text, language=lang))
        assert result["verses_cited"] == [expected]
        assert result["resolved_verses"], f"{lang}: nothing resolved from the DB"
        assert all(v["book"] == "John" for v in result["resolved_verses"])
        # Citation spans are computed against the text the client renders.
        assert result["citations"]
        assert result["truncated"] is False
        assert "follow_ups" not in result
        assert "corrected_message" not in result

    async def test_range_resolves_every_verse(self, service):
        result = await service.finalize(_req(assistant_text="See (Romans 8:38-39)."))
        assert result["verses_cited"] == ["Romans 8:38-39"]
        assert [v["verse"] for v in result["resolved_verses"]] == [38, 39]

    @pytest.mark.parametrize("translation", ["kjv", "web"])
    async def test_version_faithful_uses_requested_translation(self, service, translation):
        result = await service.finalize(
            _req(assistant_text="(John 3:16).", preferred_translation=translation)
        )
        service.search_service.get_verse.assert_awaited()
        assert service.search_service.get_verse.await_args.args[-1] == translation
        verse = result["resolved_verses"][0]
        assert verse["translation"] == translation
        assert verse["text"].startswith(f"[{translation}]")

    async def test_wrong_quote_is_rewritten_from_db_not_client_text(self, service):
        service.search_service.get_verse = AsyncMock(
            return_value=_verse(text="For God so loved the world, that he gave his only Son")
        )
        wrong = '"For God hated nobody and gave nothing" (John 3:16)'
        result = await service.finalize(_req(assistant_text=wrong + "."))
        assert "corrected_message" in result
        assert "hated nobody" not in result["corrected_message"]
        assert result["corrections"]

    async def test_db_failure_still_returns_citations_without_resolved(self, service):
        service.search_service.get_verse = AsyncMock(side_effect=RuntimeError("db down"))
        result = await service.finalize(_req(assistant_text="Read (John 3:16)."))
        assert result["verses_cited"] == ["John 3:16"]
        assert result["resolved_verses"] == []

    async def test_build_failure_degrades_never_raises(self, service):
        with patch.object(service, "_build_completion", AsyncMock(side_effect=ValueError("x"))):
            result = await service.finalize(_req(assistant_text="Read (John 3:16)."))
        assert result["verses_cited"] == ["John 3:16"]
        assert result["resolved_verses"] == []
        assert "degraded" not in result and "type" not in result
        assert result["truncated"] is False


# ---------------------------------------------------------------------------
# finalize(): chips
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFinalizeChips:
    async def test_trailer_chips_returned_and_trailer_stripped(self, service, mock_llm):
        with patch.object(settings, "chat_follow_ups_enabled", True):
            result = await service.finalize(_req(assistant_text=f"God is near. {TWO_CHIPS}"))
        assert result["follow_ups"] == ["What does this mean for me?", "How can I pray about this?"]
        assert result["corrected_message"] == "God is near."
        assert result["truncated"] is False
        mock_llm.chat.assert_not_awaited()

    async def test_llm_chips_when_no_trailer(self, service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(
            content="<!-- FOLLOWUPS: Tell me more about hope|How do I pray for hope? -->",
            model="m",
            provider="p",
        )
        with (
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(service, "_check_content_safety", AsyncMock()) as safety,
        ):
            safety.return_value = MagicMock(allowed=True, compassionate=False)
            result = await service.finalize(_req(assistant_text="Hope is a gift.", language="de"))
        assert result["follow_ups"] == ["Tell me more about hope", "How do I pray for hope?"]
        kwargs = mock_llm.chat.await_args.kwargs
        assert kwargs["max_tokens"] <= 200
        assert kwargs["temperature"] == 0.3
        assert "German" in kwargs["messages"][0].content
        # The answer text is not echoed back as a "correction".
        assert "corrected_message" not in result

    async def test_llm_chips_citing_unseen_verse_are_dropped(self, service, mock_llm):
        mock_llm.chat.return_value = LLMResponse(
            content="<!-- FOLLOWUPS: What about Genesis 1:1?|What about Exodus 3:14? -->",
            model="m",
            provider="p",
        )
        with (
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(service, "_check_content_safety", AsyncMock()) as safety,
        ):
            safety.return_value = MagicMock(allowed=True, compassionate=False)
            result = await service.finalize(_req(assistant_text="Hope is a gift."))
        assert "follow_ups" not in result

    async def test_llm_failure_means_no_chips_not_error(self, service, mock_llm):
        mock_llm.chat.side_effect = RuntimeError("provider down")
        with (
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(service, "_check_content_safety", AsyncMock()) as safety,
        ):
            safety.return_value = MagicMock(allowed=True, compassionate=False)
            result = await service.finalize(_req(assistant_text="Hope is a gift."))
        assert "follow_ups" not in result
        assert result["verses_cited"] == []

    async def test_flag_off_skips_llm_entirely(self, service, mock_llm):
        with patch.object(settings, "chat_follow_ups_enabled", False):
            result = await service.finalize(_req(assistant_text="Hope is a gift."))
        mock_llm.chat.assert_not_awaited()
        assert "follow_ups" not in result

    async def test_compassionate_turn_gets_no_llm_chips(self, service, mock_llm):
        with (
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(service, "_check_content_safety", AsyncMock()) as safety,
        ):
            safety.return_value = MagicMock(allowed=True, compassionate=True)
            result = await service.finalize(_req(assistant_text="I am here with you."))
        mock_llm.chat.assert_not_awaited()
        assert "follow_ups" not in result

    async def test_unterminated_trailer_tail_is_stripped(self, service):
        with patch.object(settings, "chat_follow_ups_enabled", False):
            result = await service.finalize(
                _req(assistant_text="Answer ends. <!-- FOLLOWUPS: What does this me")
            )
        assert result["corrected_message"] == "Answer ends."
        assert result["truncated"] is False  # marker present => reply itself was complete

    async def test_truncated_flag_true_for_cut_off_reply(self, service):
        result = await service.finalize(_req(assistant_text="Love is patient, love is"))
        assert result["truncated"] is True


# ---------------------------------------------------------------------------
# Privacy / telemetry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_logs_and_counts_without_text(service, caplog):
    secret_msg = "my very private question zzzprivate"
    secret_text = "private answer qqqprivate (John 3:16)."
    with (
        caplog.at_level(logging.DEBUG),
        patch("chat.service.chat_finalize_counter") as counter,
    ):
        await service.finalize(
            _req(
                message=secret_msg, assistant_text=secret_text, reason="timeout", platform="android"
            )
        )
    records = [r for r in caplog.records if r.getMessage() == "Chat finalize requested"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].reason == "timeout" and records[0].platform == "android"
    blob = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "zzzprivate" not in blob and "qqqprivate" not in blob
    attrs = counter.add.call_args.args[1]
    assert attrs == {"reason": "timeout", "platform": "android", "outcome": "no_chips"}


def test_follow_ups_only_prompt_names_language_and_format():
    for lang in ALL_LANGS:
        prompt = get_follow_ups_only_prompt(lang)
        assert "<!-- FOLLOWUPS:" in prompt
        assert "{language_name}" not in prompt
    assert "Korean" in get_follow_ups_only_prompt("ko")


# ---------------------------------------------------------------------------
# chat_stream(): degraded completion (integration through the real stream)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestChatStreamDegraded:
    async def _run(self, service, mock_llm, tokens, *, fail_with=None):
        mock_llm.chat.return_value = LLMResponse(content="GENERAL", model="m", provider="p")

        async def stream(*a, **k):
            for t in tokens:
                yield t

        mock_llm.chat_stream = MagicMock(return_value=stream())
        request = ChatRequest(message="tell me about God's love", include_search=False)
        patches = [
            patch.object(settings, "chat_follow_ups_enabled", True),
            patch.object(settings, "content_filter_intent_detection", True),
            patch.object(service, "_check_content_safety", AsyncMock()),
        ]
        with patches[0], patches[1], patches[2] as safety:
            safety.return_value = MagicMock(
                allowed=True, compassionate=False, is_help_seeking=False
            )
            if fail_with:
                with patch.object(
                    service, "_ground_streamed_answer", AsyncMock(side_effect=fail_with)
                ):
                    return [c async for c in service.chat_stream(request)]
            return [c async for c in service.chat_stream(request)]

    async def test_post_processing_exception_yields_degraded_completion(self, service, mock_llm):
        chunks = await self._run(
            service,
            mock_llm,
            ["God loves you (John 3:16). ", TWO_CHIPS],
            fail_with=RuntimeError("grounding blew up"),
        )
        completion = chunks[-1]
        assert completion["type"] == "completion"
        assert completion["degraded"] is True
        assert completion["verses_cited"] == ["John 3:16"]
        assert completion["resolved_verses"] == []
        assert completion["follow_ups"] == [
            "What does this mean for me?",
            "How can I pray about this?",
        ]
        assert "FOLLOWUPS" not in completion["corrected_message"]
        assert not any(c["type"] == "error" for c in chunks)

    async def test_healthy_stream_has_no_degraded_flag(self, service, mock_llm):
        chunks = await self._run(service, mock_llm, ["God loves you (John 3:16). ", TWO_CHIPS])
        completion = chunks[-1]
        assert completion["type"] == "completion"
        assert "degraded" not in completion
        assert completion["resolved_verses"]
        assert completion["verses_cited"] == ["John 3:16"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    reset_rate_limiter()
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    app.dependency_overrides[get_embedding_provider] = lambda: MagicMock()
    app.dependency_overrides[get_llm_provider] = lambda: MagicMock()
    with (
        patch.object(settings, "rate_limit_enabled", True),
        patch.object(settings, "rate_limit_backend", "memory"),
        patch.object(settings, "turnstile_enabled", True),  # finalize must NOT need a token
        patch.object(settings, "chat_finalize_rate_limit_per_minute", 2),
    ):
        yield TestClient(app)
    app.dependency_overrides.clear()
    reset_rate_limiter()


def _body(**over):
    body = {"message": "hello", "assistant_text": "Hi there.", "reason": "eof"}
    body.update(over)
    return body


class TestFinalizeRoute:
    def test_contract_happy_path_and_omitted_fields(self, api_client):
        completion = {
            "verses_cited": ["John 3:16"],
            "resolved_verses": [_verse().model_dump()],
            "citations": [{"reference": "John 3:16", "start": 0, "end": 4}],
            "truncated": False,
        }
        with patch("routes.chat.ChatService") as cls:
            cls.return_value.finalize = AsyncMock(return_value=completion)
            res = api_client.post("/api/v1/chat/finalize", json=_body())
        assert res.status_code == 200
        data = res.json()
        assert data["verses_cited"] == ["John 3:16"]
        assert data["truncated"] is False
        # Optional fields are absent (not null) when empty.
        assert "corrected_message" not in data
        assert "corrections" not in data
        assert "follow_ups" not in data

    def test_follow_ups_and_corrected_message_present_when_set(self, api_client):
        completion = {
            "verses_cited": [],
            "resolved_verses": [],
            "citations": [],
            "follow_ups": ["a", "b"],
            "corrected_message": "clean",
            "truncated": True,
        }
        with patch("routes.chat.ChatService") as cls:
            cls.return_value.finalize = AsyncMock(return_value=completion)
            data = api_client.post("/api/v1/chat/finalize", json=_body()).json()
        assert data["follow_ups"] == ["a", "b"] and data["corrected_message"] == "clean"
        assert data["truncated"] is True

    def test_service_exception_degrades_to_200(self, api_client):
        with patch("routes.chat.ChatService") as cls:
            cls.return_value.finalize = AsyncMock(side_effect=RuntimeError("boom"))
            res = api_client.post("/api/v1/chat/finalize", json=_body(assistant_text="cut off mid"))
        assert res.status_code == 200
        assert res.json()["truncated"] is True
        assert res.json()["verses_cited"] == []

    @pytest.mark.parametrize(
        "bad",
        [
            {"reason": "nope"},
            {"assistant_text": ""},
            {"message": ""},
            {"extra_field": 1},
            {"platform": "ios"},
        ],
    )
    def test_validation_422(self, api_client, bad):
        assert api_client.post("/api/v1/chat/finalize", json=_body(**bad)).status_code == 422

    def test_rate_limit_429(self, api_client):
        with patch("routes.chat.ChatService") as cls:
            cls.return_value.finalize = AsyncMock(
                return_value={
                    "verses_cited": [],
                    "resolved_verses": [],
                    "citations": [],
                    "truncated": False,
                }
            )
            codes = [
                api_client.post("/api/v1/chat/finalize", json=_body()).status_code for _ in range(3)
            ]
        assert codes == [200, 200, 429]

    def test_content_filter_400(self, api_client):
        with (
            patch.object(settings, "content_filter_enabled", True),
            patch("routes.chat.ChatService"),
            patch("utils.security.get_content_filter") as getf,
        ):
            getf.return_value.check.return_value = (False, MagicMock(value="spam"), "blocked")
            res = api_client.post("/api/v1/chat/finalize", json=_body())
        assert res.status_code == 400


def _drain(route_response):
    async def go():
        out = []
        async for part in route_response.body_iterator:
            out.append(part)
        return out

    return asyncio.run(go())


def _call_stream_route(chunks_factory):
    from routes.chat import chat_stream

    request = ChatRequest(message="hello")
    http = MagicMock()
    http.headers = {}
    with (
        patch("routes.chat.ChatService") as cls,
        patch("routes.chat.track_session", new_callable=AsyncMock),
    ):
        cls.return_value.chat_stream = chunks_factory
        response = asyncio.run(chat_stream(request, http, AsyncMock(), AsyncMock(), AsyncMock()))
    return response


class TestStreamRouteSignals:
    def test_error_after_content_is_partial_with_message_id(self):
        async def chunks(request, client_country=None):
            yield {"type": "metadata", "message_id": "mid-1"}
            yield {"type": "content", "content": "Hello"}
            raise ValueError("boom")

        response = _call_stream_route(chunks)
        frames = [json.loads(p[6:]) for p in _drain(response) if p.startswith("data: {")]
        err = frames[-1]
        assert err["type"] == "error"
        assert err["partial"] is True and err["message_id"] == "mid-1"

    def test_error_before_content_has_no_partial(self):
        async def chunks(request, client_country=None):
            yield {"type": "metadata", "message_id": "mid-1"}
            raise ValueError("boom")
            yield  # pragma: no cover

        response = _call_stream_route(chunks)
        frames = [json.loads(p[6:]) for p in _drain(response) if p.startswith("data: {")]
        assert frames[-1]["type"] == "error"
        assert "partial" not in frames[-1] and "message_id" not in frames[-1]

    def test_disconnect_is_logged_and_counted_without_text(self, caplog):
        async def chunks(request, client_country=None):
            yield {"type": "metadata", "message_id": "mid-9"}
            yield {"type": "content", "content": "secret words zzzsecret"}
            await asyncio.sleep(3600)

        response = _call_stream_route(chunks)

        async def go():
            gen = response.body_iterator
            await gen.__anext__()  # metadata
            await gen.__anext__()  # content
            await gen.aclose()  # the client went away

        with (
            caplog.at_level(logging.WARNING),
            patch("routes.chat.chat_stream_client_disconnected_counter") as counter,
        ):
            asyncio.run(go())
        records = [
            r
            for r in caplog.records
            if r.getMessage() == "Chat stream client disconnected before completion"
        ]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert records[0].content_chars == len("secret words zzzsecret")
        assert records[0].completion_sent is False
        assert "zzzsecret" not in " ".join(str(r.__dict__) for r in caplog.records)
        counter.add.assert_called_once_with(1, {"completion_sent": "false"})

    def test_cancelled_error_is_logged_counted_and_reraised(self, caplog):
        async def chunks(request, client_country=None):
            yield {"type": "metadata", "message_id": "mid-c"}
            yield {"type": "content", "content": "partial words"}
            await asyncio.sleep(3600)

        response = _call_stream_route(chunks)

        async def go():
            gen = response.body_iterator
            await gen.__anext__()
            await gen.__anext__()
            with pytest.raises(asyncio.CancelledError):
                await gen.athrow(asyncio.CancelledError())

        with (
            caplog.at_level(logging.INFO),
            patch("routes.chat.chat_stream_client_disconnected_counter") as counter,
        ):
            asyncio.run(go())
        records = [
            r
            for r in caplog.records
            if r.getMessage() == "Chat stream client disconnected before completion"
        ]
        assert len(records) == 1 and records[0].levelno == logging.WARNING
        counter.add.assert_called_once_with(1, {"completion_sent": "false"})

    @pytest.mark.parametrize("exc", [asyncio.CancelledError, GeneratorExit])
    def test_disconnect_after_completion_is_info_without_counter(self, caplog, exc):
        async def chunks(request, client_country=None):
            yield {"type": "metadata", "message_id": "mid-d"}
            yield {"type": "content", "content": "all of it"}
            yield {"type": "completion", "verses_cited": []}
            await asyncio.sleep(3600)

        response = _call_stream_route(chunks)

        async def go():
            gen = response.body_iterator
            for _ in range(3):
                await gen.__anext__()
            if exc is GeneratorExit:
                await gen.aclose()
            else:
                with pytest.raises(asyncio.CancelledError):
                    await gen.athrow(asyncio.CancelledError())

        with (
            caplog.at_level(logging.INFO),
            patch("routes.chat.chat_stream_client_disconnected_counter") as counter,
        ):
            asyncio.run(go())
        assert not [
            r
            for r in caplog.records
            if r.levelno >= logging.WARNING and "disconnected" in r.getMessage()
        ]
        info = [
            r
            for r in caplog.records
            if r.getMessage() == "Chat stream client disconnected after completion"
        ]
        assert len(info) == 1 and info[0].levelno == logging.INFO
        counter.add.assert_not_called()

    def test_normal_stream_does_not_log_disconnect(self, caplog):
        async def chunks(request, client_country=None):
            yield {"type": "metadata", "message_id": "m"}
            yield {"type": "content", "content": "ok"}
            yield {"type": "completion", "verses_cited": []}

        response = _call_stream_route(chunks)
        with caplog.at_level(logging.WARNING):
            parts = _drain(response)
        assert parts[-1] == "data: [DONE]\n\n"
        assert not [r for r in caplog.records if "disconnected" in r.getMessage()]

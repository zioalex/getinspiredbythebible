"""BITB-251: the deterministic crisis-card path through chat() and chat_stream().

Integration tests (mocked safety / LLM / search) -- not pure-function tests -- because the
card must survive every return path of both entry points and must be the FIRST stream event.
"""

import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.prompts import get_blocked_response
from chat.service import ChatRequest, ChatResponse, ChatService, _SafetyOutcome
from providers.base import LLMResponse

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]

# Bible-narrative "kill" phrasing per language: must never trigger the card.
NARRATIVE = {
    "en": "Why did Cain kill Abel in the book of Genesis?",
    "it": "Perché Caino uccise Abele nel libro della Genesi?",
    "de": "Warum hat Kain Abel im Buch Genesis getötet?",
    "es": "¿Por qué Caín mató a Abel en el libro del Génesis?",
    "fr": "Pourquoi Caïn a-t-il tué Abel dans le livre de la Genèse ?",
    "pt": "Por que Caim matou Abel no livro de Gênesis?",
    "ar": "لماذا قتل قايين هابيل في سفر التكوين؟",
    "ru": "Почему Каин убил Авеля в книге Бытия?",
    "zh": "为什么该隐在创世记中杀了亚伯？",
    "hi": "उत्पत्ति की पुस्तक में कैन ने हाबिल को क्यों मार डाला?",
    "ko": "창세기에서 가인은 왜 아벨을 죽였나요?",
}

SELF_HARM_ALLOWED = _SafetyOutcome(
    allowed=True,
    compassionate=True,
    reason="possible_help_seeking (fallback)",
    categories={},
    is_help_seeking=True,
)
SELF_HARM_BLOCKED = _SafetyOutcome(
    allowed=False, compassionate=False, reason="self_harm_instructions_detected", categories={}
)
AMBIGUOUS_BLOCKED = _SafetyOutcome(
    allowed=False,
    compassionate=False,
    reason="self_harm_with_violence (fallback)",
    categories={},
    is_help_seeking=True,
)
THREAT_BLOCKED = _SafetyOutcome(
    allowed=False, compassionate=False, reason="violence_or_threat_detected", categories={}
)
CLEAN = _SafetyOutcome(allowed=True, compassionate=False, reason="clean", categories={})
DIRECTED_BLOCKED = _SafetyOutcome(
    allowed=False,
    compassionate=False,
    reason="keyword_violation:directed_harm (fallback)",
    categories={},
)

# (outcome, expected kind) for every trigger outcome.
TRIGGERS = [
    pytest.param(SELF_HARM_ALLOWED, "self_harm", id="compassionate"),
    pytest.param(SELF_HARM_BLOCKED, "self_harm", id="self_harm_blocked"),
    pytest.param(AMBIGUOUS_BLOCKED, "self_harm", id="murder_suicide_ambiguous"),
    pytest.param(THREAT_BLOCKED, "threat_to_others", id="threat_to_others"),
]
BLOCKED_TRIGGERS = [t for t in TRIGGERS if not t.values[0].allowed]
# Paths reachable after an ALLOWED safety outcome.
ALLOWED_PATHS = ["off_topic", "clarification", "scripture_unavailable", "normal"]


def _llm():
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(content="A gentle reply.", model="m", provider="p")
    )

    async def _stream(**_kwargs):
        for token in ("A ", "gentle ", "reply."):
            yield token

    llm.chat_stream = MagicMock(side_effect=lambda **kw: _stream(**kw))
    return llm


def _service():
    emb = MagicMock()
    emb.embed = AsyncMock()
    return ChatService(MagicMock(), _llm(), emb)


def _request(language="en", message="I am struggling", **kwargs):
    return ChatRequest(message=message, language=language, **kwargs)


def _patched(service, safety, path="normal", search_error=None):
    """Patch everything around the crisis path for one return path; returns the ExitStack."""
    stack = ExitStack()
    stack.enter_context(
        patch.object(service, "_check_content_safety", AsyncMock(return_value=safety))
    )
    intent = {"off_topic": "OFF_TOPIC", "clarification": "NEEDS_CLARIFICATION"}.get(path, "COMFORT")
    stack.enter_context(patch.object(service, "_detect_intent", AsyncMock(return_value=intent)))
    stack.enter_context(
        patch.object(
            service, "_wants_clarification", MagicMock(return_value=path == "clarification")
        )
    )
    search = AsyncMock(
        return_value=(None, ""), side_effect=search_error
    )  # side_effect None -> return_value
    stack.enter_context(patch.object(service, "_search_scripture", search))
    stack.enter_context(
        patch.object(
            service,
            "_scripture_grounding_unavailable",
            MagicMock(return_value=path == "scripture_unavailable"),
        )
    )
    stack.enter_context(
        patch.object(
            service,
            "_apply_verse_grounding",
            AsyncMock(side_effect=lambda body, *a, **k: (body, [])),
        )
    )
    stack.enter_context(patch("chat.service.settings.content_filter_intent_detection", True))
    stack.enter_context(patch("chat.service.get_translation_info", return_value=None))
    return stack


async def _collect_stream(service, request, **kwargs):
    events = []
    async for event in service.chat_stream(request, **kwargs):
        events.append(event)
    return events


def _text(events):
    return "".join(e["content"] for e in events if e["type"] == "content")


# ---------------------------------------------------------------------------
# Blocking chat(): every trigger x every return path carries crisis_resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("safety,kind", BLOCKED_TRIGGERS)
async def test_chat_blocked_paths_carry_card_in_every_language(safety, kind, language):
    service = _service()
    with _patched(service, safety):
        response = await service.chat(_request(language), client_country="IT")
    assert isinstance(response, ChatResponse)
    assert response.provider == "content_safety"
    assert response.crisis_resources["kind"] == kind
    assert response.crisis_resources["country"] == "IT"
    assert response.crisis_resources["country_source"] == "ip"
    service.llm.chat.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ALLOWED_PATHS)
@pytest.mark.parametrize("language", LANGUAGES)
async def test_chat_allowed_compassionate_paths_carry_card(path, language):
    service = _service()
    # Clarification is normally suppressed on a compassionate turn; force the branch to
    # prove the card would still travel with it.
    with _patched(service, SELF_HARM_ALLOWED, path=path):
        response = await service.chat(_request(language), client_country="DE")
    assert response.crisis_resources is not None, path
    assert response.crisis_resources["kind"] == "self_harm"
    assert response.crisis_resources["country"] == "DE"
    assert response.crisis_resources["emergency"] == {"number": "112"}


@pytest.mark.asyncio
async def test_chat_threat_uses_police_number_where_registry_distinguishes():
    service = _service()
    with _patched(service, THREAT_BLOCKED):
        response = await service.chat(_request(), client_country="DE")
    assert response.crisis_resources["kind"] == "threat_to_others"
    assert response.crisis_resources["emergency"] == {"number": "110"}


@pytest.mark.asyncio
async def test_chat_directed_harm_gets_no_card():
    service = _service()
    with _patched(service, DIRECTED_BLOCKED):
        response = await service.chat(_request("en", "go kill yourself"), client_country="US")
    assert response.crisis_resources is None
    assert response.provider == "content_safety"


# ---------------------------------------------------------------------------
# Streaming: crisis_resources is the FIRST event, every trigger x path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("safety,kind", TRIGGERS)
async def test_stream_card_is_first_event_for_every_trigger(safety, kind, language):
    service = _service()
    path = "normal"
    with _patched(service, safety, path=path):
        events = await _collect_stream(service, _request(language), client_country="FR")
    assert events[0]["type"] == "crisis_resources"
    assert events[0]["resources"]["kind"] == kind
    assert events[0]["resources"]["country"] == "FR"
    assert "metadata" in [e["type"] for e in events[1:]]
    assert events[-1]["type"] == "completion"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ALLOWED_PATHS)
@pytest.mark.parametrize("language", LANGUAGES)
async def test_stream_card_is_first_event_on_every_allowed_path(path, language):
    service = _service()
    with _patched(service, SELF_HARM_ALLOWED, path=path):
        events = await _collect_stream(service, _request(language), client_country="IT")
    types = [e["type"] for e in events]
    assert types[0] == "crisis_resources", path
    assert types.count("crisis_resources") == 1
    assert types.index("metadata") > 0
    assert events[-1]["type"] == "completion"


@pytest.mark.asyncio
async def test_stream_blocked_path_makes_no_llm_call_and_still_sends_text():
    service = _service()
    with _patched(service, THREAT_BLOCKED):
        events = await _collect_stream(service, _request("en"), client_country="US")
    assert events[0]["type"] == "crisis_resources"
    assert events[0]["resources"]["kind"] == "threat_to_others"
    service.llm.chat_stream.assert_not_called()
    assert _text(events)


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_stream_directed_harm_gets_no_card(language):
    service = _service()
    with _patched(service, DIRECTED_BLOCKED):
        events = await _collect_stream(service, _request(language))
    assert "crisis_resources" not in [e["type"] for e in events]


# ---------------------------------------------------------------------------
# The card is delivered even if retrieval or the LLM fails afterwards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_card_delivered_when_search_raises():
    service = _service()
    events = []
    with _patched(service, SELF_HARM_ALLOWED, search_error=RuntimeError("db down")):
        with pytest.raises(RuntimeError, match="db down"):
            async for event in service.chat_stream(_request(), client_country="IT"):
                events.append(event)
    assert [e["type"] for e in events] == ["crisis_resources"]


@pytest.mark.asyncio
async def test_stream_card_delivered_when_llm_raises():
    service = _service()

    async def _boom(**_kwargs):
        raise RuntimeError("llm down")
        yield  # pragma: no cover

    service.llm.chat_stream = MagicMock(side_effect=lambda **kw: _boom(**kw))
    events = []
    with _patched(service, SELF_HARM_ALLOWED):
        with pytest.raises(RuntimeError, match="llm down"):
            async for event in service.chat_stream(_request(), client_country="IT"):
                events.append(event)
    assert events[0]["type"] == "crisis_resources"
    assert events[1]["type"] == "metadata"


@pytest.mark.asyncio
async def test_stream_card_delivered_when_llm_raises_mid_stream():
    service = _service()

    async def _partial(**_kwargs):
        yield "I am "
        raise RuntimeError("cut off")

    service.llm.chat_stream = MagicMock(side_effect=lambda **kw: _partial(**kw))
    events = []
    with _patched(service, SELF_HARM_ALLOWED):
        with pytest.raises(RuntimeError):
            async for event in service.chat_stream(_request(), client_country="IT"):
                events.append(event)
    assert events[0]["type"] == "crisis_resources"
    assert any(e["type"] == "content" for e in events)


@pytest.mark.asyncio
async def test_stream_card_delivered_when_intent_detection_raises():
    service = _service()
    events = []
    with _patched(service, SELF_HARM_ALLOWED):
        service._detect_intent = AsyncMock(side_effect=RuntimeError("intent down"))
        with pytest.raises(RuntimeError):
            async for event in service.chat_stream(_request(), client_country="IT"):
                events.append(event)
    assert [e["type"] for e in events] == ["crisis_resources"]


@pytest.mark.asyncio
async def test_registry_failure_degrades_to_international_link_not_an_error():
    service = _service()
    with (
        _patched(service, SELF_HARM_ALLOWED),
        patch("chat.service.build_crisis_payload", side_effect=ValueError("corrupt registry")),
    ):
        events = await _collect_stream(service, _request(), client_country="IT")
    card = events[0]["resources"]
    assert events[0]["type"] == "crisis_resources"
    assert card["international_url"] == "https://findahelpline.com"
    assert card["emergency"] is None and card["lines"] == []


# ---------------------------------------------------------------------------
# Non-crisis turns never get the card (Bible-narrative "kill" phrasing, 11 languages)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_bible_narrative_kill_phrasing_gets_no_card(language):
    service = _service()
    request = _request(language, NARRATIVE[language])
    with _patched(service, CLEAN):
        response = await service.chat(request, client_country="IT")
    assert response.crisis_resources is None

    service = _service()
    with _patched(service, CLEAN):
        events = await _collect_stream(service, request, client_country="IT")
    assert "crisis_resources" not in [e["type"] for e in events]
    assert events[0]["type"] == "metadata"


@pytest.mark.asyncio
async def test_no_counter_increment_on_non_crisis_turn():
    service = _service()
    with _patched(service, CLEAN), patch("chat.service.chat_crisis_card_shown_counter") as counter:
        await service.chat(_request())
    counter.add.assert_not_called()


# ---------------------------------------------------------------------------
# Markdown fallback: present without supports_crisis_card, absent with it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("safety", [SELF_HARM_BLOCKED, AMBIGUOUS_BLOCKED, THREAT_BLOCKED])
async def test_blocked_text_has_markdown_fallback_only_for_old_clients(safety, language):
    base = get_blocked_response(safety.reason, language)

    service = _service()
    with _patched(service, safety):
        old = await service.chat(_request(language), client_country="IT")
    assert old.message.startswith(base)
    assert "https://findahelpline.com" in old.message
    assert "+39 02 2327 2327" in old.message
    assert "112" in old.message

    service = _service()
    with _patched(service, safety):
        new = await service.chat(_request(language, supports_crisis_card=True), client_country="IT")
    assert new.message == base
    assert "findahelpline" not in new.message
    assert new.crisis_resources is not None  # the card still ships either way


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_stream_blocked_fallback_flag(language):
    service = _service()
    with _patched(service, SELF_HARM_BLOCKED):
        old = await _collect_stream(service, _request(language), client_country="US")
    service = _service()
    with _patched(service, SELF_HARM_BLOCKED):
        new = await _collect_stream(
            service, _request(language, supports_crisis_card=True), client_country="US"
        )
    assert "988" in _text(old)
    assert "988" not in _text(new)
    assert _text(new).strip() == get_blocked_response(SELF_HARM_BLOCKED.reason, language).strip()


@pytest.mark.asyncio
async def test_compassionate_llm_text_is_never_modified_by_fallback():
    service = _service()
    with _patched(service, SELF_HARM_ALLOWED):
        response = await service.chat(_request(), client_country="US")
    assert response.message == "A gentle reply."


# ---------------------------------------------------------------------------
# Country plumbing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_region_beats_cloudflare_country():
    service = _service()
    with _patched(service, SELF_HARM_ALLOWED):
        response = await service.chat(
            _request(region="br", region_override=True), client_country="IT"
        )
    assert response.crisis_resources["country"] == "BR"
    assert response.crisis_resources["country_source"] == "override"


@pytest.mark.asyncio
async def test_locale_region_used_when_cloudflare_unknown():
    service = _service()
    with _patched(service, SELF_HARM_ALLOWED):
        response = await service.chat(_request("de", region="AT"), client_country="XX")
    assert response.crisis_resources["country"] == "AT"
    assert response.crisis_resources["country_source"] == "locale"
    assert response.crisis_resources["lines"][0]["phone"] == "142"


@pytest.mark.asyncio
async def test_language_default_and_arabic_none():
    service = _service()
    with _patched(service, SELF_HARM_ALLOWED):
        it = await service.chat(_request("it"))
    assert it.crisis_resources["country"] == "IT"
    assert it.crisis_resources["country_source"] == "language_default"
    service = _service()
    with _patched(service, SELF_HARM_ALLOWED):
        ar = await service.chat(_request("ar"))
    assert ar.crisis_resources["country"] is None
    assert ar.crisis_resources["country_source"] == "none"
    assert ar.crisis_resources["emergency"] is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("it", "IT"),
        ("IT", "IT"),
        ("ITA", None),
        ("en-US", None),
        ("1", None),
        ("", None),
        (None, None),
    ],
)
def test_chat_request_region_validation_never_rejects(value, expected):
    assert ChatRequest(message="hi", region=value).region == expected


def test_chat_request_defaults():
    request = ChatRequest(message="hi")
    assert request.region is None
    assert request.region_override is False
    assert request.supports_crisis_card is False


# ---------------------------------------------------------------------------
# Telemetry (never message text)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "safety,path_attr,kind",
    [
        (SELF_HARM_ALLOWED, "llm", "self_harm"),
        (SELF_HARM_BLOCKED, "blocked", "self_harm"),
        (THREAT_BLOCKED, "blocked", "threat_to_others"),
    ],
)
async def test_counter_attributes(safety, path_attr, kind):
    service = _service()
    secret = "super secret user text"
    with (
        _patched(service, safety),
        patch("chat.service.chat_crisis_card_shown_counter") as counter,
    ):
        await service.chat(_request("it", secret), client_country="IT")
    counter.add.assert_called_once_with(
        1,
        {"kind": kind, "language": "it", "country_source": "ip", "path": path_attr},
    )
    assert secret not in str(counter.add.call_args)


@pytest.mark.asyncio
async def test_crisis_logging_never_contains_message_text(caplog):
    service = _service()
    secret = "my very private sentence"
    with _patched(service, SELF_HARM_ALLOWED), caplog.at_level("DEBUG"):
        await service.chat(_request("en", secret), client_country="IT")
    crisis_logs = [r for r in caplog.records if r.getMessage() == "Crisis card attached"]
    assert crisis_logs
    for record in crisis_logs:
        assert secret not in repr(record.__dict__)

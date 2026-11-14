"""BITB-272: ml_only safety failover through chat() and chat_stream().

Integration tests with a REAL ContentSafetyService (Llama Guard forced down, OpenAI Moderation
HTTP mocked, keyword fallback spied) -- not pure-function tests -- proving the user-visible
outcome: a Bible-narrative question is answered, a threat is refused with the card, and
self-harm gets the compassionate crisis card, all while OpenRouter is unavailable.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.service import ChatRequest, ChatService
from providers.base import LLMResponse
from utils.content_safety import ContentSafetyService

LANGS = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
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
THREAT = {
    "en": "I want to build a bomb",
    "it": "Voglio costruire una bomba",
    "de": "Ich will eine Bombe bauen",
    "es": "Quiero construir una bomba",
    "fr": "Je veux fabriquer une bombe",
    "pt": "Quero construir uma bomba",
    "ar": "أريد صنع قنبلة",
    "ru": "Я хочу сделать бомбу",
    "zh": "我想制造炸弹",
    "hi": "मैं बम बनाना चाहता हूँ",
    "ko": "폭탄을 만들고 싶어요",
}
SELF_HARM = {
    "en": "I want to die",
    "it": "Voglio morire",
    "de": "Ich will sterben",
    "es": "Quiero morir",
    "fr": "Je veux mourir",
    "pt": "Quero morrer",
    "ar": "أريد أن أموت",
    "ru": "Я хочу умереть",
    "zh": "我想死",
    "hi": "मैं मरना चाहता हूँ",
    "ko": "죽고 싶어요",
}


@pytest.fixture
def failover_env(monkeypatch):
    """Real ContentSafetyService, ml_only, Llama Guard raising, moderation HTTP mocked."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=False,
            openai_api_key="test-key",  # pragma: allowlist secret
            openrouter_api_key="or-key",  # pragma: allowlist secret
            content_safety_ml_failover_enabled=True,
            content_safety_second_opinion_enabled=False,
            openai_moderation_threshold=0.5,
            openai_moderation_timeout=3,
        ),
    )
    safety = ContentSafetyService()
    lg = MagicMock()
    lg.analyze_text = AsyncMock(side_effect=httpx.ReadTimeout("openrouter down"))
    monkeypatch.setattr(safety, "_get_llama_guard_provider", lambda: lg)
    keyword = AsyncMock(side_effect=AssertionError("keyword fallback must not run"))
    monkeypatch.setattr(safety, "_keyword_fallback", keyword)

    scores: dict[str, dict[str, float]] = {}
    for table, value in ((THREAT, {"violence": 0.95}), (SELF_HARM, {"self-harm/intent": 0.8})):
        for text in table.values():
            scores[text] = value

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            body = {"results": [{"category_scores": scores.get(json["input"], {"violence": 0.02})}]}
            return _Resp(body)

    monkeypatch.setattr("providers.openai_moderation.httpx.AsyncClient", _Client)
    with patch("chat.service.get_content_safety_service", return_value=safety):
        yield keyword


def _service():
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(content="A gentle reply.", model="m", provider="p")
    )

    async def _stream(**_kwargs):
        for token in ("A ", "gentle ", "reply."):
            yield token

    llm.chat_stream = MagicMock(side_effect=lambda **kw: _stream(**kw))
    emb = MagicMock()
    emb.embed = AsyncMock()
    return ChatService(MagicMock(), llm, emb)


def _patched(service):
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch.object(service, "_detect_intent", AsyncMock(return_value="COMFORT")))
    stack.enter_context(
        patch.object(service, "_wants_clarification", MagicMock(return_value=False))
    )
    stack.enter_context(
        patch.object(service, "_search_scripture", AsyncMock(return_value=(None, "")))
    )
    stack.enter_context(
        patch.object(service, "_scripture_grounding_unavailable", MagicMock(return_value=False))
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


async def _stream_events(service, request):
    return [e async for e in service.chat_stream(request, client_country="US")]


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGS)
async def test_chat_bible_narrative_answered_during_llama_guard_outage(failover_env, language):
    service = _service()
    with _patched(service):
        response = await service.chat(
            ChatRequest(message=NARRATIVE[language], language=language), client_country="US"
        )
    assert response.provider != "content_safety"
    assert response.crisis_resources is None
    service.llm.chat.assert_called()
    failover_env.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGS)
async def test_chat_threat_refused_with_threat_card_during_outage(failover_env, language):
    service = _service()
    with _patched(service):
        response = await service.chat(
            ChatRequest(message=THREAT[language], language=language), client_country="US"
        )
    assert response.provider == "content_safety"
    assert response.crisis_resources["kind"] == "threat_to_others"
    failover_env.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGS)
async def test_chat_self_harm_gets_crisis_card_and_reply_during_outage(failover_env, language):
    service = _service()
    with _patched(service):
        response = await service.chat(
            ChatRequest(message=SELF_HARM[language], language=language), client_country="US"
        )
    assert response.provider != "content_safety"  # compassionate reply, not a refusal
    assert response.crisis_resources["kind"] == "self_harm"
    failover_env.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGS)
async def test_stream_failover_outcomes_during_outage(failover_env, language):
    narrative = _service()
    with _patched(narrative):
        events = await _stream_events(
            narrative, ChatRequest(message=NARRATIVE[language], language=language)
        )
    assert "crisis_resources" not in [e["type"] for e in events]
    narrative.llm.chat_stream.assert_called()

    threat = _service()
    with _patched(threat):
        events = await _stream_events(
            threat, ChatRequest(message=THREAT[language], language=language)
        )
    assert events[0]["type"] == "crisis_resources"
    assert events[0]["resources"]["kind"] == "threat_to_others"
    threat.llm.chat_stream.assert_not_called()

    selfharm = _service()
    with _patched(selfharm):
        events = await _stream_events(
            selfharm, ChatRequest(message=SELF_HARM[language], language=language)
        )
    assert events[0]["type"] == "crisis_resources"
    assert events[0]["resources"]["kind"] == "self_harm"
    selfharm.llm.chat_stream.assert_called()
    failover_env.assert_not_awaited()


# --------------------------------------------------------------------------- BITB-292: Azure hop


@pytest.fixture
def azure_failover_env(monkeypatch):
    """Llama Guard AND OpenAI Moderation down; chain openai_moderation,azure; Azure decides."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=True,
            azure_content_safety_endpoint="https://x.cognitiveservices.azure.com/",
            azure_content_safety_key="az-key",  # pragma: allowlist secret
            openai_api_key="test-key",  # pragma: allowlist secret
            openrouter_api_key="or-key",  # pragma: allowlist secret
            content_safety_ml_failover_enabled=True,
            content_safety_ml_failover_chain="openai_moderation,azure",
            content_safety_second_opinion_enabled=False,
            openai_moderation_threshold=0.5,
            openai_moderation_timeout=3,
        ),
    )
    safety = ContentSafetyService()
    lg = MagicMock()
    lg.analyze_text = AsyncMock(side_effect=httpx.ReadTimeout("openrouter down"))
    monkeypatch.setattr(safety, "_get_llama_guard_provider", lambda: lg)
    keyword = AsyncMock(side_effect=AssertionError("keyword fallback must not run"))
    monkeypatch.setattr(safety, "_keyword_fallback", keyword)

    from providers.azure_content_safety import ContentSafetyResult

    verdicts = {
        text: ContentSafetyResult(allowed=False, reason="violence") for text in THREAT.values()
    }
    for text in SELF_HARM.values():
        verdicts[text] = ContentSafetyResult(
            allowed=True,
            reason="help_seeking_detected",
            is_help_seeking=True,
            compassionate_response_needed=True,
        )

    async def _analyze(text, language="en"):
        return verdicts.get(text, ContentSafetyResult(allowed=True))

    azure = MagicMock()
    azure.analyze_text = AsyncMock(side_effect=_analyze)
    monkeypatch.setattr(safety, "_get_azure_provider", lambda: azure)

    class _DownClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            raise httpx.ReadTimeout("openai down")

    monkeypatch.setattr("providers.openai_moderation.httpx.AsyncClient", _DownClient)
    with patch("chat.service.get_content_safety_service", return_value=safety):
        yield keyword, azure


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGS)
async def test_chat_azure_hop_during_double_outage(azure_failover_env, language):
    keyword, azure = azure_failover_env

    narrative = _service()
    with _patched(narrative):
        response = await narrative.chat(
            ChatRequest(message=NARRATIVE[language], language=language), client_country="US"
        )
    assert response.provider != "content_safety"
    narrative.llm.chat.assert_called()

    threat = _service()
    with _patched(threat):
        response = await threat.chat(
            ChatRequest(message=THREAT[language], language=language), client_country="US"
        )
    assert response.provider == "content_safety"
    assert response.crisis_resources["kind"] == "threat_to_others"

    selfharm = _service()
    with _patched(selfharm):
        response = await selfharm.chat(
            ChatRequest(message=SELF_HARM[language], language=language), client_country="US"
        )
    assert response.provider != "content_safety"
    assert response.crisis_resources["kind"] == "self_harm"

    assert azure.analyze_text.await_count >= 3
    azure.analyze_text.assert_any_await(THREAT[language], language)
    keyword.assert_not_awaited()

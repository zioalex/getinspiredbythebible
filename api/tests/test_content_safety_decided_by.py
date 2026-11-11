"""BITB-291: every ContentSafetyCheckResult says which stage decided it.

The synthetic ML-path probe needs to tell "Llama Guard decided" apart from "the keyword
fallback decided" (which still blocks a bomb threat but means the ML path is down).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.azure_content_safety import ContentSafetyResult
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
DEFAULT_UNSAFE = "I want to build a bomb to blow up a building"
DEFAULT_BENIGN = "Why did Cain kill Abel?"


def _settings(monkeypatch, **overrides):
    values = {
        "content_safety_enabled": True,
        "content_safety_mode": "ml_only",
        "azure_content_safety_enabled": False,
        "azure_content_safety_endpoint": None,
        "azure_content_safety_key": None,
        "azure_content_safety_threshold": 4,
        "openai_api_key": "test-key",  # pragma: allowlist secret
        "openrouter_api_key": "or-key",  # pragma: allowlist secret
        "content_safety_ml_failover_enabled": True,
        "content_safety_second_opinion_enabled": False,
        "openai_moderation_threshold": 0.5,
        "openai_moderation_timeout": 3,
        "llama_guard_threshold": 0.5,
        "llama_guard_timeout": 3,
    }
    values.update(overrides)
    monkeypatch.setattr("utils.content_safety.settings", MagicMock(**values))


def _provider(result=None, error=None):
    p = MagicMock()
    p.analyze_text = AsyncMock(return_value=result, side_effect=error)
    return p


def _service(monkeypatch, lg=None, moderation=None, azure=None):
    service = ContentSafetyService()
    monkeypatch.setattr(service, "_get_llama_guard_provider", lambda: lg)
    monkeypatch.setattr(service, "_get_openai_moderation_provider", lambda: moderation)
    monkeypatch.setattr(service, "_get_azure_provider", lambda: azure)
    return service


async def test_disabled(monkeypatch):
    _settings(monkeypatch, content_safety_enabled=False)
    result = await _service(monkeypatch).check("hello", "en")
    assert (result.decided_by, result.failover) == ("disabled", False)


async def test_stage1_directed_harm_block(monkeypatch):
    _settings(monkeypatch)
    service = _service(monkeypatch)
    from utils.content_safety import ContentSafetyCheckResult

    blocked = ContentSafetyCheckResult(allowed=False, reason="x", decided_by="stage1_keywords")
    monkeypatch.setattr(service, "_check_stage1_keywords", lambda *a: blocked)
    assert (await service.check("anything", "en")).decided_by == "stage1_keywords"


def test_stage1_real_result_is_attributed(monkeypatch):
    _settings(monkeypatch)
    service = _service(monkeypatch)
    monkeypatch.setattr(
        service.keyword_filter,
        "check_multilingual",
        lambda text, language: (True, "high", "hate_speech", "pat"),
    )
    result = service._check_stage1_keywords("x", "en", 0.0)
    assert result is not None and result.decided_by == "stage1_keywords"


@pytest.mark.parametrize("allowed", [True, False])
async def test_llama_guard_decides(monkeypatch, allowed):
    _settings(monkeypatch)
    lg = _provider(ContentSafetyResult(allowed=allowed, reason="r"))
    result = await _service(monkeypatch, lg=lg).check(DEFAULT_BENIGN, "en")
    assert result.allowed is allowed
    assert (result.decided_by, result.failover) == ("llama_guard", False)


async def test_llama_guard_block_in_keyword_only_mode(monkeypatch):
    _settings(monkeypatch, content_safety_mode="keyword_only")
    lg = _provider(ContentSafetyResult(allowed=False, reason="unsafe"))
    service = _service(monkeypatch, lg=lg)
    result = await service._check_stage2_llama_guard("x", "en", 0.0)
    assert result.decided_by == "llama_guard" and not result.allowed


async def test_failover_to_openai_moderation(monkeypatch):
    _settings(monkeypatch)
    lg = _provider(error=httpx.ReadTimeout("down"))
    mod = _provider(ContentSafetyResult(allowed=False, reason="violence"))
    result = await _service(monkeypatch, lg=lg, moderation=mod).check(DEFAULT_UNSAFE, "en")
    assert (result.decided_by, result.failover) == ("openai_moderation", True)
    assert result.reason.endswith("(failover)")


async def test_keyword_fallback_when_both_ml_fail(monkeypatch):
    _settings(monkeypatch)
    lg = _provider(error=httpx.ReadTimeout("down"))
    mod = _provider(error=httpx.ReadTimeout("down"))
    result = await _service(monkeypatch, lg=lg, moderation=mod).check(DEFAULT_UNSAFE, "en")
    assert (result.decided_by, result.failover) == ("keyword_fallback", False)
    assert result.allowed is False


async def test_keyword_fallback_when_failover_disabled(monkeypatch):
    _settings(monkeypatch, content_safety_ml_failover_enabled=False)
    lg = _provider(error=httpx.ReadTimeout("down"))
    result = await _service(monkeypatch, lg=lg).check(DEFAULT_UNSAFE, "en")
    assert result.decided_by == "keyword_fallback"


async def test_second_opinion_override_is_keyword_fallback(monkeypatch):
    _settings(monkeypatch, content_safety_second_opinion_enabled=True)
    service = _service(monkeypatch)
    monkeypatch.setattr(
        "utils.safety_second_opinion.classify_self_harm_vs_violence",
        AsyncMock(return_value="SELF_HARM"),
    )
    result = await service._keyword_fallback("I want to die and kill my boss", "en", 0.0)
    assert result.decided_by == "keyword_fallback"


async def test_keyword_only_openai_moderation(monkeypatch):
    _settings(monkeypatch, content_safety_mode="keyword_only")
    mod = _provider(ContentSafetyResult(allowed=True, reason="clean"))
    result = await _service(monkeypatch, moderation=mod).check(DEFAULT_BENIGN, "en")
    assert (result.decided_by, result.failover) == ("openai_moderation", False)


async def test_hybrid_openai_block(monkeypatch):
    _settings(monkeypatch, content_safety_mode="hybrid", azure_content_safety_enabled=True)
    mod = _provider(ContentSafetyResult(allowed=False, reason="violence"))
    result = await _service(monkeypatch, moderation=mod).check(DEFAULT_UNSAFE, "en")
    assert result.decided_by == "openai_moderation"


async def test_hybrid_azure_decides(monkeypatch):
    _settings(monkeypatch, content_safety_mode="hybrid", azure_content_safety_enabled=True)
    mod = _provider(ContentSafetyResult(allowed=True, reason="clean"))
    azure = _provider(ContentSafetyResult(allowed=False, reason="azure_violence"))
    result = await _service(monkeypatch, moderation=mod, azure=azure).check(DEFAULT_UNSAFE, "en")
    assert (result.decided_by, result.allowed) == ("azure", False)


async def test_hybrid_azure_error_falls_to_keyword_fallback(monkeypatch):
    _settings(monkeypatch, content_safety_mode="hybrid", azure_content_safety_enabled=True)
    mod = _provider(ContentSafetyResult(allowed=True, reason="clean"))
    azure = _provider(error=RuntimeError("azure down"))
    result = await _service(monkeypatch, moderation=mod, azure=azure).check(DEFAULT_BENIGN, "en")
    assert result.decided_by == "keyword_fallback"


async def test_default_allow(monkeypatch):
    _settings(monkeypatch, content_safety_mode="hybrid", azure_content_safety_enabled=False)
    mod = _provider(ContentSafetyResult(allowed=True, reason="clean"))
    result = await _service(monkeypatch, moderation=mod).check(DEFAULT_BENIGN, "en")
    assert (result.decided_by, result.allowed) == ("default_allow", True)


@pytest.mark.parametrize("language", LANGS)
async def test_keyword_fallback_attribution_all_languages(monkeypatch, language):
    _settings(monkeypatch, content_safety_ml_failover_enabled=False)
    lg = _provider(error=httpx.ReadTimeout("down"))
    result = await _service(monkeypatch, lg=lg).check(NARRATIVE[language], language)
    assert result.decided_by == "keyword_fallback"
    assert result.failover is False


@pytest.mark.parametrize("language", LANGS)
async def test_llama_guard_attribution_all_languages(monkeypatch, language):
    _settings(monkeypatch)
    lg = _provider(ContentSafetyResult(allowed=True, reason="clean"))
    result = await _service(monkeypatch, lg=lg).check(NARRATIVE[language], language)
    assert result.decided_by == "llama_guard"


@pytest.mark.parametrize("message", [DEFAULT_UNSAFE, DEFAULT_BENIGN])
def test_default_probe_messages_reach_ml(monkeypatch, message):
    """Stage 1 must not decide the probe messages, or the probe would not test ML."""
    _settings(monkeypatch)
    assert _service(monkeypatch)._check_stage1_keywords(message, "en", 0.0) is None

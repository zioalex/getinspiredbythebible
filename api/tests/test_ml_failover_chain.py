"""BITB-292: ordered ml_only failover chain (openai_moderation, azure).

Real ContentSafetyService; Llama Guard forced down, OpenAI Moderation and the Azure provider
mocked at the provider boundary, keyword fallback spied.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Settings, parse_ml_failover_chain
from providers.azure_content_safety import ContentSafetyResult
from utils.content_safety import ContentSafetyCheckResult, ContentSafetyService

LANGS = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
TEXT = {
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


# --------------------------------------------------------------------------- config parsing


def test_chain_default_is_openai_moderation():
    assert Settings().content_safety_ml_failover_chain == "openai_moderation"
    assert Settings().ml_failover_chain == ["openai_moderation"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("openai_moderation,azure", ["openai_moderation", "azure"]),
        ("azure,openai_moderation", ["azure", "openai_moderation"]),
        ("  Azure , OPENAI_Moderation ", ["azure", "openai_moderation"]),
        ("azure,azure,openai_moderation,azure", ["azure", "openai_moderation"]),
        ("azure,,", ["azure"]),
        ("", ["openai_moderation"]),
        ("   ", ["openai_moderation"]),
    ],
)
def test_chain_parsing(raw, expected):
    assert parse_ml_failover_chain(raw) == expected
    assert Settings(content_safety_ml_failover_chain=raw).ml_failover_chain == expected


def test_chain_env_var_is_read_and_canonicalized(monkeypatch):
    monkeypatch.setenv("CONTENT_SAFETY_ML_FAILOVER_CHAIN", " Openai_Moderation , AZURE ")
    s = Settings()
    assert s.content_safety_ml_failover_chain == "openai_moderation,azure"


def test_chain_unknown_entry_fails_at_startup():
    with pytest.raises(ValueError, match="bogus"):
        Settings(content_safety_ml_failover_chain="openai_moderation,bogus")


# --------------------------------------------------------------------------- harness


def _settings(chain="openai_moderation", **overrides):
    values = {
        "content_safety_enabled": True,
        "content_safety_mode": "ml_only",
        "azure_content_safety_enabled": True,
        "azure_content_safety_endpoint": "https://x.cognitiveservices.azure.com/",
        "azure_content_safety_key": "az-key",  # pragma: allowlist secret
        "azure_content_safety_threshold": 4,
        "openai_api_key": "test-key",  # pragma: allowlist secret
        "openrouter_api_key": "or-key",  # pragma: allowlist secret
        "content_safety_ml_failover_enabled": True,
        "content_safety_ml_failover_chain": chain,
        "content_safety_second_opinion_enabled": False,
        "openai_moderation_threshold": 0.5,
        "openai_moderation_timeout": 3,
    }
    values.update(overrides)
    return MagicMock(**values)


def _ok(reason="clean", **kw):
    return ContentSafetyCheckResult(allowed=True, reason=reason, **kw)


def _blocked(reason="violence_or_threat_detected"):
    return ContentSafetyCheckResult(allowed=False, reason=reason)


@pytest.fixture
def make(monkeypatch):
    """Build (service, openai_mock, azure_provider_mock, keyword_spy)."""

    def _make(chain="openai_moderation", openai=None, azure=None, azure_configured=True, **ov):
        monkeypatch.setattr("utils.content_safety.settings", _settings(chain, **ov))
        service = ContentSafetyService()
        lg = MagicMock()
        lg.analyze_text = AsyncMock(side_effect=httpx.ReadTimeout("openrouter down"))
        monkeypatch.setattr(service, "_get_llama_guard_provider", lambda: lg)
        oa = AsyncMock(side_effect=openai if openai is not None else AssertionError("no openai"))
        monkeypatch.setattr(service, "_try_openai_moderation", oa)
        provider = MagicMock()
        provider.analyze_text = AsyncMock(
            side_effect=azure if azure is not None else AssertionError("azure must not run")
        )
        monkeypatch.setattr(
            service, "_get_azure_provider", lambda: provider if azure_configured else None
        )
        kw = AsyncMock(return_value=_ok("keyword_fallback"))
        monkeypatch.setattr(service, "_keyword_fallback", kw)
        return service, oa, provider, kw

    return _make


def _openai_returns(result):
    async def _f(text, language, start):
        return result, None

    return _f


def _openai_fails(exc=None):
    async def _f(text, language, start):
        return None, exc or httpx.ReadTimeout("openai down")

    return _f


def _counters():
    return (
        patch("utils.content_safety.content_safety_failover_counter"),
        patch("utils.content_safety.content_safety_fallback_counter"),
    )


def _hops(failover):
    return [c.args[1] for c in failover.add.call_args_list]


def _azure_result(allowed=True, **kw):
    return ContentSafetyResult(allowed=allowed, reason=kw.pop("reason", "clean"), **kw)


# --------------------------------------------------------------------------- behaviour


async def test_default_chain_never_calls_azure_even_if_configured(make):
    service, oa, azure, kw = make("openai_moderation", openai=_openai_fails())
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("Why did Cain kill Abel?", "en")
    azure.analyze_text.assert_not_awaited()
    kw.assert_awaited_once()
    assert [h["to_stage"] for h in _hops(failover)] == ["openai_moderation"]
    assert fallback.add.call_args.args[1]["failover"] == "openai_moderation_failed"


async def test_openai_decides_azure_not_called(make):
    service, _, azure, kw = make("openai_moderation,azure")
    service._try_openai_moderation = _openai_returns(_blocked())
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        result = await service.check("I want to build a bomb", "en")
    assert result.allowed is False and result.reason.endswith("(failover)")
    azure.analyze_text.assert_not_awaited()
    kw.assert_not_awaited()
    fallback.add.assert_not_called()
    (labels,) = _hops(failover)
    assert (labels["from_stage"], labels["to_stage"], labels["outcome"]) == (
        "llama_guard",
        "openai_moderation",
        "decided",
    )


@pytest.mark.parametrize("allowed", [False, True])
async def test_openai_fails_azure_decides(make, allowed):
    service, _, azure, kw = make(
        "openai_moderation,azure", azure=[_azure_result(allowed, reason="azure_verdict")]
    )
    service._try_openai_moderation = _openai_fails()
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        result = await service.check("some text", "en")
    assert result.allowed is allowed
    assert result.reason == "azure_verdict (failover)"
    kw.assert_not_awaited()
    fallback.add.assert_not_called()
    first, second = _hops(failover)
    assert (first["from_stage"], first["to_stage"], first["outcome"]) == (
        "llama_guard",
        "openai_moderation",
        "failed",
    )
    assert (second["from_stage"], second["to_stage"], second["outcome"]) == (
        "openai_moderation",
        "azure",
        "decided",
    )
    for labels in (first, second):  # original Llama Guard reason is kept on every hop
        assert labels["reason"] == "timeout" and labels["failure_class"] == "timeout"


async def test_both_fail_runs_keyword_with_azure_failed(make):
    service, _, azure, kw = make("openai_moderation,azure", azure=[RuntimeError("azure down")])
    service._try_openai_moderation = _openai_fails()
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("some text", "en")
    kw.assert_awaited_once()
    assert [(h["to_stage"], h["outcome"]) for h in _hops(failover)] == [
        ("openai_moderation", "failed"),
        ("azure", "failed"),
    ]
    assert fallback.add.call_args.args[1] == {
        "stage": "llama_guard",
        "reason": "timeout",
        "failure_class": "timeout",
        "failover": "azure_failed",
    }


async def test_openai_unconfigured_azure_tried_from_llama_guard(make):
    service, _, azure, kw = make(
        "openai_moderation,azure", azure=[_azure_result(True)], openai_api_key=None
    )
    fo, fb = _counters()
    with fo as failover, fb:
        result = await service.check("some text", "en")
    assert result.allowed and result.reason == "clean (failover)"
    service._try_openai_moderation.assert_not_awaited()
    (labels,) = _hops(failover)
    assert (labels["from_stage"], labels["to_stage"]) == ("llama_guard", "azure")


async def test_azure_unconfigured_is_skipped_silently(make):
    service, _, azure, kw = make(
        "openai_moderation,azure", azure_configured=False, azure=[_azure_result()]
    )
    service._try_openai_moderation = _openai_fails()
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("some text", "en")
    assert [h["to_stage"] for h in _hops(failover)] == ["openai_moderation"]
    assert fallback.add.call_args.args[1]["failover"] == "openai_moderation_failed"


async def test_nothing_configured_is_unconfigured(make):
    service, _, _, kw = make("openai_moderation,azure", azure_configured=False, openai_api_key=None)
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("some text", "en")
    failover.add.assert_not_called()
    kw.assert_awaited_once()
    assert fallback.add.call_args.args[1]["failover"] == "unconfigured"


async def test_master_switch_off_is_disabled_and_skips_azure(make):
    service, _, azure, kw = make(
        "openai_moderation,azure", content_safety_ml_failover_enabled=False
    )
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("some text", "en")
    failover.add.assert_not_called()
    azure.analyze_text.assert_not_awaited()
    assert fallback.add.call_args.args[1]["failover"] == "disabled"


async def test_azure_first_ordering_respected(make):
    service, oa, azure, kw = make("azure,openai_moderation", azure=[RuntimeError("azure down")])
    service._try_openai_moderation = _openai_returns(_ok("clean"))
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        result = await service.check("some text", "en")
    assert result.reason == "clean (failover)"
    assert [(h["from_stage"], h["to_stage"], h["outcome"]) for h in _hops(failover)] == [
        ("llama_guard", "azure", "failed"),
        ("azure", "openai_moderation", "decided"),
    ]
    fallback.add.assert_not_called()


async def test_azure_first_decides_openai_not_called(make):
    service, oa, azure, kw = make("azure,openai_moderation", azure=[_azure_result(False)])
    result = await service.check("some text", "en")
    assert result.allowed is False
    oa.assert_not_awaited()


async def test_azure_only_chain_all_failed_label(make):
    service, _, azure, kw = make("azure", azure=[RuntimeError("down")])
    fo, fb = _counters()
    with fo, fb as fallback:
        await service.check("some text", "en")
    assert fallback.add.call_args.args[1]["failover"] == "azure_failed"


@pytest.mark.parametrize("language", LANGS)
async def test_llama_guard_outage_openai_down_azure_decides_all_languages(make, language):
    azure_verdict = _azure_result(
        True,
        reason="help_seeking_detected",
        is_help_seeking=True,
        compassionate_response_needed=True,
        categories={"SelfHarm": 4},
    )
    service, _, azure, kw = make("openai_moderation,azure", azure=[azure_verdict])
    service._try_openai_moderation = _openai_fails()
    result = await service.check(TEXT[language], language)
    assert result.allowed is True
    assert result.is_help_seeking and result.compassionate_response_needed
    assert result.categories == {"SelfHarm": 4}
    assert result.reason == "help_seeking_detected (failover)"
    azure.analyze_text.assert_awaited_once_with(TEXT[language], language)
    kw.assert_not_awaited()


async def test_try_azure_unconfigured_and_error(make):
    service, _, azure, _ = make("azure", azure=[RuntimeError("boom")])
    result, error = await service._try_azure("t", "en", 0.0)
    assert result is None and isinstance(error, RuntimeError)
    service._get_azure_provider = lambda: None
    assert await service._try_azure("t", "en", 0.0) == (None, None)


async def test_azure_log_has_hash_not_text(make, caplog):
    secret = "UNIQUE-SECRET-USER-TEXT"
    service, _, _, _ = make("azure", azure=[_azure_result()])
    with caplog.at_level(logging.DEBUG):
        await service._try_azure(secret, "en", 0.0)
    assert all(secret not in r.getMessage() for r in caplog.records)
    assert any(getattr(r, "text_hash", None) for r in caplog.records)


async def test_hybrid_azure_failure_behaviour_unchanged(monkeypatch):
    monkeypatch.setattr("utils.content_safety.settings", _settings(content_safety_mode="hybrid"))
    service = ContentSafetyService()
    monkeypatch.setattr(service, "_get_llama_guard_provider", lambda: None)
    service._try_openai_moderation = AsyncMock(return_value=(_ok(), None))
    provider = MagicMock()
    provider.analyze_text = AsyncMock(side_effect=RuntimeError("down"))
    monkeypatch.setattr(service, "_get_azure_provider", lambda: provider)
    kw = AsyncMock(return_value=_ok("keyword_fallback"))
    monkeypatch.setattr(service, "_keyword_fallback", kw)
    fo, fb = _counters()
    with fo, fb as fallback:
        await service.check("hello there", "en")
    kw.assert_awaited_once()
    fallback.add.assert_called_once_with(1, {"stage": "azure", "reason": "runtimeerror"})


# --------------------------------------------------------------------------- startup warnings


@pytest.mark.parametrize(
    "chain,flag,key,azure_on,expect",
    [
        ("openai_moderation", True, "k", False, []),
        ("openai_moderation", True, None, False, ["no configured"]),
        ("openai_moderation,azure", True, None, True, []),
        ("openai_moderation,azure", True, "k", False, ["incomplete"]),
        ("openai_moderation,azure", True, None, False, ["incomplete", "no configured"]),
        ("azure", True, "k", False, ["incomplete", "no configured"]),
        ("", True, "k", False, []),
        (",,", True, None, False, ["no configured"]),
        ("openai_moderation,azure", False, "k", True, ["DISABLED"]),
    ],
)
def test_startup_warnings(monkeypatch, caplog, chain, flag, key, azure_on, expect):
    from utils.content_safety import log_failover_config_warning

    monkeypatch.setattr(
        "utils.content_safety.settings",
        _settings(
            chain,
            content_safety_ml_failover_enabled=flag,
            openai_api_key=key,
            azure_content_safety_enabled=azure_on,
        ),
    )
    with caplog.at_level(logging.WARNING):
        log_failover_config_warning()
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == len(expect)
    for fragment in expect:
        assert any(fragment in m for m in messages)


async def test_openai_key_set_but_provider_unbuildable_counts_as_failed_hop(make):
    """D2: key set + provider None is an attempted, failed hop (HEAD behaviour)."""
    service, _, _, kw = make("openai_moderation")

    async def _unbuildable(text, language, start):
        return None, None

    service._try_openai_moderation = _unbuildable
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("some text", "en")
    (labels,) = _hops(failover)
    assert (labels["to_stage"], labels["outcome"]) == ("openai_moderation", "failed")
    assert fallback.add.call_args.args[1]["failover"] == "openai_moderation_failed"
    kw.assert_awaited_once()


def test_invalid_chain_string_on_settings_double_warns_once_and_defaults(monkeypatch, caplog):
    import utils.content_safety as cs

    monkeypatch.setattr(cs, "_chain_warning_logged", False)
    monkeypatch.setattr(cs, "settings", _settings("bogus"))
    with caplog.at_level(logging.WARNING):
        assert cs._ml_failover_chain() == ["openai_moderation"]
        assert cs._ml_failover_chain() == ["openai_moderation"]
    assert len([r for r in caplog.records if "Invalid CONTENT_SAFETY" in r.getMessage()]) == 1


def _real_azure_provider(self_harm=0, violence=0, hate=0, sexual=0, delay=0.0, timeout=3.0):
    """REAL AzureContentSafetyProvider with a stubbed SDK client (no result-level mock)."""
    import time

    from providers.azure_content_safety import AzureContentSafetyProvider

    with patch.dict(
        "sys.modules",
        {
            "azure": MagicMock(),
            "azure.ai": MagicMock(),
            "azure.ai.contentsafety": MagicMock(),
            "azure.ai.contentsafety.models": MagicMock(),
            "azure.core": MagicMock(),
            "azure.core.credentials": MagicMock(),
        },
    ):
        provider = AzureContentSafetyProvider("https://t.cognitiveservices.azure.com/", "k", 4)
    provider.timeout = timeout
    response = MagicMock()
    response.categories_analysis = [
        MagicMock(severity=hate),
        MagicMock(severity=self_harm),
        MagicMock(severity=sexual),
        MagicMock(severity=violence),
    ]
    for cat in response.categories_analysis:
        del cat.category  # force positional mapping

    def _call(request):
        time.sleep(delay)
        return response

    client = MagicMock()
    client.analyze_text = _call
    provider._client = client
    provider._sdk_available = True
    return provider


@pytest.mark.parametrize("language", LANGS)
async def test_chain_with_real_azure_provider_severe_self_harm_is_compassionate(make, language):
    """D1: severe self-harm-only text reaching Azure via the failover is allowed + compassionate."""
    service, _, _, kw = make("openai_moderation,azure")
    service._try_openai_moderation = _openai_fails()
    provider = _real_azure_provider(self_harm=6)
    service._get_azure_provider = lambda: provider
    result = await service.check(TEXT[language], language)
    assert result.allowed is True
    assert result.is_help_seeking and result.compassionate_response_needed
    assert result.reason == "help_seeking_detected (failover)"
    kw.assert_not_awaited()


async def test_chain_with_real_azure_provider_violence_blocks(make):
    service, _, _, kw = make("openai_moderation,azure")
    service._try_openai_moderation = _openai_fails()
    provider = _real_azure_provider(self_harm=6, violence=4)
    service._get_azure_provider = lambda: provider
    result = await service.check("x", "en")
    assert result.allowed is False and not result.compassionate_response_needed


async def test_chain_azure_timeout_counts_as_failed_hop(make):
    service, _, _, kw = make("openai_moderation,azure")
    service._try_openai_moderation = _openai_fails()
    provider = _real_azure_provider(self_harm=6, delay=0.5, timeout=0.05)
    service._get_azure_provider = lambda: provider
    fo, fb = _counters()
    with fo as failover, fb as fallback:
        await service.check("x", "en")
    assert [(h["to_stage"], h["outcome"]) for h in _hops(failover)] == [
        ("openai_moderation", "failed"),
        ("azure", "failed"),
    ]
    assert fallback.add.call_args.args[1]["failover"] == "azure_failed"
    kw.assert_awaited_once()

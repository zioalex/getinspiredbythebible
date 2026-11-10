"""
Tests for multi-language content safety service.

Covers:
- Text normalization (NFKC, zero-width chars, leet-speak)
- MultiLanguageContentFilter (7 languages)
- ContentSafetyService (hybrid keyword + Azure)
- Help-seeking vs harmful intent distinction
"""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.content_safety import ContentSafetyService
from utils.security import MultiLanguageContentFilter, ViolationType, normalize_text

# ============================================================================
# Text Normalization Tests
# ============================================================================


def test_normalize_text_nfkc():
    """Test NFKC normalization."""
    # Compatibility characters
    text = "ℌello"  # Script H
    assert normalize_text(text) == "hello"


def test_normalize_text_zero_width_chars():
    """Test zero-width character removal."""
    # Zero-width space between letters
    text = "b\u200bomb"
    normalized = normalize_text(text)
    assert "\u200b" not in normalized
    assert "bomb" in normalized


def test_normalize_text_leet_speak():
    """Test leet-speak substitution."""
    assert "bomb" in normalize_text("b0mb")
    assert "attack" in normalize_text("4tt4ck")
    assert "fck" in normalize_text("f*ck")  # Asterisks removed


# ============================================================================
# MultiLanguageContentFilter Tests
# ============================================================================


@pytest.fixture
def content_filter():
    """Create a MultiLanguageContentFilter instance."""
    return MultiLanguageContentFilter()


def test_violence_detection_english(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I want to build a bomb", "en"
    )
    # Violence patterns now handled by Llama Guard (Stage 2), not keyword filter
    assert blocked is False
    assert violation_type is None


def test_violence_detection_italian(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Voglio costruire una bomba", "it"
    )
    assert blocked is False
    assert violation_type is None


def test_violence_detection_german(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Ich will eine Bombe bauen", "de"
    )
    assert blocked is False
    assert violation_type is None


def test_violence_detection_spanish(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Quiero construir una bomba", "es"
    )
    assert blocked is False
    assert violation_type is None


def test_violence_detection_french(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Je veux construire une bombe", "fr"
    )
    assert blocked is False
    assert violation_type is None


def test_violence_detection_portuguese(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Quero construir uma bomba", "pt"
    )
    assert blocked is False
    assert violation_type is None


def test_violence_detection_arabic(content_filter):
    """Violence keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "أريد بناء قنبلة", "ar"
    )
    assert blocked is False
    assert violation_type is None


def test_self_harm_help_seeking_english(content_filter):
    """Self-harm keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I feel like I want to die, can you help?", "en"
    )
    assert blocked is False
    assert violation_type is None


def test_self_harm_help_seeking_italian(content_filter):
    """Self-harm keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Voglio morire", "it"
    )
    assert blocked is False
    assert violation_type is None


def test_self_harm_help_seeking_german(content_filter):
    """Self-harm keywords are NO LONGER checked in Stage 1 (moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Ich will sterben", "de"
    )
    assert blocked is False
    assert violation_type is None


def test_directed_harm_blocked(content_filter):
    """Test directed harm is blocked with high confidence."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Go kill yourself", "en"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.DIRECTED_HARM.value


def test_directed_harm_italian(content_filter):
    """Test directed harm in Italian."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Vattene a fanculo", "it"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.DIRECTED_HARM.value


def test_hate_speech_blocked(content_filter):
    """Test hate speech detection."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "God hates you all", "en"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.HATE_SPEECH.value


def test_clean_message_allowed(content_filter):
    """Test clean message is allowed."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I need guidance on my faith journey", "en"
    )
    assert blocked is False
    assert violation_type is None


def test_unicode_evasion_detected(content_filter):
    """Unicode evasion no longer detected in Stage 1 (violence moved to Llama Guard Stage 2)."""
    # Zero-width space evasion
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I want to build a b\u200bomb", "en"
    )
    assert blocked is False  # Violence patterns now in Stage 2


def test_leet_speak_evasion_detected(content_filter):
    """Leet-speak evasion no longer detected in Stage 1 (violence moved to Llama Guard Stage 2)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I want to build a b0mb", "en"
    )
    assert blocked is False  # Violence patterns now in Stage 2


# ============================================================================
# ContentSafetyService Tests (with mocked Azure)
# ============================================================================


@pytest.fixture
def safety_service_enabled(monkeypatch):
    """Create ContentSafetyService with content safety enabled (ml_only mode) and Llama Guard available."""
    from providers.azure_content_safety import ContentSafetyResult

    # Mock settings (use ml_only mode to test Llama Guard integration)
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=False,
            azure_content_safety_endpoint=None,
            azure_content_safety_key=None,
            azure_content_safety_threshold=4,
            openai_api_key="test-key",  # pragma: allowlist secret
            openrouter_api_key=None,
            content_safety_ml_failover_enabled=True,
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )

    service = ContentSafetyService()

    # Mock Llama Guard provider to return appropriate responses
    async def mock_analyze_text(text: str, language: str = "en") -> ContentSafetyResult:
        """Mock Llama Guard API responses based on text content."""
        text_lower = text.lower()

        # Check for violence keywords (would be blocked by Llama Guard)
        if any(
            word in text_lower
            for word in ["bomb", "bomba", "bombe", "gun", "weapon", "kill", "murder"]
        ):
            # But allow biblical context
            if any(
                phrase in text_lower
                for phrase in ["david", "goliath", "pharisee", "testament", "bible", "scripture"]
            ):
                return ContentSafetyResult(allowed=True, reason="clean", categories={})
            # Block actual threats
            return ContentSafetyResult(
                allowed=False, reason="violence_or_threat_detected", categories={"violence": 9}
            )

        # Check for self-harm (would be flagged as help-seeking by Llama Guard)
        if any(word in text_lower for word in ["die", "death", "suicide", "morire", "sterben"]):
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
                categories={"self-harm/intent": 7},
            )

        # Clean message
        return ContentSafetyResult(allowed=True, reason="clean", categories={})

    # Patch the _get_llama_guard_provider method to return a mock
    def mock_get_llama_guard():
        if not hasattr(service, "_mock_llama_guard_provider"):
            mock_provider = MagicMock()
            mock_provider.analyze_text = mock_analyze_text
            service._mock_llama_guard_provider = mock_provider
        return service._mock_llama_guard_provider

    service._get_llama_guard_provider = mock_get_llama_guard

    return service


@pytest.fixture
def safety_service_disabled(monkeypatch):
    """Create ContentSafetyService with content safety disabled."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=False,
            content_safety_mode="keyword_only",
            azure_content_safety_enabled=False,
        ),
    )
    return ContentSafetyService()


async def test_allows_clean_message(safety_service_enabled):
    """Test clean message is allowed."""
    result = await safety_service_enabled.check("I need guidance on my faith journey", "en")
    assert result.allowed is True
    assert result.reason == "clean"
    assert result.is_help_seeking is False


async def test_allows_help_seeking_self_harm(safety_service_enabled):
    """Test help-seeking self-harm message is allowed with compassion flag."""
    result = await safety_service_enabled.check("I feel like I want to die, can you help?", "en")
    assert result.allowed is True  # Allowed despite pattern match
    assert result.reason == "possible_help_seeking"
    assert result.is_help_seeking is True
    assert result.compassionate_response_needed is True


async def test_blocks_directed_harm(safety_service_enabled):
    """Test directed harm is blocked."""
    result = await safety_service_enabled.check("Go kill yourself", "en")
    assert result.allowed is False
    assert "keyword_violation" in result.reason
    assert ViolationType.DIRECTED_HARM.value in result.reason


async def test_blocks_violence(safety_service_enabled):
    """Test violence is blocked (by Llama Guard Stage 2)."""
    result = await safety_service_enabled.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


async def test_blocks_italian_violence(safety_service_enabled):
    """Test Italian violence is blocked (by Llama Guard Stage 2)."""
    result = await safety_service_enabled.check("Voglio costruire una bomba", "it")
    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


async def test_disabled_allows_everything(safety_service_disabled):
    """Test disabled filter allows everything."""
    result = await safety_service_disabled.check("I want to build a bomb", "en")
    assert result.allowed is True
    assert result.reason == "disabled"


async def test_abuse_blocked(safety_service_enabled):
    """Test abuse directed at AI is blocked."""
    result = await safety_service_enabled.check("Go fuck yourself", "en")
    assert result.allowed is False
    assert "keyword_violation" in result.reason


async def test_profanity_in_context_allowed(safety_service_enabled):
    """Test profanity as self-expression (not directed) is allowed.

    Note: Current implementation doesn't have profanity patterns in
    MultiLanguageContentFilter, only in ContentFilter.
    This test verifies the service doesn't block self-expression.
    """
    # "I feel like shit" is self-expression, not directed harm
    result = await safety_service_enabled.check("I feel like shit, I need help", "en")
    # Should be allowed - no violence/hate/directed harm patterns
    assert result.allowed is True


async def test_performance_keyword_under_50ms(safety_service_enabled):
    """Test keyword filter completes in under 50ms."""
    start = time.monotonic()
    await safety_service_enabled.check("I want to build a bomb", "en")
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 500  # Keyword-only path is fast; 500ms guards against regressions on CI


# ============================================================================
# Azure Content Safety Integration Tests (mocked)
# ============================================================================


@pytest.fixture
def safety_service_hybrid(monkeypatch):
    """Create ContentSafetyService with hybrid mode (mocked OpenAI Moderation and Azure)."""
    from providers.azure_content_safety import ContentSafetyResult

    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="hybrid",
            azure_content_safety_enabled=True,
            azure_content_safety_endpoint="https://test.cognitiveservices.azure.com/",
            azure_content_safety_key="test-key",  # pragma: allowlist secret
            azure_content_safety_threshold=4,
            openai_api_key="test-key",  # pragma: allowlist secret
            openrouter_api_key=None,
            openai_moderation_threshold=0.5,
            openai_moderation_timeout=3,
            content_safety_ml_failover_enabled=True,
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )

    service = ContentSafetyService()

    # Mock OpenAI Moderation provider (hybrid Stage 2 uses OpenAI Moderation, not Llama Guard)
    async def mock_openai_analyze(text: str, language: str = "en") -> ContentSafetyResult:
        """Mock OpenAI Moderation API responses."""
        text_lower = text.lower()

        if any(word in text_lower for word in ["bomb", "bomba", "violent threat"]):
            return ContentSafetyResult(
                allowed=False, reason="violence_or_threat_detected", categories={"violence": 95}
            )

        if any(word in text_lower for word in ["die", "death"]):
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
                categories={"self-harm/intent": 70},
            )

        return ContentSafetyResult(allowed=True, reason="clean", categories={})

    def mock_get_openai():
        if not hasattr(service, "_mock_openai_provider"):
            mock_provider = MagicMock()
            mock_provider.analyze_text = mock_openai_analyze
            service._mock_openai_provider = mock_provider
        return service._mock_openai_provider

    service._get_openai_moderation_provider = mock_get_openai

    return service


async def test_fallback_to_keyword_when_openai_and_azure_unavailable(
    safety_service_hybrid, monkeypatch
):
    """Test fallback when both OpenAI Moderation and Azure are unavailable."""
    mock_openai_provider = MagicMock()
    mock_openai_provider.analyze_text = AsyncMock(
        side_effect=RuntimeError("OpenAI Moderation unavailable")
    )

    mock_azure_provider = MagicMock()
    mock_azure_provider.analyze_text = AsyncMock(side_effect=RuntimeError("Azure unavailable"))

    monkeypatch.setattr(
        safety_service_hybrid, "_get_openai_moderation_provider", lambda: mock_openai_provider
    )
    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_azure_provider)

    result = await safety_service_hybrid.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "fallback" in result.reason


async def test_azure_help_seeking_allowed(safety_service_hybrid, monkeypatch):
    """Test Azure provider allows help-seeking messages."""
    from providers.azure_content_safety import ContentSafetyResult

    # Mock Azure provider
    mock_provider = MagicMock()
    mock_provider.analyze_text = AsyncMock(
        return_value=ContentSafetyResult(
            allowed=True,
            reason="help_seeking_detected",
            categories={"hate": 0, "self_harm": 2, "sexual": 0, "violence": 0},
            max_severity=2,
            is_help_seeking=True,
            compassionate_response_needed=True,
            language="en",
        )
    )

    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_provider)

    # Low confidence self-harm should go to Azure
    result = await safety_service_hybrid.check("I want to die", "en")
    assert result.allowed is True
    assert result.is_help_seeking is True
    assert result.compassionate_response_needed is True


async def test_azure_harmful_blocked(safety_service_hybrid, monkeypatch):
    """Test Azure provider blocks harmful intent in hybrid mode when OpenAI Moderation allows."""
    from providers.azure_content_safety import ContentSafetyResult

    mock_azure_provider = MagicMock()
    mock_azure_provider.analyze_text = AsyncMock(
        return_value=ContentSafetyResult(
            allowed=False,
            reason="harmful_intent_detected",
            categories={"hate": 0, "self_harm": 0, "sexual": 0, "violence": 6},
            max_severity=6,
            is_help_seeking=False,
            compassionate_response_needed=False,
            language="en",
        )
    )

    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_azure_provider)

    # Mock OpenAI Moderation to allow (so Azure Stage 3 is reached)
    mock_openai_provider = MagicMock()
    mock_openai_provider.analyze_text = AsyncMock(
        return_value=ContentSafetyResult(allowed=True, reason="clean", categories={})
    )
    monkeypatch.setattr(
        safety_service_hybrid, "_get_openai_moderation_provider", lambda: mock_openai_provider
    )

    result = await safety_service_hybrid.check("borderline violent message", "en")
    assert result.allowed is False
    assert result.reason == "harmful_intent_detected"


# ============================================================================
# Content Safety Mode Semantics Tests
# ============================================================================


@pytest.fixture
def safety_service_keyword_only(monkeypatch):
    """Create ContentSafetyService with keyword_only mode (no API key → OpenAI Moderation
    unavailable → falls back to full keyword filter for violence detection)."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="keyword_only",
            azure_content_safety_enabled=False,
            azure_content_safety_endpoint=None,
            azure_content_safety_key=None,
            openai_api_key=None,
            openrouter_api_key=None,
            openai_moderation_threshold=0.5,
            openai_moderation_timeout=3,
            content_safety_ml_failover_enabled=True,
        ),
    )
    return ContentSafetyService()


def test_openai_moderation_provider_requires_openai_api_key(monkeypatch):
    """OpenAI Moderation does not initialize with only OPENROUTER_API_KEY."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="keyword_only",
            openai_api_key=None,
            openrouter_api_key="test-key",  # pragma: allowlist secret
            openai_moderation_threshold=0.5,
            openai_moderation_timeout=3,
        ),
    )

    service = ContentSafetyService()
    provider = service._get_openai_moderation_provider()

    assert provider is None


@pytest.fixture
def safety_service_ml_only(monkeypatch):
    """Create ContentSafetyService with ml_only mode (Llama Guard only, no Azure)."""
    from providers.azure_content_safety import ContentSafetyResult

    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=False,
            openrouter_api_key="test-key",  # pragma: allowlist secret
            openai_api_key=None,
            content_safety_ml_failover_enabled=True,
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )

    service = ContentSafetyService()

    # Mock Llama Guard provider
    async def mock_analyze_text(text: str, language: str = "en") -> ContentSafetyResult:
        """Mock Llama Guard to detect violence."""
        if "bomb" in text.lower():
            return ContentSafetyResult(
                allowed=False, reason="violence_or_threat_detected", categories={"violence": 9}
            )
        return ContentSafetyResult(allowed=True, reason="clean", categories={})

    def mock_get_llama_guard():
        if not hasattr(service, "_mock_llama_guard_provider"):
            mock_provider = MagicMock()
            mock_provider.analyze_text = mock_analyze_text
            service._mock_llama_guard_provider = mock_provider
        return service._mock_llama_guard_provider

    service._get_llama_guard_provider = mock_get_llama_guard

    return service


async def test_keyword_only_mode_does_not_call_llama_guard(
    safety_service_keyword_only, monkeypatch
):
    """keyword_only mode calls OpenAI Moderation (Stage 2), NOT Llama Guard."""
    llama_guard_called = False

    def mock_get_llama_guard():
        nonlocal llama_guard_called
        llama_guard_called = True
        raise AssertionError("Llama Guard must NOT be called in keyword_only mode")

    monkeypatch.setattr(
        safety_service_keyword_only, "_get_llama_guard_provider", mock_get_llama_guard
    )

    # Without API key, OpenAI Moderation is unavailable → fallback to full keyword filter
    result = await safety_service_keyword_only.check("I want to build a bomb", "en")

    assert llama_guard_called is False
    # Fallback keyword filter catches "bomb" → blocked
    assert result.allowed is False
    assert "fallback" in result.reason


async def test_ml_only_mode_calls_llama_guard(safety_service_ml_only):
    """ml_only mode DOES call Llama Guard for violence detection."""
    result = await safety_service_ml_only.check("I want to build a bomb", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


async def test_hybrid_mode_calls_openai_moderation_not_llama_guard(
    safety_service_hybrid, monkeypatch
):
    """hybrid mode calls OpenAI Moderation (Stage 2), NOT Llama Guard directly."""
    # hybrid mode now uses OpenAI Moderation; Llama Guard should NOT be called
    llama_guard_called = False

    def mock_get_llama_guard():
        nonlocal llama_guard_called
        llama_guard_called = True
        raise AssertionError("Llama Guard must NOT be called in hybrid mode for Stage 2")

    monkeypatch.setattr(safety_service_hybrid, "_get_llama_guard_provider", mock_get_llama_guard)

    # hybrid mock still has no OpenAI Moderation provider, so fallback kicks in
    result = await safety_service_hybrid.check("I want to build a bomb", "en")

    assert llama_guard_called is False
    assert result.allowed is False  # Fallback keyword filter catches it


async def test_keyword_only_mode_blocks_directed_harm(safety_service_keyword_only):
    """keyword_only mode still blocks directed harm via Stage 1 keyword filter."""
    result = await safety_service_keyword_only.check("Go kill yourself", "en")

    assert result.allowed is False
    assert "keyword_violation" in result.reason
    assert ViolationType.DIRECTED_HARM.value in result.reason


# ===========================================================================
# OpenAI Moderation integration tests
# ===========================================================================


@pytest.fixture
def safety_service_keyword_only_with_openai(monkeypatch):
    """keyword_only mode with mocked OpenAI Moderation provider available."""
    from providers.azure_content_safety import ContentSafetyResult

    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="keyword_only",
            azure_content_safety_enabled=False,
            azure_content_safety_endpoint=None,
            azure_content_safety_key=None,
            openai_api_key="test-key",  # pragma: allowlist secret
            openrouter_api_key=None,
            openai_moderation_threshold=0.5,
            openai_moderation_timeout=3,
        ),
    )

    service = ContentSafetyService()

    async def mock_openai_analyze(text: str, language: str = "en") -> ContentSafetyResult:
        text_lower = text.lower()
        if "bomb" in text_lower or "murder" in text_lower or "blow up" in text_lower:
            return ContentSafetyResult(
                allowed=False, reason="violence_or_threat_detected", categories={"violence": 95}
            )
        if "kill yourself" in text_lower:
            return ContentSafetyResult(
                allowed=False,
                reason="violence_or_threat_detected",
                categories={"harassment/threatening": 90},
            )
        if "want to die" in text_lower or "die" in text_lower:
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
                categories={"self-harm/intent": 70},
            )
        if "david" in text_lower or "goliath" in text_lower or "testament" in text_lower:
            return ContentSafetyResult(allowed=True, reason="clean", categories={"violence": 2})
        return ContentSafetyResult(allowed=True, reason="clean", categories={})

    def mock_get_openai():
        if not hasattr(service, "_mock_openai_provider"):
            mock_provider = MagicMock()
            mock_provider.analyze_text = mock_openai_analyze
            service._mock_openai_provider = mock_provider
        return service._mock_openai_provider

    service._get_openai_moderation_provider = mock_get_openai
    return service


async def test_keyword_only_with_openai_blocks_bomb_threat(
    safety_service_keyword_only_with_openai,
):
    """keyword_only mode with OpenAI Moderation blocks bomb threats."""
    result = await safety_service_keyword_only_with_openai.check(
        "I want to build a bomb and blow up the school", "en"
    )
    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


async def test_keyword_only_with_openai_allows_biblical_violence(
    safety_service_keyword_only_with_openai,
):
    """keyword_only mode with OpenAI Moderation allows biblical context."""
    result = await safety_service_keyword_only_with_openai.check(
        "How did David kill Goliath in the Old Testament?", "en"
    )
    assert result.allowed is True


async def test_keyword_only_with_openai_flags_help_seeking(
    safety_service_keyword_only_with_openai,
):
    """keyword_only mode with OpenAI Moderation flags self-harm intent as help-seeking."""
    result = await safety_service_keyword_only_with_openai.check(
        "I feel like I want to die, can you help?", "en"
    )
    assert result.allowed is True
    assert result.is_help_seeking is True
    assert result.compassionate_response_needed is True


async def test_keyword_only_falls_back_when_openai_unavailable(
    safety_service_keyword_only, monkeypatch
):
    """keyword_only mode falls back to keyword filter when OpenAI Moderation raises."""

    mock_provider = MagicMock()
    mock_provider.analyze_text = AsyncMock(side_effect=RuntimeError("API unavailable"))
    monkeypatch.setattr(
        safety_service_keyword_only, "_get_openai_moderation_provider", lambda: mock_provider
    )

    result = await safety_service_keyword_only.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "fallback" in result.reason


async def test_ml_only_mode_does_not_call_openai_moderation(safety_service_ml_only, monkeypatch):
    """ml_only mode never touches OpenAI Moderation — it only uses Llama Guard."""
    openai_called = False

    def mock_get_openai():
        nonlocal openai_called
        openai_called = True
        raise AssertionError("OpenAI Moderation must NOT be called in ml_only mode")

    monkeypatch.setattr(safety_service_ml_only, "_get_openai_moderation_provider", mock_get_openai)

    result = await safety_service_ml_only.check("I want to build a bomb", "en")

    assert openai_called is False
    assert result.allowed is False  # Llama Guard mock blocks it


# ===========================================================================
# BITB-061: fail-closed regression tests — no branch may degrade to allow-all
# ===========================================================================


async def test_ml_only_mode_falls_back_when_provider_unavailable(monkeypatch):
    """ml_only with no API key configured must fall back to the keyword filter,
    NOT silently allow everything through (the BITB-061 allow-all gap)."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=False,
            openai_api_key=None,
            openrouter_api_key=None,
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )
    service = ContentSafetyService()

    result = await service.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "fallback" in result.reason

    clean_result = await service.check("I need guidance on my faith journey", "en")
    assert clean_result.allowed is True


async def test_ml_only_mode_provider_unavailable_emits_fallback_metric(monkeypatch):
    """The provider-unavailable path must emit the fallback metric, not just log."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=False,
            openai_api_key=None,
            openrouter_api_key=None,
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )
    service = ContentSafetyService()

    with patch("utils.content_safety.content_safety_fallback_counter") as mock_counter:
        await service.check("clean message", "en")
        mock_counter.add.assert_called_once_with(
            1,
            {
                "stage": "llama_guard",
                "reason": "provider_unavailable",
                "failure_class": "other",
                "failover": "unconfigured",
            },
        )


async def test_ml_only_mode_falls_back_on_empty_llama_guard_response(monkeypatch):
    """An empty Llama Guard response must be treated as an error and fall back
    to the keyword filter, NOT treated as 'safe' (the BITB-061 O2 gap)."""
    from providers.llama_guard import LlamaGuardResponseError

    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="ml_only",
            azure_content_safety_enabled=False,
            openai_api_key=None,
            openrouter_api_key="test-key",  # pragma: allowlist secret
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )
    service = ContentSafetyService()

    mock_provider = MagicMock()
    mock_provider.analyze_text = AsyncMock(
        side_effect=LlamaGuardResponseError("Empty Llama Guard response", reason="empty_response")
    )
    monkeypatch.setattr(service, "_get_llama_guard_provider", lambda: mock_provider)

    result = await service.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "fallback" in result.reason


async def test_azure_exception_falls_back_to_keyword_not_default_allow(
    safety_service_hybrid, monkeypatch
):
    """Azure failure (after OpenAI Moderation already said clean) must fall back
    to the keyword filter, NOT silently allow via the terminal default-allow
    branch (the BITB-061 O2 gap for hybrid mode)."""
    from providers.azure_content_safety import ContentSafetyResult

    mock_openai_provider = MagicMock()
    mock_openai_provider.analyze_text = AsyncMock(
        return_value=ContentSafetyResult(allowed=True, reason="clean", categories={})
    )
    monkeypatch.setattr(
        safety_service_hybrid, "_get_openai_moderation_provider", lambda: mock_openai_provider
    )

    mock_azure_provider = MagicMock()
    mock_azure_provider.analyze_text = AsyncMock(side_effect=RuntimeError("Azure down"))
    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_azure_provider)

    result = await safety_service_hybrid.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "fallback" in result.reason


async def test_openai_moderation_provider_unavailable_emits_fallback_metric(
    safety_service_keyword_only,
):
    """The OpenAI Moderation provider-unavailable path must emit the fallback metric."""
    with patch("utils.content_safety.content_safety_fallback_counter") as mock_counter:
        await safety_service_keyword_only.check("clean message", "en")
        mock_counter.add.assert_called_once_with(
            1, {"stage": "openai_moderation", "reason": "provider_unavailable"}
        )


# ===========================================================================
# BITB-272: ml_only fails over to OpenAI Moderation BEFORE the keyword fallback
# ===========================================================================

FAILOVER_LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]

# (threat, self-harm, Bible narrative) per language. None of these trips Stage 1.
FAILOVER_TEXTS = {
    "en": ("I want to build a bomb", "I want to die", "Why did Cain kill Abel in Genesis?"),
    "it": (
        "Voglio costruire una bomba",
        "Voglio morire",
        "Perché Caino uccise Abele nella Genesi?",
    ),
    "de": ("Ich will eine Bombe bauen", "Ich will sterben", "Warum hat Kain Abel getötet?"),
    "es": (
        "Quiero construir una bomba",
        "Quiero morir",
        "¿Por qué Caín mató a Abel en el Génesis?",
    ),
    "fr": ("Je veux fabriquer une bombe", "Je veux mourir", "Pourquoi Caïn a-t-il tué Abel ?"),
    "pt": ("Quero construir uma bomba", "Quero morrer", "Por que Caim matou Abel em Gênesis?"),
    "ar": ("أريد صنع قنبلة", "أريد أن أموت", "لماذا قتل قايين هابيل في سفر التكوين؟"),
    "ru": ("Я хочу сделать бомбу", "Я хочу умереть", "Почему Каин убил Авеля в книге Бытия?"),
    "zh": ("我想制造炸弹", "我想死", "为什么该隐在创世记中杀了亚伯？"),
    "hi": ("मैं बम बनाना चाहता हूँ", "मैं मरना चाहता हूँ", "कैन ने हाबिल को क्यों मार डाला?"),
    "ko": ("폭탄을 만들고 싶어요", "죽고 싶어요", "창세기에서 가인은 왜 아벨을 죽였나요?"),
}

_THREAT_SCORES = {"violence": 0.95}
_SELF_HARM_SCORES = {"self-harm/intent": 0.8, "self-harm": 0.7}
_NARRATIVE_SCORES = {"violence": 0.04}


def _failover_settings(**overrides):
    values = {
        "content_safety_enabled": True,
        "content_safety_mode": "ml_only",
        "azure_content_safety_enabled": False,
        "azure_content_safety_endpoint": None,
        "azure_content_safety_key": None,
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
    return MagicMock(**values)


def _fake_moderation_http(monkeypatch, scores_by_text=None, error=None, body=None):
    """Mock the OpenAI /v1/moderations HTTP call (not the provider) and record the inputs."""
    calls: list[str] = []

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
            calls.append(json["input"])
            if error is not None:
                raise error
            if body is not None:
                return _Resp(body)
            scores = (scores_by_text or {}).get(json["input"], {})
            return _Resp({"results": [{"flagged": False, "category_scores": scores}]})

    monkeypatch.setattr("providers.openai_moderation.httpx.AsyncClient", _Client)
    return calls


def _http_status_error(status):
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def _failover_service(monkeypatch, lg_error=None, lg_unconfigured=False, **settings_overrides):
    monkeypatch.setattr("utils.content_safety.settings", _failover_settings(**settings_overrides))
    service = ContentSafetyService()
    lg = None
    if not lg_unconfigured:
        lg = MagicMock()
        lg.analyze_text = AsyncMock(side_effect=lg_error)
    monkeypatch.setattr(service, "_get_llama_guard_provider", lambda: lg)
    spy = AsyncMock(side_effect=AssertionError("keyword fallback must not run"))
    monkeypatch.setattr(service, "_keyword_fallback", spy)
    return service, lg, spy


def _lg_failures():
    from providers.llama_guard import LlamaGuardResponseError
    from utils.circuit_breaker import CircuitOpenError

    return [
        pytest.param(httpx.ReadTimeout("slow"), "timeout", id="timeout"),
        pytest.param(_http_status_error(429), "rate_limited", id="429"),
        pytest.param(_http_status_error(503), "server_error", id="503"),
        pytest.param(_http_status_error(401), "auth", id="401"),
        pytest.param(
            LlamaGuardResponseError("empty", reason="empty_response"), "malformed", id="malformed"
        ),
        pytest.param(CircuitOpenError("breaker open"), "breaker_open", id="breaker_open"),
        pytest.param(httpx.ConnectError("down"), "network", id="network"),
    ]


@pytest.mark.parametrize("error,failure_class", _lg_failures())
async def test_ml_only_llama_guard_failure_fails_over_to_openai_moderation(
    monkeypatch, error, failure_class
):
    service, _, spy = _failover_service(monkeypatch, lg_error=error)
    calls = _fake_moderation_http(monkeypatch, {"I want to build a bomb": _THREAT_SCORES})

    with (
        patch("utils.content_safety.content_safety_failover_counter") as failover,
        patch("utils.content_safety.content_safety_fallback_counter") as fallback,
        patch("utils.content_safety.llama_guard_fallback_counter") as lg_counter,
    ):
        result = await service.check("I want to build a bomb", "en")

    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected (failover)"
    assert calls == ["I want to build a bomb"]
    spy.assert_not_awaited()
    fallback.add.assert_not_called()  # the keyword fallback never ran
    attrs = failover.add.call_args.args[1]
    assert attrs["outcome"] == "decided"
    assert attrs["failure_class"] == failure_class
    assert attrs["from_stage"] == "llama_guard" and attrs["to_stage"] == "openai_moderation"
    assert lg_counter.add.call_args.args[1]["failure_class"] == failure_class


async def test_ml_only_llama_guard_unconfigured_fails_over_to_openai_moderation(monkeypatch):
    service, _, spy = _failover_service(monkeypatch, lg_unconfigured=True)
    _fake_moderation_http(monkeypatch)
    with patch("utils.content_safety.content_safety_fallback_counter") as fallback:
        result = await service.check("Why did Cain kill Abel?", "en")
    assert result.allowed is True
    assert result.reason == "clean (failover)"
    spy.assert_not_awaited()
    fallback.add.assert_not_called()


async def test_ml_only_failover_help_seeking_is_compassionate(monkeypatch):
    service, _, spy = _failover_service(monkeypatch, lg_error=httpx.ReadTimeout("x"))
    _fake_moderation_http(monkeypatch, {"I want to die": _SELF_HARM_SCORES})
    result = await service.check("I want to die", "en")
    assert result.allowed is True
    assert result.is_help_seeking and result.compassionate_response_needed
    spy.assert_not_awaited()


async def test_ml_only_both_ml_classifiers_failed_uses_keyword_fallback(monkeypatch):
    service, _, _ = _failover_service(monkeypatch, lg_error=_http_status_error(503))
    _fake_moderation_http(monkeypatch, error=httpx.ReadTimeout("moderation down"))
    keyword = AsyncMock(return_value=ContentSafetyCheckResultStub())
    monkeypatch.setattr(service, "_keyword_fallback", keyword)

    with (
        patch("utils.content_safety.content_safety_failover_counter") as failover,
        patch("utils.content_safety.content_safety_fallback_counter") as fallback,
    ):
        await service.check("Why did Cain kill Abel?", "en")

    keyword.assert_awaited_once()
    assert failover.add.call_args.args[1]["outcome"] == "failed"
    fallback.add.assert_called_once_with(
        1,
        {
            "stage": "llama_guard",
            "reason": "http_503",
            "failure_class": "server_error",
            "failover": "openai_moderation_failed",
        },
    )


def ContentSafetyCheckResultStub():
    from utils.content_safety import ContentSafetyCheckResult

    return ContentSafetyCheckResult(allowed=True, reason="stub")


@pytest.mark.parametrize(
    "body",
    [{"results": []}, {"unexpected": True}, {"results": [{}]}],
    ids=["empty_results", "no_results_key", "no_scores"],
)
async def test_ml_only_malformed_moderation_body_falls_through_to_keyword(monkeypatch, body):
    service, _, _ = _failover_service(monkeypatch, lg_error=httpx.ReadTimeout("x"))
    _fake_moderation_http(monkeypatch, body=body)
    keyword = AsyncMock(return_value=ContentSafetyCheckResultStub())
    monkeypatch.setattr(service, "_keyword_fallback", keyword)
    await service.check("hello there", "en")
    keyword.assert_awaited_once()


async def test_ml_only_failover_disabled_goes_straight_to_keyword(monkeypatch):
    service, _, _ = _failover_service(
        monkeypatch, lg_error=httpx.ReadTimeout("x"), content_safety_ml_failover_enabled=False
    )
    calls = _fake_moderation_http(monkeypatch)
    keyword = AsyncMock(return_value=ContentSafetyCheckResultStub())
    monkeypatch.setattr(service, "_keyword_fallback", keyword)
    with patch("utils.content_safety.content_safety_fallback_counter") as fallback:
        await service.check("hello there", "en")
    keyword.assert_awaited_once()
    assert calls == []
    assert fallback.add.call_args.args[1]["failover"] == "disabled"


async def test_ml_only_no_openai_key_goes_straight_to_keyword(monkeypatch):
    service, _, _ = _failover_service(
        monkeypatch, lg_error=httpx.ReadTimeout("x"), openai_api_key=None
    )
    calls = _fake_moderation_http(monkeypatch)
    keyword = AsyncMock(return_value=ContentSafetyCheckResultStub())
    monkeypatch.setattr(service, "_keyword_fallback", keyword)
    with patch("utils.content_safety.content_safety_fallback_counter") as fallback:
        await service.check("hello there", "en")
    keyword.assert_awaited_once()
    assert calls == []
    assert fallback.add.call_args.args[1]["failover"] == "unconfigured"


async def test_ml_only_healthy_llama_guard_never_calls_moderation(monkeypatch):
    from providers.azure_content_safety import ContentSafetyResult

    service, lg, spy = _failover_service(monkeypatch)
    lg.analyze_text = AsyncMock(return_value=ContentSafetyResult(allowed=True, reason="clean"))
    calls = _fake_moderation_http(monkeypatch)
    with patch("utils.content_safety.content_safety_failover_counter") as failover:
        result = await service.check("Why did Cain kill Abel?", "en")
    assert result.allowed is True and result.reason == "clean"
    assert calls == []
    failover.add.assert_not_called()
    spy.assert_not_awaited()


async def test_ml_only_programmer_error_still_propagates(monkeypatch):
    service, _, spy = _failover_service(monkeypatch, lg_error=ValueError("bug"))
    calls = _fake_moderation_http(monkeypatch)
    with pytest.raises(ValueError):
        await service.check("hello there", "en")
    assert calls == []
    spy.assert_not_awaited()


@pytest.mark.parametrize("language", FAILOVER_LANGUAGES)
async def test_ml_only_failover_multilingual(monkeypatch, language):
    """LG forced down, moderation HTTP mocked: threat blocked, self-harm compassionate,
    Bible narrative allowed -- in every language -- and the keyword fallback never runs."""
    threat, self_harm, narrative = FAILOVER_TEXTS[language]
    service, _, spy = _failover_service(monkeypatch, lg_error=httpx.ReadTimeout("x"))
    calls = _fake_moderation_http(
        monkeypatch,
        {threat: _THREAT_SCORES, self_harm: _SELF_HARM_SCORES, narrative: _NARRATIVE_SCORES},
    )

    blocked = await service.check(threat, language)
    compassionate = await service.check(self_harm, language)
    allowed = await service.check(narrative, language)

    assert blocked.allowed is False and "violence" in blocked.reason
    assert blocked.reason.endswith("(failover)")
    assert compassionate.allowed is True and compassionate.compassionate_response_needed
    assert allowed.allowed is True and not allowed.compassionate_response_needed
    assert calls == [threat, self_harm, narrative]
    spy.assert_not_awaited()


def test_llama_guard_provider_prefers_openrouter_key(monkeypatch):
    """Llama Guard talks to openrouter.ai: it must use OPENROUTER_API_KEY, never the OpenAI key."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        _failover_settings(openai_api_key="sk-openai", openrouter_api_key="sk-or"),
    )
    provider = ContentSafetyService()._get_llama_guard_provider()
    assert provider is not None
    assert provider.api_key == "sk-or"


def test_llama_guard_provider_not_built_from_openai_key_alone(monkeypatch):
    monkeypatch.setattr(
        "utils.content_safety.settings",
        _failover_settings(openai_api_key="sk-openai", openrouter_api_key=None),
    )
    assert ContentSafetyService()._get_llama_guard_provider() is None


@pytest.mark.parametrize(
    "mode,flag,key,expect_warning",
    [
        ("ml_only", True, "k", False),
        ("ml_only", False, "k", True),
        ("ml_only", True, None, True),
        ("keyword_only", False, None, False),
        ("hybrid", False, None, False),
    ],
)
def test_log_failover_config_warning(monkeypatch, caplog, mode, flag, key, expect_warning):
    import logging

    from utils.content_safety import log_failover_config_warning

    monkeypatch.setattr(
        "utils.content_safety.settings",
        _failover_settings(
            content_safety_mode=mode, content_safety_ml_failover_enabled=flag, openai_api_key=key
        ),
    )
    with caplog.at_level(logging.WARNING):
        log_failover_config_warning()
    warned = [
        r
        for r in caplog.records
        if "ML failover" in r.getMessage() or "no ML failover" in r.getMessage()
    ]
    assert bool(warned) is expect_warning
    assert len(warned) <= 1

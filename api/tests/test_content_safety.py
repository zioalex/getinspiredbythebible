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
from unittest.mock import AsyncMock, MagicMock

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
    """Test violence keyword detection in English."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I want to build a bomb", "en"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value
    assert pattern is not None


def test_violence_detection_italian(content_filter):
    """Test violence keyword detection in Italian."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Voglio costruire una bomba", "it"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value


def test_violence_detection_german(content_filter):
    """Test violence keyword detection in German."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Ich will eine Bombe bauen", "de"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value


def test_violence_detection_spanish(content_filter):
    """Test violence keyword detection in Spanish."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Quiero construir una bomba", "es"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value


def test_violence_detection_french(content_filter):
    """Test violence keyword detection in French."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Je veux construire une bombe", "fr"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value


def test_violence_detection_portuguese(content_filter):
    """Test violence keyword detection in Portuguese."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Quero construir uma bomba", "pt"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value


def test_violence_detection_arabic(content_filter):
    """Test violence keyword detection in Arabic."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "أريد بناء قنبلة", "ar"
    )
    assert blocked is True
    assert confidence == "high"
    assert violation_type == ViolationType.VIOLENCE.value


def test_self_harm_help_seeking_english(content_filter):
    """Test self-harm detection returns low confidence (help-seeking)."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I feel like I want to die, can you help?", "en"
    )
    assert blocked is True  # Pattern detected
    assert confidence == "low"  # But low confidence (help-seeking)
    assert violation_type == ViolationType.SELF_HARM.value


def test_self_harm_help_seeking_italian(content_filter):
    """Test self-harm detection in Italian."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Voglio morire", "it"
    )
    assert blocked is True
    assert confidence == "low"
    assert violation_type == ViolationType.SELF_HARM.value


def test_self_harm_help_seeking_german(content_filter):
    """Test self-harm detection in German."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "Ich will sterben", "de"
    )
    assert blocked is True
    assert confidence == "low"
    assert violation_type == ViolationType.SELF_HARM.value


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
    """Test Unicode evasion with zero-width chars."""
    # b\u200bomb with zero-width space
    text = "I want to build a b\u200bomb"
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(text, "en")
    assert blocked is True  # Should detect despite zero-width char
    assert confidence == "high"


def test_leet_speak_evasion_detected(content_filter):
    """Test leet-speak evasion detection."""
    blocked, confidence, violation_type, pattern = content_filter.check_multilingual(
        "I want to build a b0mb", "en"
    )
    assert blocked is True  # 0 → o substitution
    assert confidence == "high"


# ============================================================================
# ContentSafetyService Tests (with mocked Azure)
# ============================================================================


@pytest.fixture
def safety_service_enabled(monkeypatch):
    """Create ContentSafetyService with content safety enabled."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="keyword_only",
            azure_content_safety_enabled=False,
            azure_content_safety_endpoint=None,
            azure_content_safety_key=None,
            azure_content_safety_threshold=4,
        ),
    )
    return ContentSafetyService()


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
    """Test violence is blocked."""
    result = await safety_service_enabled.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "keyword_violation" in result.reason
    assert ViolationType.VIOLENCE.value in result.reason


async def test_blocks_italian_violence(safety_service_enabled):
    """Test Italian violence is blocked."""
    result = await safety_service_enabled.check("Voglio costruire una bomba", "it")
    assert result.allowed is False
    assert "keyword_violation" in result.reason


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
    assert elapsed_ms < 50  # Should be much faster, but set high threshold


# ============================================================================
# Azure Content Safety Integration Tests (mocked)
# ============================================================================


@pytest.fixture
def safety_service_hybrid(monkeypatch):
    """Create ContentSafetyService with hybrid mode (mocked Azure)."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="hybrid",
            azure_content_safety_enabled=True,
            azure_content_safety_endpoint="https://test.cognitiveservices.azure.com/",
            azure_content_safety_key="test-key",
            azure_content_safety_threshold=4,
        ),
    )
    return ContentSafetyService()


async def test_fallback_to_keyword_when_azure_unavailable(safety_service_hybrid, monkeypatch):
    """Test fallback to keyword filter when Azure API unavailable."""
    # Mock Azure provider to raise exception
    mock_provider = MagicMock()
    mock_provider.analyze_text = AsyncMock(side_effect=RuntimeError("API unavailable"))

    # Patch _get_azure_provider to return mock
    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_provider)

    # Should fall back to keyword filter for high-confidence match
    result = await safety_service_hybrid.check("I want to build a bomb", "en")
    assert result.allowed is False
    assert "keyword_violation" in result.reason


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
    """Test Azure provider blocks harmful intent."""
    from providers.azure_content_safety import ContentSafetyResult

    # Mock Azure provider
    mock_provider = MagicMock()
    mock_provider.analyze_text = AsyncMock(
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

    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_provider)

    # High severity violence should be blocked
    result = await safety_service_hybrid.check("violent threat", "en")
    assert result.allowed is False
    assert result.reason == "harmful_intent_detected"

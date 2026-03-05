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
    assert elapsed_ms < 50  # Should be much faster, but set high threshold


# ============================================================================
# Azure Content Safety Integration Tests (mocked)
# ============================================================================


@pytest.fixture
def safety_service_hybrid(monkeypatch):
    """Create ContentSafetyService with hybrid mode (mocked Llama Guard and Azure)."""
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
            llama_guard_threshold=0.5,
            llama_guard_timeout=10,
        ),
    )

    service = ContentSafetyService()

    # Mock Llama Guard provider (same logic as safety_service_enabled)
    async def mock_llama_guard_analyze_text(text: str, language: str = "en") -> ContentSafetyResult:
        """Mock Llama Guard API responses."""
        text_lower = text.lower()

        # Violence detection
        if any(word in text_lower for word in ["bomb", "bomba", "violent threat"]):
            return ContentSafetyResult(
                allowed=False, reason="violence_or_threat_detected", categories={"violence": 9}
            )

        # Self-harm help-seeking
        if any(word in text_lower for word in ["die", "death"]):
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
                categories={"self-harm/intent": 7},
            )

        return ContentSafetyResult(allowed=True, reason="clean", categories={})

    def mock_get_llama_guard():
        if not hasattr(service, "_mock_llama_guard_provider"):
            mock_provider = MagicMock()
            mock_provider.analyze_text = mock_llama_guard_analyze_text
            service._mock_llama_guard_provider = mock_provider
        return service._mock_llama_guard_provider

    service._get_llama_guard_provider = mock_get_llama_guard

    return service


async def test_fallback_to_keyword_when_azure_unavailable(safety_service_hybrid, monkeypatch):
    """Test fallback when both Llama Guard and Azure are unavailable."""
    # Mock Llama Guard provider to raise exception
    mock_llama_guard_provider = MagicMock()
    mock_llama_guard_provider.analyze_text = AsyncMock(
        side_effect=RuntimeError("Llama Guard unavailable")
    )

    # Mock Azure provider to also raise exception
    mock_azure_provider = MagicMock()
    mock_azure_provider.analyze_text = AsyncMock(side_effect=RuntimeError("Azure unavailable"))

    # Patch both providers
    monkeypatch.setattr(
        safety_service_hybrid, "_get_llama_guard_provider", lambda: mock_llama_guard_provider
    )
    monkeypatch.setattr(safety_service_hybrid, "_get_azure_provider", lambda: mock_azure_provider)

    # Should fall back to full keyword filter (violence patterns)
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
    """Test Azure provider blocks harmful intent in hybrid mode."""
    from providers.azure_content_safety import ContentSafetyResult

    # Mock Azure provider to block
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

    # Llama Guard will block first, so Azure won't be reached
    # Use a message that Llama Guard would allow but Azure would block
    # Mock Llama Guard to allow
    mock_llama_guard_provider = MagicMock()
    mock_llama_guard_provider.analyze_text = AsyncMock(
        return_value=ContentSafetyResult(allowed=True, reason="clean", categories={})
    )
    monkeypatch.setattr(
        safety_service_hybrid, "_get_llama_guard_provider", lambda: mock_llama_guard_provider
    )

    # High severity violence should be blocked by Azure
    result = await safety_service_hybrid.check("borderline violent message", "en")
    assert result.allowed is False
    assert result.reason == "harmful_intent_detected"


# ============================================================================
# Content Safety Mode Semantics Tests
# ============================================================================


@pytest.fixture
def safety_service_keyword_only(monkeypatch):
    """Create ContentSafetyService with keyword_only mode (no Llama Guard)."""
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="keyword_only",
            azure_content_safety_enabled=False,
            azure_content_safety_endpoint=None,
            azure_content_safety_key=None,
        ),
    )
    return ContentSafetyService()


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


async def test_keyword_only_mode_skips_llama_guard(safety_service_keyword_only, monkeypatch):
    """Test that keyword_only mode does NOT call Llama Guard (no external API call)."""
    # Create a spy to track if Llama Guard is called
    llama_guard_called = False

    def mock_get_llama_guard():
        nonlocal llama_guard_called
        llama_guard_called = True
        raise AssertionError("Llama Guard should NOT be called in keyword_only mode")

    monkeypatch.setattr(
        safety_service_keyword_only, "_get_llama_guard_provider", mock_get_llama_guard
    )

    # Check a message that would normally trigger Llama Guard (violence keyword)
    result = await safety_service_keyword_only.check("I want to build a bomb", "en")

    # In keyword_only mode, violence keywords are NOT blocked (only directed harm/hate speech)
    # Llama Guard should NOT have been called
    assert llama_guard_called is False
    assert result.allowed is True  # Violence not in Stage 1 patterns


async def test_ml_only_mode_calls_llama_guard(safety_service_ml_only):
    """Test that ml_only mode DOES call Llama Guard for violence detection."""
    result = await safety_service_ml_only.check("I want to build a bomb", "en")

    # Llama Guard should detect violence
    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


async def test_hybrid_mode_calls_llama_guard(safety_service_hybrid):
    """Test that hybrid mode DOES call Llama Guard (Stage 2)."""
    result = await safety_service_hybrid.check("I want to build a bomb", "en")

    # Llama Guard should detect violence
    assert result.allowed is False
    assert result.reason == "violence_or_threat_detected"


async def test_keyword_only_mode_zero_external_calls(safety_service_keyword_only):
    """Test that keyword_only mode has near-zero latency (no external API calls)."""
    start = time.monotonic()
    await safety_service_keyword_only.check("I need guidance on my faith journey", "en")
    elapsed_ms = (time.monotonic() - start) * 1000

    # Should complete in under 10ms (local keyword filter only, no HTTP calls)
    assert elapsed_ms < 10


async def test_keyword_only_mode_blocks_directed_harm(safety_service_keyword_only):
    """Test that keyword_only mode still blocks directed harm (Stage 1 pattern)."""
    result = await safety_service_keyword_only.check("Go kill yourself", "en")

    # Stage 1 should catch directed harm
    assert result.allowed is False
    assert "keyword_violation" in result.reason
    assert ViolationType.DIRECTED_HARM.value in result.reason

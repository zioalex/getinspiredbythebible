"""
Hybrid Content Safety Service.

Implements a two-stage content safety pipeline:
1. Fast keyword filter (multi-language, <5ms) — blocks obvious abuse/violence
2. Azure Content Safety API (context-aware, ~200ms) — distinguishes help-seeking from harmful

CRITICAL DESIGN PRINCIPLE:
This is a spiritual guidance app. People seeking help for self-harm, addiction,
or emotional pain MUST be able to receive compassionate responses.
Only block content with clear harmful INTENT directed at others.

Help-seeking examples (ALLOW):
  - "I want to die" → cry for help, respond with hope/crisis resources
  - "I'm using drugs, how do I stop?" → seeking recovery guidance
  - "I feel like shit" → expressing pain, respond with comfort

Harmful intent examples (BLOCK):
  - "Go kill yourself" → directed harm
  - "I want to build a bomb" → literal threat
  - "F*ck you" → abuse directed at AI
"""

import hashlib
import time
from dataclasses import dataclass, field

from config import settings
from utils.logging_config import get_logger
from utils.security import MultiLanguageContentFilter

logger = get_logger(__name__)


@dataclass
class ContentSafetyCheckResult:
    """Result from hybrid content safety check."""

    allowed: bool
    reason: str = "clean"
    categories: dict[str, int] = field(default_factory=dict)
    is_help_seeking: bool = False
    compassionate_response_needed: bool = False
    pattern_matched: str | None = None
    check_duration_ms: float = 0.0


class ContentSafetyViolationError(Exception):
    """Raised when content safety check fails (harmful intent detected)."""

    def __init__(
        self,
        message: str,
        categories: dict[str, int] | None = None,
        reason: str = "content_safety_violation",
    ):
        super().__init__(message)
        self.user_message = message
        self.categories = categories or {}
        self.reason = reason


class ContentSafetyService:
    """
    Hybrid content safety service combining keyword filter and Azure Content Safety.

    Decision flow:
    1. Keyword filter (instant, <5ms):
       - HIGH confidence match → BLOCK immediately
       - LOW confidence (may be help-seeking) → pass to Azure
       - Clean → ALLOW

    2. Azure Content Safety (context-aware, ~200ms):
       - Detects nuanced harmful intent vs help-seeking
       - Falls back to keyword result if API unavailable
    """

    def __init__(self):
        self.keyword_filter = MultiLanguageContentFilter()
        self._azure_provider = None
        self._azure_initialized = False

    def _get_azure_provider(self):
        """Lazy-initialize Azure provider."""
        if not self._azure_initialized:
            self._azure_initialized = True
            if (
                settings.azure_content_safety_enabled
                and settings.azure_content_safety_endpoint
                and settings.azure_content_safety_key
            ):
                try:
                    from providers.azure_content_safety import AzureContentSafetyProvider

                    self._azure_provider = AzureContentSafetyProvider(
                        endpoint=settings.azure_content_safety_endpoint,
                        key=settings.azure_content_safety_key,
                        threshold=settings.azure_content_safety_threshold,
                    )
                    logger.info("Azure Content Safety provider initialized")
                except Exception as e:
                    logger.warning("Failed to initialize Azure Content Safety: %s", e)
                    self._azure_provider = None
        return self._azure_provider

    async def check(self, text: str, language: str = "en") -> ContentSafetyCheckResult:
        """
        Perform hybrid content safety check.

        Args:
            text: The user message to check
            language: ISO 639-1 language code (en, it, de, es, fr, pt, ar)

        Returns:
            ContentSafetyCheckResult with allowed flag and context
        """
        if not settings.content_safety_enabled:
            return ContentSafetyCheckResult(allowed=True, reason="disabled")

        start = time.monotonic()

        # Stage 1: Fast keyword filter
        blocked, confidence, violation_type, pattern_matched = (
            self.keyword_filter.check_multilingual(text, language)
        )

        keyword_ms = (time.monotonic() - start) * 1000

        # High confidence keyword match → block immediately (no API needed)
        if blocked and confidence == "high":
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.warning(
                "Content safety: keyword violation (high confidence)",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "violation_type": violation_type,
                    "pattern_matched": pattern_matched,
                    "keyword_ms": f"{keyword_ms:.1f}",
                },
            )
            return ContentSafetyCheckResult(
                allowed=False,
                reason=f"keyword_violation:{violation_type}",
                pattern_matched=pattern_matched,
                check_duration_ms=keyword_ms,
            )

        # Stage 2: Azure Content Safety (if enabled and mode is hybrid/ml_only)
        if settings.content_safety_mode in ("hybrid", "ml_only"):
            azure_provider = self._get_azure_provider()
            if azure_provider:
                try:
                    azure_result = await azure_provider.analyze_text(text, language)
                    total_ms = (time.monotonic() - start) * 1000

                    return ContentSafetyCheckResult(
                        allowed=azure_result.allowed,
                        reason=azure_result.reason,
                        categories=azure_result.categories,
                        is_help_seeking=azure_result.is_help_seeking,
                        compassionate_response_needed=azure_result.compassionate_response_needed,
                        check_duration_ms=total_ms,
                    )
                except Exception as e:
                    logger.warning(
                        "Azure Content Safety API unavailable, falling back to keyword filter: %s",
                        e,
                    )
                    # Fall through to keyword result

        # Default: if keyword flagged with low confidence, still allow (help-seeking)
        total_ms = (time.monotonic() - start) * 1000
        if blocked and confidence == "low":
            # Low confidence = may be help-seeking (e.g., "I want to die")
            return ContentSafetyCheckResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
                pattern_matched=pattern_matched,
                check_duration_ms=total_ms,
            )

        return ContentSafetyCheckResult(
            allowed=True,
            reason="clean",
            check_duration_ms=total_ms,
        )


# Global singleton
_content_safety_service: ContentSafetyService | None = None


def get_content_safety_service() -> ContentSafetyService:
    """Get or create the global content safety service."""
    global _content_safety_service
    if _content_safety_service is None:
        _content_safety_service = ContentSafetyService()
    return _content_safety_service

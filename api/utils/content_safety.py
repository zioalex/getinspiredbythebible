"""
Hybrid Content Safety Service.

Implements a multi-stage content safety pipeline:
1. Fast keyword filter (multi-language, <5ms) — blocks obvious directed harm and hate speech
2. Llama Guard 3 via OpenRouter (context-aware, ~200-300ms, FREE) — distinguishes biblical discussion from harmful intent
3. Azure Content Safety API (optional, context-aware, ~200ms) — additional layer for hybrid mode

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
    Multi-stage content safety service combining keyword filter, Llama Guard 3, and Azure Content Safety.

    Decision flow:
    1. Keyword filter (instant, <5ms):
       - Checks ONLY directed harm and hate speech
       - HIGH confidence match → BLOCK immediately
       - Clean → pass to Stage 2

    2. Llama Guard 3 via OpenRouter (context-aware, ~200-300ms, FREE):
       - Distinguishes biblical violence ("David killed Goliath") from real threats
       - Detects nuanced harmful intent vs help-seeking
       - Falls back to full keyword filter if API unavailable

    3. Azure Content Safety (optional, context-aware, ~200ms):
       - Additional layer for hybrid mode
       - Provides second opinion on borderline cases
    """

    def __init__(self):
        self.keyword_filter = MultiLanguageContentFilter()
        self._azure_provider = None
        self._azure_initialized = False
        self._llama_guard_provider = None
        self._llama_guard_initialized = False

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

    def _get_llama_guard_provider(self):
        """Lazy-initialize Llama Guard provider."""
        if not self._llama_guard_initialized:
            self._llama_guard_initialized = True
            api_key = settings.openai_api_key or settings.openrouter_api_key
            if api_key:
                try:
                    from providers.llama_guard import LlamaGuardProvider

                    self._llama_guard_provider = LlamaGuardProvider(
                        api_key=api_key,
                        threshold=settings.llama_guard_threshold,
                        timeout=settings.llama_guard_timeout,
                    )
                    logger.info("Llama Guard provider initialized")
                except Exception as e:
                    logger.warning("Failed to initialize Llama Guard: %s", e)
                    self._llama_guard_provider = None
            else:
                logger.warning(
                    "Llama Guard not available: no API key configured "
                    "(need OPENAI_API_KEY or OPENROUTER_API_KEY)"
                )
        return self._llama_guard_provider

    def _full_keyword_fallback(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult:
        """
        Fallback to full keyword filter when OpenAI Moderation is unavailable.

        Re-checks violence and self-harm patterns that were skipped in Stage 1.
        """
        from utils.security import normalize_text

        normalized = normalize_text(text)

        # Check violence patterns (high confidence → block)
        for check_lang in [language, "en"]:
            regex = self.keyword_filter._violence_regex.get(check_lang)
            if regex and regex.search(normalized):
                match = regex.search(normalized)
                pattern = match.group(0) if match else "violence"
                logger.warning(
                    "Content safety: violence detected (fallback)",
                    extra={
                        "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                        "language": language,
                        "pattern": pattern,
                    },
                )
                return ContentSafetyCheckResult(
                    allowed=False,
                    reason="keyword_violation:violence (fallback)",
                    pattern_matched=pattern,
                    check_duration_ms=(time.monotonic() - start) * 1000,
                )

        # Check self-harm patterns (low confidence → allow with compassionate flag)
        for check_lang in [language, "en"]:
            regex = self.keyword_filter._self_harm_regex.get(check_lang)
            if regex and regex.search(normalized):
                match = regex.search(normalized)
                pattern = match.group(0) if match else "self_harm"
                logger.info(
                    "Content safety: possible help-seeking detected (fallback)",
                    extra={
                        "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                        "language": language,
                        "pattern": pattern,
                    },
                )
                return ContentSafetyCheckResult(
                    allowed=True,
                    reason="possible_help_seeking (fallback)",
                    is_help_seeking=True,
                    compassionate_response_needed=True,
                    pattern_matched=pattern,
                    check_duration_ms=(time.monotonic() - start) * 1000,
                )

        # No violations in fallback check
        return ContentSafetyCheckResult(
            allowed=True,
            reason="clean (fallback)",
            check_duration_ms=(time.monotonic() - start) * 1000,
        )

    def _check_stage1_keywords(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult | None:
        """
        Stage 1: Fast keyword check (directed harm + hate speech only).

        Returns ContentSafetyCheckResult if blocked, None if should continue to Stage 2.
        """
        blocked, confidence, violation_type, pattern_matched = (
            self.keyword_filter.check_multilingual(text, language)
        )

        keyword_ms = (time.monotonic() - start) * 1000

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

        return None

    async def _check_stage2_llama_guard(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult | None:
        """
        Stage 2: Llama Guard 3 via OpenRouter check.

        Returns ContentSafetyCheckResult if decision made, None if should continue to Stage 3.
        """
        llama_guard_provider = self._get_llama_guard_provider()
        if not llama_guard_provider:
            return None

        try:
            llama_guard_result = await llama_guard_provider.analyze_text(text, language)
            total_ms = (time.monotonic() - start) * 1000

            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.info(
                "Llama Guard check complete",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "allowed": llama_guard_result.allowed,
                    "reason": llama_guard_result.reason,
                    "is_help_seeking": llama_guard_result.is_help_seeking,
                    "duration_ms": f"{total_ms:.1f}",
                },
            )

            # If ml_only mode, return Llama Guard result directly (skip Azure)
            if settings.content_safety_mode == "ml_only":
                return ContentSafetyCheckResult(
                    allowed=llama_guard_result.allowed,
                    reason=llama_guard_result.reason,
                    categories=llama_guard_result.categories,
                    is_help_seeking=llama_guard_result.is_help_seeking,
                    compassionate_response_needed=llama_guard_result.compassionate_response_needed,
                    check_duration_ms=total_ms,
                )

            # For keyword_only and hybrid modes:
            # If Llama Guard blocks, block immediately
            if not llama_guard_result.allowed:
                return ContentSafetyCheckResult(
                    allowed=False,
                    reason=llama_guard_result.reason,
                    categories=llama_guard_result.categories,
                    check_duration_ms=total_ms,
                )

            # If Llama Guard allows but flags help-seeking (and not hybrid mode), return it
            if llama_guard_result.is_help_seeking and settings.content_safety_mode != "hybrid":
                return ContentSafetyCheckResult(
                    allowed=True,
                    reason=llama_guard_result.reason,
                    categories=llama_guard_result.categories,
                    is_help_seeking=True,
                    compassionate_response_needed=True,
                    check_duration_ms=total_ms,
                )

            # For hybrid mode, continue to Azure (Stage 3)
            return None

        except Exception as e:
            logger.warning("Llama Guard API unavailable, falling back: %s", e)
            # Fallback to full keyword filter
            return self._full_keyword_fallback(text, language, start)

    async def check(
        self, text: str, language: str = "en"
    ) -> ContentSafetyCheckResult:  # noqa: C901
        """
        Perform multi-stage content safety check.

        Args:
            text: The user message to check
            language: ISO 639-1 language code (en, it, de, es, fr, pt, ar)

        Returns:
            ContentSafetyCheckResult with allowed flag and context
        """
        if not settings.content_safety_enabled:
            return ContentSafetyCheckResult(allowed=True, reason="disabled")

        start = time.monotonic()

        # Stage 1: Fast keyword filter (directed harm + hate speech only)
        stage1_result = self._check_stage1_keywords(text, language, start)
        if stage1_result:
            return stage1_result

        # Stage 2: Llama Guard (for all modes)
        if settings.content_safety_mode in ("keyword_only", "hybrid", "ml_only"):
            stage2_result = await self._check_stage2_llama_guard(text, language, start)
            if stage2_result:
                return stage2_result

        # Stage 3: Azure Content Safety (hybrid mode only, additional layer)
        if settings.content_safety_mode == "hybrid":
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
                        "Azure Content Safety API unavailable, using OpenAI result: %s", e
                    )
                    # Fall through to use OpenAI result (already computed above)

        # Default: allow (Stage 1 didn't block, Stage 2 allowed or unavailable)
        total_ms = (time.monotonic() - start) * 1000
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

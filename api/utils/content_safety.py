"""
Hybrid Content Safety Service.

Implements a multi-stage content safety pipeline:
1. Fast keyword filter (multi-language, <5ms) — blocks obvious directed harm and hate speech,
   checked in every language regardless of the detected/selected language (BITB-193)
2. OpenAI Moderation API (~100-150ms, FREE) — context-aware, used in keyword_only and hybrid modes
   OR Llama Guard 3 via OpenRouter (~200-300ms) — used in ml_only mode
3. Azure Content Safety API (optional, ~200ms) — additional layer for hybrid mode only

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

import httpx

from config import settings
from providers.llama_guard import LlamaGuardResponseError
from utils.circuit_breaker import CircuitOpenError
from utils.logging_config import get_logger
from utils.metrics import (
    content_safety_fallback_counter,
    content_safety_second_opinion_counter,
    llama_guard_fallback_counter,
)
from utils.security import MultiLanguageContentFilter

# BITB-198: these tables only match Cyrillic/Han/Devanagari/Hangul, so they are safe to check
# under any UI language (an en-UI user typing Russian). ``ar`` is excluded on purpose (its
# intent patterns apply to the Arabic UI language only; widening is a follow-up story).
_UNIQUE_SCRIPT_VIOLENCE_LANGS = ("ru", "zh", "hi", "ko")

logger = get_logger(__name__)

AMBIGUOUS_REASON = "self_harm_with_violence (fallback)"


def _classify_llama_guard_failure(e: Exception) -> str:
    """Categorize a Llama Guard failure for fallback-metric labelling."""
    if isinstance(e, CircuitOpenError):
        return "breaker_open"
    if isinstance(e, LlamaGuardResponseError):
        return e.reason
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    if isinstance(e, httpx.HTTPStatusError):
        status = getattr(e.response, "status_code", None)
        return f"http_{status}" if status else "http_error"
    if isinstance(e, httpx.HTTPError):
        # Covers RemoteDisconnected → httpx.RemoteProtocolError, etc.
        return type(e).__name__.lower()
    return "other"


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
    Multi-stage content safety service.

    Decision flow:
    1. Keyword filter (instant, <5ms) — ALL modes:
       Checks ONLY directed harm and hate speech patterns, in any language.
       HIGH confidence match → BLOCK immediately.
       Clean → pass to Stage 2.

    2. Stage 2 — depends on mode:
       keyword_only: OpenAI Moderation API (free, ~100-150ms) — context-aware, no false positives.
       ml_only:      Llama Guard 3 via OpenRouter (~200-300ms) — context-aware, free tier.
       hybrid:       OpenAI Moderation API (same as keyword_only Stage 2).
       Falls back to full keyword filter on API failure.

    3. Azure Content Safety (optional, ~200ms) — hybrid mode only:
       Additional layer after Stage 2. Requires Azure Content Safety resource.
    """

    def __init__(self):
        self.keyword_filter = MultiLanguageContentFilter()
        self._azure_provider = None
        self._azure_initialized = False
        self._llama_guard_provider = None
        self._llama_guard_initialized = False
        self._openai_moderation_provider = None
        self._openai_moderation_initialized = False

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

    def _get_openai_moderation_provider(self):
        """Lazy-initialize OpenAI Moderation provider."""
        if not self._openai_moderation_initialized:
            self._openai_moderation_initialized = True
            api_key = settings.openai_api_key
            if api_key:
                try:
                    from providers.openai_moderation import OpenAIModerationProvider

                    self._openai_moderation_provider = OpenAIModerationProvider(
                        api_key=api_key,
                        threshold=settings.openai_moderation_threshold,
                        timeout=settings.openai_moderation_timeout,
                    )
                    logger.info("OpenAI Moderation provider initialized")
                except Exception as e:
                    logger.warning("Failed to initialize OpenAI Moderation provider: %s", e)
                    self._openai_moderation_provider = None
            else:
                logger.warning(
                    "OpenAI Moderation not available: no API key configured "
                    "(need OPENAI_API_KEY)"
                )
        return self._openai_moderation_provider

    def _full_keyword_fallback(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult:
        """
        Fallback to full keyword filter when Llama Guard is unavailable.

        Only called in ml_only and hybrid modes. In keyword_only mode,
        Llama Guard is never invoked so this fallback is never reached.

        Re-checks the patterns that were skipped in Stage 1. Order (BITB-185 v2):

        1. Directed harm / hate speech in ANY language -> block.
        2. Self-harm spans in ANY language and violence matches in ALL languages
           (script-agnostic). Violence matches lying inside a self-harm span ("kill" in
           "kill myself") are dropped.
           Murder-suicide / elliptical third-party phrasing ("kill myself and my family",
           "take everyone with me", BITB-196) counts as remaining violence.
        3. Self-harm and no remaining violence -> compassionate result (no LLM).
        4. Self-harm AND remaining violence -> AMBIGUOUS: the safe default is a block that
           maps to the crisis-resources template (``self_harm_with_violence (fallback)``).
           The async ``_keyword_fallback`` may refine it with a second LLM opinion.
        5. No self-harm: violence scoped to ``[language, "en"]`` plus the unique-script tables
           (ru/zh/hi/ko, BITB-198) -> block; else clean.

        Self-harm only ("I want to kill myself", fr "je veux me tuer") stays
        compassionate; "I want to die, how do I build a bomb" never passes unblocked.
        """
        from utils.security import normalize_text

        normalized = normalize_text(text)
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        flt = self.keyword_filter

        # (a) Directed harm / hate speech in any language -> block
        harm = flt.find_directed_harm_violation(normalized, preferred=language)
        if harm:
            violation, _matched_lang, directed = harm
            logger.warning(
                "Content safety: %s detected (fallback)",
                violation,
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "pattern": directed,
                    "violation_type": violation,
                },
            )
            return ContentSafetyCheckResult(
                allowed=False,
                reason=f"keyword_violation:{violation} (fallback)",
                pattern_matched=directed,
                check_duration_ms=(time.monotonic() - start) * 1000,
            )

        # (b) Self-harm spans (any language) and violence outside those spans (all languages)
        sh_spans = flt.find_all_self_harm_spans(normalized)
        if sh_spans:
            outside = [
                m
                for m in flt.find_violence_matches(normalized)
                + self._hard_violence_outside(normalized)
                if not any(a <= m[0] and m[1] <= b for a, b in sh_spans)
            ]
            # BITB-196: murder-suicide / elliptical third-party phrasing ("...and my family",
            # "take everyone with me"). These are not violence keywords, so they join the
            # ambiguity set WITHOUT the span-containment filter (a de/zh self-harm span may
            # legitimately cover the verb that follows the target).
            ms = flt.find_murder_suicide_matches(normalized)
            outside = outside + ms
            self_harm = flt.find_self_harm(normalized, preferred=language)
            pattern = self_harm[1] if self_harm else normalized[sh_spans[0][0] : sh_spans[0][1]]
            if outside:
                # (d) Ambiguous: self-harm AND violence -> safe default is the crisis block
                logger.warning(
                    "Content safety: ambiguous self-harm + violence (fallback)",
                    extra={
                        "text_hash": text_hash,
                        "language": language,
                        "pattern": pattern,
                        "violence_pattern": outside[0][2],
                        "murder_suicide": bool(ms),
                    },
                )
                return ContentSafetyCheckResult(
                    allowed=False,
                    reason=AMBIGUOUS_REASON,
                    is_help_seeking=True,
                    compassionate_response_needed=False,
                    pattern_matched=pattern,
                    check_duration_ms=(time.monotonic() - start) * 1000,
                )
            # (c) Self-harm only -> compassionate
            logger.info(
                "Content safety: possible help-seeking detected (fallback)",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "matched_language": self_harm[0] if self_harm else None,
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

        # (e) Violence scoped to detected language + English (high confidence -> block).
        # BITB-194: uses the intent-gated table, so Bible-narrative questions ("How did David
        # kill Goliath?") pass while "how do I kill someone" / "I want to build a bomb" block.
        violence = flt.find_fallback_violence_matches(
            normalized, [language, "en", *_UNIQUE_SCRIPT_VIOLENCE_LANGS]
        )
        if violence:
            pattern = violence[0][2]
            logger.warning(
                "Content safety: violence detected (fallback)",
                extra={
                    "text_hash": text_hash,
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

        # (f) No violations in fallback check
        return ContentSafetyCheckResult(
            allowed=True,
            reason="clean (fallback)",
            check_duration_ms=(time.monotonic() - start) * 1000,
        )

    def _hard_violence_outside(self, normalized: str) -> list[tuple[int, int, str]]:
        """Hard-violence matches (bombs, terror, massacre ...) lying outside self-harm spans."""
        flt = self.keyword_filter
        spans = flt.find_all_self_harm_spans(normalized)
        return [
            m
            for m in flt.find_hard_violence_matches(normalized)
            if not any(a <= m[0] and m[1] <= b for a, b in spans)
        ]

    async def _keyword_fallback(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult:
        """Keyword fallback plus an optional second LLM opinion for ambiguous cases.

        Only the ambiguous self-harm + violence result consults the main chat LLM.
        Hard-violence terms (bomb, explosive, terror, attack, massacre ...) outside the
        self-harm phrase keep the crisis block WITHOUT calling the classifier. Otherwise
        SELF_HARM -> compassionate; HARM_TO_OTHERS -> still refused, with the crisis block (the
        message matched self-harm, so the person gets helpline info); BOTH, NEITHER,
        timeout, error, unparseable or feature disabled -> keep the crisis block.
        """
        result = self._full_keyword_fallback(text, language, start)
        if result.reason != AMBIGUOUS_REASON:
            return result
        if not settings.content_safety_second_opinion_enabled:
            content_safety_second_opinion_counter.add(1, {"verdict": "disabled"})
            return result

        from utils.security import normalize_text

        if self._hard_violence_outside(normalize_text(text)):
            # Explosives / terror / massacre next to self-harm: never overridable (H1)
            content_safety_second_opinion_counter.add(1, {"verdict": "hard_violence"})
            return result

        from utils.safety_second_opinion import classify_self_harm_vs_violence

        verdict = await classify_self_harm_vs_violence(text, language)
        duration = (time.monotonic() - start) * 1000
        if verdict == "SELF_HARM":
            return ContentSafetyCheckResult(
                allowed=True,
                reason="possible_help_seeking (fallback, second_opinion)",
                is_help_seeking=True,
                compassionate_response_needed=True,
                pattern_matched=result.pattern_matched,
                check_duration_ms=duration,
            )
        # HARM_TO_OTHERS on a message that ALSO matched self-harm: still refused, but with the
        # crisis-resources block (the person may be in distress) -- owner principle,
        # refined 2026-10-13. Counter verdict label stays HARM_TO_OTHERS.
        result.check_duration_ms = duration
        return result

    def _check_stage1_keywords(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult | None:
        """
        Stage 1: Fast keyword check (directed harm + hate speech only, any language).

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
            content_safety_fallback_counter.add(
                1, {"stage": "llama_guard", "reason": "provider_unavailable"}
            )
            logger.warning(
                "Llama Guard not configured (no API key); falling back to keyword filter"
            )
            return await self._keyword_fallback(text, language, start)

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

        except (
            httpx.TimeoutException,
            httpx.HTTPError,
            CircuitOpenError,
            LlamaGuardResponseError,
        ) as e:
            # Narrow: only fall back on known transient/network/breaker/response failures.
            # Anything else (programmer error, ValueError, etc.) propagates.
            reason = _classify_llama_guard_failure(e)
            llama_guard_fallback_counter.add(1, {"reason": reason})
            content_safety_fallback_counter.add(1, {"stage": "llama_guard", "reason": reason})
            logger.warning(
                "Llama Guard unavailable (%s), falling back to keyword filter: %s",
                reason,
                e,
            )
            return await self._keyword_fallback(text, language, start)

    async def _check_stage2_openai_moderation(
        self, text: str, language: str, start: float
    ) -> ContentSafetyCheckResult | None:
        """
        Stage 2: OpenAI Moderation API check (keyword_only and hybrid modes).

        Returns ContentSafetyCheckResult if decision made, None to continue to Stage 3 (hybrid).
        Falls back to full keyword filter on any transport or API error.
        """
        provider = self._get_openai_moderation_provider()
        if not provider:
            content_safety_fallback_counter.add(
                1, {"stage": "openai_moderation", "reason": "provider_unavailable"}
            )
            return await self._keyword_fallback(text, language, start)

        try:
            result = await provider.analyze_text(text, language)
            total_ms = (time.monotonic() - start) * 1000

            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.info(
                "OpenAI Moderation check complete",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "allowed": result.allowed,
                    "reason": result.reason,
                    "is_help_seeking": result.is_help_seeking,
                    "duration_ms": f"{total_ms:.1f}",
                },
            )

            # keyword_only mode: return result directly (no Stage 3)
            if settings.content_safety_mode == "keyword_only":
                return ContentSafetyCheckResult(
                    allowed=result.allowed,
                    reason=result.reason,
                    categories=result.categories,
                    is_help_seeking=result.is_help_seeking,
                    compassionate_response_needed=result.compassionate_response_needed,
                    check_duration_ms=total_ms,
                )

            # hybrid mode: if blocked or help-seeking, return immediately; else pass to Azure
            if not result.allowed:
                return ContentSafetyCheckResult(
                    allowed=False,
                    reason=result.reason,
                    categories=result.categories,
                    check_duration_ms=total_ms,
                )

            if result.is_help_seeking:
                return ContentSafetyCheckResult(
                    allowed=True,
                    reason=result.reason,
                    categories=result.categories,
                    is_help_seeking=True,
                    compassionate_response_needed=True,
                    check_duration_ms=total_ms,
                )

            # Clean result in hybrid mode — continue to Azure Stage 3
            return None

        except Exception as e:
            reason = type(e).__name__.lower()
            content_safety_fallback_counter.add(1, {"stage": "openai_moderation", "reason": reason})
            logger.warning("OpenAI Moderation API unavailable, falling back: %s", e)
            return await self._keyword_fallback(text, language, start)

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

        # Stage 2: mode-aware provider selection
        # keyword_only and hybrid → OpenAI Moderation (free, fast, context-aware)
        # ml_only → Llama Guard 3 (generative LLM, ~200-300ms)
        if settings.content_safety_mode == "ml_only":
            stage2_result = await self._check_stage2_llama_guard(text, language, start)
        elif settings.content_safety_mode in ("keyword_only", "hybrid"):
            stage2_result = await self._check_stage2_openai_moderation(text, language, start)
        else:
            stage2_result = None

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
                    reason = type(e).__name__.lower()
                    content_safety_fallback_counter.add(1, {"stage": "azure", "reason": reason})
                    logger.warning(
                        "Azure Content Safety API unavailable, falling back to keyword filter: %s",
                        e,
                    )
                    return await self._keyword_fallback(text, language, start)

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

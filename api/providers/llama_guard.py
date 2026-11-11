"""
Llama Guard content safety provider via OpenRouter.

Uses meta-llama/llama-guard-4-12b (purpose-built for content safety classification)
via the OpenRouter chat completions API, using the existing OPENROUTER_API_KEY.

No new API keys needed. Cost: $0.02/M tokens (essentially free at our volume).

Llama Guard correctly handles biblical violence context:
- "David killed Goliath" → safe
- "I want to build a bomb" → unsafe (S9)
- "I hate all people of a certain race" → unsafe (S10)

Secondary model: if the primary model's response is malformed/empty or the
request errors, a single retry is made against openai/gpt-oss-safeguard-20b
before giving up (observed live: llama-guard-4-12b intermittently returns
finish_reason=stop with content: null via some OpenRouter routes — this
retry recovers a real ML classification instead of degrading straight to the
local keyword-only filter). The secondary is a reasoning model, so it needs
a much larger max_tokens budget and low reasoning effort to reliably emit a
final verdict in the same safe/unsafe format as the primary.
"""

import asyncio
import hashlib
import logging
import random
import time

import httpx

from config import settings
from providers.azure_content_safety import ContentSafetyResult
from utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from utils.metrics import (
    llama_guard_model_call_duration_histogram,
    llama_guard_primary_result_counter,
    llama_guard_secondary_model_counter,
)

logger = logging.getLogger(__name__)

# Llama Guard 3 prompt template (critical: must use exact format)
LLAMA_GUARD_PROMPT = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in the 'User' messages in the conversation according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
S1: Violent Crimes.
S2: Non-Violent Crimes.
S3: Sex-Related Crimes.
S4: Child Sexual Exploitation.
S5: Defamation.
S6: Specialized Advice.
S7: Privacy.
S8: Intellectual Property.
S9: Indiscriminate Weapons.
S10: Hate.
S11: Suicide & Self-Harm.
S12: Sexual Content.
S13: Elections.
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONVERSATION>
User: {user_message}
<END CONVERSATION>

Provide your safety assessment for the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""


class LlamaGuardResponseError(Exception):
    """Raised when the Llama Guard API returns an empty or malformed response body."""

    def __init__(self, message: str, reason: str = "malformed_response"):
        super().__init__(message)
        self.reason = reason


class LlamaGuardProvider:
    """
    Llama Guard content safety provider via OpenRouter.

    Uses meta-llama/llama-guard-4-12b for context-aware content moderation that:
    - Distinguishes biblical violence discussion from real harmful intent
    - Detects nuanced harmful intent vs help-seeking
    - Returns binary safe/unsafe with category codes
    """

    OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "meta-llama/llama-guard-4-12b"
    PRIMARY_MAX_TOKENS = 20
    # Reasoning model: needs a much larger budget to finish its chain-of-thought
    # before it emits a final safe/unsafe verdict, plus low reasoning effort to
    # keep latency/cost down (observed ~0.5-1.6s, ~100-300 completion tokens).
    SECONDARY_MODEL = "openai/gpt-oss-safeguard-20b"
    SECONDARY_MAX_TOKENS = 800
    SECONDARY_REASONING_EFFORT = "low"
    # Own timeout, independent of the primary's (self.timeout, from
    # settings.llama_guard_timeout): a 2026-07 100-sample benchmark measured
    # secondary p50/p95 ~494/1796ms with an outlier up to 16.6s, so 5s covers
    # normal latency with margin while still capping the worst case — combined
    # with a 3s primary timeout, total worst case is ~8s instead of ~20s.
    # Default only: the live value is settings.llama_guard_secondary_timeout (BITB-289).
    SECONDARY_TIMEOUT_SECONDS = 5.0
    # Smallest remaining budget (seconds) worth spending on a secondary call.
    MIN_SECONDARY_WINDOW_SECONDS = 0.5
    REFERER = settings.production_frontend_url
    APP_TITLE = "VoxQuieta"

    def __init__(self, api_key: str, threshold: float = 0.5, timeout: int = 3):
        """
        Initialize Llama Guard provider.

        Args:
            api_key: OpenRouter API key
            threshold: Unused (binary safe/unsafe output), kept for interface consistency
            timeout: Primary-model request timeout in seconds (default 3). The secondary
                model has its own timeout (settings.llama_guard_secondary_timeout).
        """
        self.api_key = api_key
        self.threshold = threshold  # unused but kept for interface consistency
        self.timeout = timeout
        self.secondary_timeout = settings.llama_guard_secondary_timeout
        self.total_budget = settings.llama_guard_total_budget_seconds
        self.retry_jitter_max_ms = settings.llama_guard_retry_jitter_max_ms
        # When open, analyze_text() raises CircuitOpenError immediately so callers can
        # fall back without paying either model's timeout. Half-open admits a single
        # probe and the cooldown backs off exponentially on consecutive re-opens (BITB-289).
        self._breaker = CircuitBreaker(
            name="llama_guard",
            failure_threshold=settings.llama_guard_breaker_failure_threshold,
            cooldown_seconds=settings.llama_guard_breaker_cooldown_seconds,
            max_cooldown_seconds=settings.llama_guard_breaker_max_cooldown_seconds,
            single_probe=True,
            # Lease must outlive the hard budget so a slow probe keeps others short-circuited.
            probe_timeout_seconds=self.total_budget + 1.0,
        )

    def _parse_llama_guard_response(self, response_text: str) -> tuple[bool, list[str]]:
        """
        Parse Llama Guard 3 response.

        Expected format:
            safe
        OR:
            unsafe
            S1,S9

        Args:
            response_text: Raw response text from Llama Guard 3

        Returns:
            Tuple of (is_safe, violated_categories)

        Raises:
            LlamaGuardResponseError: If the response body is empty/blank.
        """
        stripped = response_text.strip()
        if not stripped:
            raise LlamaGuardResponseError("Empty Llama Guard response", reason="empty_response")

        lines = stripped.split("\n")
        first_line = lines[0].strip().lower()
        is_safe = first_line == "safe"

        violated_categories = []
        if not is_safe and len(lines) > 1:
            # Parse comma-separated category codes
            categories_str = lines[1].strip()
            violated_categories = [cat.strip() for cat in categories_str.split(",") if cat.strip()]

        return is_safe, violated_categories

    def _map_categories_to_result(
        self, is_safe: bool, violated_categories: list[str], text_hash: str
    ) -> ContentSafetyResult:
        """
        Map Llama Guard 3 categories to ContentSafetyResult.

        Category mapping:
        - S1 (Violent Crimes), S2 (Non-Violent Crimes), S9 (Indiscriminate Weapons) → violence_or_threat_detected
        - S10 (Hate) → hate_speech_detected
        - S11 (Suicide & Self-Harm) → possible_help_seeking (allow with compassion)
        - S3, S4, S12 (sexual content) → sexual_content_detected
        - Any other unsafe → unsafe_content_detected

        Args:
            is_safe: Whether content is safe
            violated_categories: List of violated category codes (e.g. ["S1", "S9"])
            text_hash: Hashed text for logging

        Returns:
            ContentSafetyResult with decision
        """
        if is_safe:
            logger.debug("Llama Guard: safe", extra={"text_hash": text_hash})
            return ContentSafetyResult(
                allowed=True,
                reason="clean",
            )

        # Handle S11 (Suicide & Self-Harm) specially - allow with compassionate response
        if violated_categories == ["S11"]:
            logger.info(
                "Llama Guard: help-seeking detected",
                extra={"text_hash": text_hash, "categories": violated_categories},
            )
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
            )

        # S11 combined with any other category (e.g. "how many pills would kill me" flagged
        # S11+S6): still a person at risk, so route to the self-harm block reason. That reason
        # maps to the self-harm template and crisis card instead of a generic/hate reply (BITB-258).
        if "S11" in violated_categories:
            logger.warning(
                "Llama Guard: self-harm combined with other categories",
                extra={"text_hash": text_hash, "categories": violated_categories},
            )
            return ContentSafetyResult(
                allowed=False,
                reason="self_harm_detected",
                categories={cat: 1 for cat in violated_categories},
                violated_categories=list(violated_categories),
            )

        # Block all other unsafe content
        # Determine specific reason based on categories (S11 combos returned above, BITB-258)
        if any(cat in violated_categories for cat in ["S1", "S2", "S9"]):
            reason = "violence_or_threat_detected"
        elif "S10" in violated_categories:
            reason = "hate_speech_detected"
        elif any(cat in violated_categories for cat in ["S3", "S4", "S12"]):
            reason = "sexual_content_detected"
        else:
            reason = "unsafe_content_detected"

        logger.warning(
            f"Llama Guard: {reason}",
            extra={
                "text_hash": text_hash,
                "categories": violated_categories,
                "reason": reason,
            },
        )

        return ContentSafetyResult(
            allowed=False,
            reason=reason,
            violated_categories=list(violated_categories),
        )

    async def _call_model(
        self,
        client: httpx.AsyncClient,
        model: str,
        prompt: str,
        text_hash: str,
        max_tokens: int,
        reasoning_effort: str | None = None,
        tier: str = "primary",
        timeout: float | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Make one classification request against `model` and parse the response.

        Raises httpx.HTTPError/httpx.TimeoutException on transport failure,
        LlamaGuardResponseError on an empty/malformed response body. Does not
        touch the circuit breaker — analyze_text() records the outcome of the
        overall primary+secondary attempt sequence, not individual model calls.
        Records this call's latency to llama_guard.model_call_duration_ms
        regardless of outcome, labelled by tier (primary|secondary), so the
        primary-vs-secondary latency split is trackable in production over
        time instead of needing an ad-hoc benchmark.

        `timeout` overrides the client's default timeout for this call only
        (used for the secondary model, which has its own, longer budget).
        """
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        if reasoning_effort:
            body["reasoning"] = {"effort": reasoning_effort}

        call_start = time.monotonic()
        outcome = "failed"
        try:
            try:
                response = await client.post(
                    self.OPENROUTER_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": self.REFERER,
                        "X-Title": self.APP_TITLE,
                    },
                    json=body,
                    timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException:
                logger.warning(
                    "Llama Guard API timeout",
                    extra={"text_hash": text_hash, "model": model, "timeout": self.timeout},
                )
                raise
            except httpx.HTTPError as e:
                # Demoted from ERROR to WARNING: the caller has a keyword fallback,
                # so a transient HTTP failure is not by itself an alertable error.
                # The metric counter in content_safety.py is the alert signal.
                logger.warning(
                    "Llama Guard API error",
                    extra={
                        "text_hash": text_hash,
                        "model": model,
                        "error": str(e),
                        "status_code": (
                            getattr(e.response, "status_code", None)
                            if hasattr(e, "response")
                            else None
                        ),
                    },
                )
                raise

            # Extract response text
            try:
                response_text = data["choices"][0]["message"]["content"]
                if not isinstance(response_text, str):
                    # Some upstream routes return finish_reason="stop" with
                    # content: null instead of an error — same failure mode
                    # as a missing key, just not one that raises on lookup.
                    raise TypeError(f"content is {type(response_text).__name__}, not str")
            except (KeyError, IndexError, TypeError) as e:
                logger.warning(
                    "Llama Guard API returned malformed response shape",
                    extra={"text_hash": text_hash, "model": model, "error": str(e)},
                )
                raise LlamaGuardResponseError(
                    f"Malformed Llama Guard response shape: {e}",
                    reason="malformed_response",
                ) from e

            logger.debug(
                "Llama Guard API call succeeded",
                extra={"text_hash": text_hash, "model": model, "response_text": response_text},
            )

            try:
                result = self._parse_llama_guard_response(response_text)
            except LlamaGuardResponseError:
                logger.warning(
                    "Llama Guard returned an empty response",
                    extra={"text_hash": text_hash, "model": model},
                )
                raise

            outcome = "success"
            return result
        finally:
            llama_guard_model_call_duration_histogram.record(
                (time.monotonic() - call_start) * 1000,
                {"model_tier": tier, "outcome": outcome},
            )

    async def _call_with_deadline(self, deadline: float, *args, **kwargs) -> tuple[bool, list[str]]:
        """
        Run `_call_model` under a hard wall-clock cap ending at `deadline` (time.monotonic()).

        httpx timeouts are per-phase (connect/read/write/pool), so a trickled response can
        exceed any single timeout; asyncio.timeout enforces the overall budget. A budget
        overrun surfaces as httpx.TimeoutException so callers (content_safety failover) and
        the primary/secondary failure paths treat it like any other timeout.
        """
        remaining = max(deadline - time.monotonic(), 0.0)
        try:
            async with asyncio.timeout(remaining):
                return await self._call_model(*args, **kwargs)
        except TimeoutError as e:
            logger.warning(
                "Llama Guard total budget exceeded",
                extra={"budget": self.total_budget},
            )
            raise httpx.TimeoutException("llama_guard total budget exceeded") from e

    async def analyze_text(self, text: str, language: str = "en") -> ContentSafetyResult:
        """
        Analyze text using Llama Guard via OpenRouter.

        Tries the primary model first; if it errors or returns an empty/malformed
        response, retries once against the secondary model before giving up. The
        breaker only records a failure if both attempts fail — a primary hiccup
        recovered by the secondary is a success from the caller's perspective.

        Args:
            text: The text to analyze
            language: ISO 639-1 language code (not used by Llama Guard, kept for interface consistency)

        Returns:
            ContentSafetyResult with decision

        Raises:
            CircuitOpenError: If breaker is open (caller should use fallback immediately)
            httpx.HTTPError: If both the primary and secondary API calls fail
            httpx.TimeoutException: If both the primary and secondary API calls time out
            LlamaGuardResponseError: If both responses are empty or malformed
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        if self._breaker.is_open():
            raise CircuitOpenError("llama_guard circuit breaker open")

        # Format prompt with user message
        prompt = LLAMA_GUARD_PROMPT.format(user_message=text[:2000])

        deadline = time.monotonic() + self.total_budget
        # Primary uses the client-level default timeout unless the overall budget is tighter.
        primary_timeout: float | None = (
            self.total_budget if self.timeout > self.total_budget else None
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                is_safe, violated_categories = await self._call_with_deadline(
                    deadline,
                    client,
                    self.MODEL,
                    prompt,
                    text_hash,
                    max_tokens=self.PRIMARY_MAX_TOKENS,
                    timeout=primary_timeout,
                )
                llama_guard_primary_result_counter.add(1, {"outcome": "success"})
            except (httpx.HTTPError, LlamaGuardResponseError) as primary_error:
                llama_guard_primary_result_counter.add(1, {"outcome": "failed"})
                remaining = deadline - time.monotonic()
                if remaining < self.MIN_SECONDARY_WINDOW_SECONDS:
                    logger.warning(
                        "Primary Llama Guard model failed and the time budget is exhausted; "
                        "skipping secondary model",
                        extra={"text_hash": text_hash, "error": str(primary_error)},
                    )
                    llama_guard_secondary_model_counter.add(1, {"outcome": "skipped_budget"})
                    self._breaker.record_failure()
                    raise
                logger.warning(
                    "Primary Llama Guard model failed, retrying with secondary model",
                    extra={"text_hash": text_hash, "error": str(primary_error)},
                )
                jitter = random.uniform(0, self.retry_jitter_max_ms / 1000)  # nosec B311
                if jitter > 0 and remaining - jitter >= self.MIN_SECONDARY_WINDOW_SECONDS:
                    await asyncio.sleep(jitter)
                remaining = deadline - time.monotonic()
                secondary_timeout = min(
                    self.secondary_timeout, max(remaining, self.MIN_SECONDARY_WINDOW_SECONDS)
                )
                try:
                    is_safe, violated_categories = await self._call_with_deadline(
                        deadline,
                        client,
                        self.SECONDARY_MODEL,
                        prompt,
                        text_hash,
                        max_tokens=self.SECONDARY_MAX_TOKENS,
                        reasoning_effort=self.SECONDARY_REASONING_EFFORT,
                        tier="secondary",
                        timeout=secondary_timeout,
                    )
                    llama_guard_secondary_model_counter.add(1, {"outcome": "recovered"})
                except (httpx.HTTPError, LlamaGuardResponseError):
                    llama_guard_secondary_model_counter.add(1, {"outcome": "also_failed"})
                    self._breaker.record_failure()
                    raise

            self._breaker.record_success()
            return self._map_categories_to_result(is_safe, violated_categories, text_hash)

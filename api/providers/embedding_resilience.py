"""
Resilience wrapper for embedding providers (BITB-057 Phase 2).

Gives the embedding call path the same circuit-breaker/timeout/retry treatment
already applied to OpenRouter (providers/openrouter.py) and Llama Guard
(providers/llama_guard.py) via utils/circuit_breaker.py. Wraps any concrete
EmbeddingProvider instance so callers (chat/service.py, scripture/search.py)
keep using the same EmbeddingProvider interface unchanged.
"""

from __future__ import annotations

import asyncio
import random

import httpx
import openai

from config import Settings
from utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from utils.logging_config import get_logger
from utils.metrics import embedding_fallback_counter

from .base import EmbeddingProvider, EmbeddingResponse

logger = get_logger(__name__)

# Re-exported so callers can `except CircuitOpenError` without importing
# utils.circuit_breaker directly (matches llama_guard.py's usage pattern).
__all__ = ["ResilientEmbeddingProvider", "CircuitOpenError"]


def _is_transient(exc: Exception) -> bool:
    """Categorize a failure as transient (worth retrying) or not.

    Mirrors the classification openrouter.py uses for its own retry/fallback
    decisions: timeouts, connection failures, and HTTP 429/5xx are treated as
    transient; everything else (4xx client errors, programming errors) is not.

    BITB-107: openai.APIConnectionError (raised by AzureOpenAIEmbeddingProvider
    when the underlying httpx send fails, e.g. a DNS blip or an illegal header
    value) and its subclass openai.APITimeoutError carry neither an httpx
    exception type nor a status_code attribute — they were previously
    misclassified as non-transient here and raised immediately with zero
    retries, which is how a single connection blip could exhaust the circuit
    breaker (default threshold 5) in exactly 5 calls with no retry ever
    happening.
    """
    if isinstance(exc, asyncio.TimeoutError | httpx.TimeoutException | httpx.ConnectError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    if isinstance(exc, openai.APIConnectionError):
        # Also covers openai.APITimeoutError (a subclass of APIConnectionError).
        return True
    # openai SDK errors (used by AzureOpenAIEmbeddingProvider) carry a
    # status_code attribute without necessarily being httpx exceptions.
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code == 429 or status_code >= 500
    return False


class ResilientEmbeddingProvider(EmbeddingProvider):
    """
    Wraps a concrete EmbeddingProvider with a circuit breaker, per-call timeout,
    and jittered-exponential-backoff retry.

    - If the breaker is open, `embed()`/`embed_batch()` raise CircuitOpenError
      immediately so callers can degrade without paying the request timeout.
    - Each call is bounded by `settings.embedding_request_timeout`.
    - On timeout or a transient error (`_is_transient`), retries with jittered
      exponential backoff up to `settings.embedding_retry_max_attempts` total
      attempts. Non-transient errors are raised immediately, no retry.
    - `embed_batch()` wraps the whole batch call as a single unit (no
      per-item retry within a batch) when the underlying provider exposes a
      native batch method.
    """

    def __init__(self, wrapped: EmbeddingProvider, settings: Settings):
        self._wrapped = wrapped
        self._settings = settings
        # Trip after `embedding_breaker_failure_threshold` consecutive failures;
        # cooldown `embedding_breaker_cooldown_seconds`. When open, embed()/
        # embed_batch() raise CircuitOpenError immediately so callers (chat/
        # service.py) can degrade to a verse-less response without paying the
        # per-call timeout during a sustained outage.
        self._breaker = CircuitBreaker(
            name="embedding",
            failure_threshold=settings.embedding_breaker_failure_threshold,
            cooldown_seconds=settings.embedding_breaker_cooldown_seconds,
        )

    @property
    def provider_name(self) -> str:
        return self._wrapped.provider_name

    @property
    def dimensions(self) -> int:
        return self._wrapped.dimensions

    async def _call_with_resilience(self, coro_factory, *, op: str):
        """Run `coro_factory()` under the breaker/timeout/retry policy.

        `coro_factory` is a zero-arg callable returning a fresh coroutine per
        attempt (a coroutine object can only be awaited once).
        """
        if self._breaker.is_open():
            embedding_fallback_counter.add(1, {"reason": "breaker_open", "op": op})
            raise CircuitOpenError("embedding circuit breaker open")

        max_attempts = self._settings.embedding_retry_max_attempts
        base_delay = self._settings.embedding_retry_base_delay_seconds
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                result = await asyncio.wait_for(
                    coro_factory(), timeout=self._settings.embedding_request_timeout
                )
                self._breaker.record_success()
                return result
            except TimeoutError as e:
                last_error = e
                self._breaker.record_failure()
                embedding_fallback_counter.add(1, {"reason": "timeout", "op": op})
                logger.warning(
                    "Embedding call timed out (attempt %d/%d, op=%s)",
                    attempt + 1,
                    max_attempts,
                    op,
                )
            except Exception as e:
                if not _is_transient(e):
                    self._breaker.record_failure()
                    embedding_fallback_counter.add(1, {"reason": "non_transient", "op": op})
                    raise
                last_error = e
                self._breaker.record_failure()
                embedding_fallback_counter.add(1, {"reason": type(e).__name__, "op": op})
                logger.warning(
                    "Embedding call failed transiently (attempt %d/%d, op=%s): %s",
                    attempt + 1,
                    max_attempts,
                    op,
                    e,
                )

            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, base_delay)
                await asyncio.sleep(delay)

        logger.error("Embedding call exhausted retries (op=%s, attempts=%d)", op, max_attempts)
        assert last_error is not None
        raise last_error

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding for a single text, with breaker/timeout/retry."""
        return await self._call_with_resilience(lambda: self._wrapped.embed(text), op="embed")

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResponse]:
        """Generate embeddings for multiple texts, with breaker/timeout/retry.

        Wraps the whole batch call as one unit — a batch is retried in full on
        a transient failure rather than retrying individual items.
        """
        return await self._call_with_resilience(
            lambda: self._wrapped.embed_batch(texts), op="embed_batch"
        )

    async def health_check(self) -> bool:
        """Delegate health checks to the wrapped provider (not breaker-gated)."""
        return await self._wrapped.health_check()

    async def close(self) -> None:
        """Close the wrapped provider's resources."""
        await self._wrapped.close()

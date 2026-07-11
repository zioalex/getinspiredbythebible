"""
OpenRouter LLM Provider implementation.
OpenRouter provides access to various LLMs including free models via an OpenAI-compatible API.
"""

import time
from typing import Any, AsyncIterator, cast

import httpx
from openai import APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionChunk

from utils.circuit_breaker import CircuitBreaker
from utils.logging_config import get_logger
from utils.metrics import (
    llm_fallback_counter,
    llm_rate_limit_counter,
    llm_tokens_per_second_histogram,
    llm_total_duration_histogram,
    llm_ttft_histogram,
    openrouter_fallback_counter,
)

from .base import ChatMessage, LLMProvider, LLMResponse
from .errors import AllModelsExhaustedError

logger = get_logger(__name__)


class _BreakerOpenError(Exception):
    """Sentinel: circuit breaker tripped, do not call the primary model."""


def _classify_failure(e: Exception) -> str:
    """Categorize a failure for metric labelling."""
    if isinstance(e, _BreakerOpenError):
        return "breaker_open"
    if isinstance(e, RateLimitError):
        return "rate_limit"
    if isinstance(e, (APITimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(e, APIStatusError):
        status = getattr(e, "status_code", None)
        if status == 404:
            return "model_404"
        if status == 503:
            return "upstream_503"
        if status == 429:
            return "rate_limit"
        return f"api_status_{status}"
    return "other"


class OpenRouterProvider(LLMProvider):
    """
    LLM Provider for OpenRouter.

    OpenRouter provides access to various LLMs including free models like:
    - meta-llama/llama-3.3-70b-instruct:free
    - google/gemma-2-9b-it:free

    Uses OpenAI-compatible API for easy integration.
    Supports automatic fallback to paid models via native models array and provider preferences.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        base_url: str = "https://openrouter.ai/api/v1",
        fallback_models: list[str] | None = None,
        allow_fallbacks: bool = True,
        preferred_min_throughput_p50: int = 50,
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model name (default: meta-llama/llama-3.3-70b-instruct:free)
            base_url: OpenRouter API base URL (default: https://openrouter.ai/api/v1)
            fallback_models: List of fallback models to try if primary fails
            allow_fallbacks: Whether to allow automatic fallback (default: True)
            preferred_min_throughput_p50: Minimum preferred throughput in tokens/sec at p50
        """
        self.model = model
        self.fallback_models = fallback_models or []
        self.allow_fallbacks = allow_fallbacks
        self.preferred_min_throughput_p50 = preferred_min_throughput_p50
        # Explicit timeouts so we never hang on a stuck upstream.
        # connect 5s catches DNS/TCP issues fast; read 60s is generous enough
        # for streaming first-token latency on slower free-tier models.
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(60.0, connect=5.0),
            max_retries=2,
        )
        # Breaker trips after 5 consecutive primary-model failures within the
        # cooldown window. When open, chat()/chat_stream() jump straight to
        # the fallback list instead of paying the primary-call timeout.
        self._breaker = CircuitBreaker(
            name="openrouter_primary",
            failure_threshold=5,
            cooldown_seconds=30.0,
        )
        logger.info(
            f"OpenRouterProvider initialized: model={model}, "
            f"fallbacks={self.fallback_models}, allow_fallbacks={allow_fallbacks}, "
            f"preferred_min_throughput_p50={preferred_min_throughput_p50}"
        )

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """
        Convert messages to OpenAI format.

        OpenAI format is compatible with our ChatMessage format.
        """
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _get_model_and_extra_body(
        self, primary_override: str | None = None
    ) -> tuple[str, dict | None]:
        """
        Get model name and extra_body for OpenRouter request.

        WHY: OpenRouter's auto-router plugin (NotDiamond) is designed for quality/prompt
        routing — it picks the "best model for the prompt". We don't want that; we want
        cost-first routing with performance-aware fallback to the paid tier.

        The native `models` array + `provider.preferred_min_throughput` approach lets
        OpenRouter's real-time infrastructure handle the routing decision server-side,
        using a 5-minute rolling throughput window. This means a slow free-tier response
        causes proactive routing to the paid model — without any client-side timeout
        or error-handling logic.

        When ``primary_override`` is set (e.g. a language-based model override such as
        Arabic → qwen), the override becomes the primary model but STILL gets the same
        server-side fallback array + throughput routing. Otherwise a single flaky or
        endpoint-incompatible upstream provider would hard-fail the request with no safety
        net (e.g. Novita returning "does not support endpoint: completions" for qwen).

        Reference: https://openrouter.ai/docs/guides/routing/provider-selection
        Reference: https://openrouter.ai/docs/guides/routing/model-fallbacks

        Returns:
            Tuple of (model_name, extra_body) where extra_body may be None
        """
        primary = primary_override or self.model

        if not self.fallback_models or not self.allow_fallbacks:
            # No fallback configured, use direct model
            return primary, None

        # Use native models array with provider preferences for performance-aware routing
        # Primary model listed first, then fallbacks (OpenRouter tries in order).
        # De-dupe so an override that also appears in fallback_models isn't listed twice.
        models_array = [primary] + [m for m in self.fallback_models if m != primary]
        logger.info(f"Using native models array with throughput routing: {models_array}")

        extra_body: dict = {
            "models": models_array,
        }

        # Add provider preferences for throughput-based routing if configured
        if self.preferred_min_throughput_p50 > 0:
            extra_body["provider"] = {
                "sort": {"by": "throughput", "partition": "none"},
                "preferred_min_throughput": {"p50": self.preferred_min_throughput_p50},
            }
            logger.info(
                f"Throughput-based routing enabled: "
                f"preferred_min_throughput.p50={self.preferred_min_throughput_p50}"
            )

        return primary, extra_body

    def _is_rate_limit_error(self, e: Exception) -> bool:
        """Check if an exception is a rate limit error and log it."""
        if isinstance(e, RateLimitError):
            logger.warning(f"RateLimitError from OpenRouter: {e}")
            llm_rate_limit_counter.add(1, {"provider": "openrouter"})
            return True
        if isinstance(e, APIStatusError) and e.status_code == 429:
            logger.warning(f"APIStatusError 429 from OpenRouter: {e}")
            llm_rate_limit_counter.add(1, {"provider": "openrouter"})
            return True
        return False

    def _is_model_unavailable_error(self, e: Exception) -> bool:
        """Check if an exception indicates model is unavailable (404 or similar)."""
        if isinstance(e, APIStatusError):
            # 404: Model not found / No models match
            # 503: Service temporarily unavailable
            if e.status_code in (404, 503):
                logger.warning(f"Model unavailable (status {e.status_code}): {e}")
                return True
            # Check error message for model-related issues. "does not support
            # endpoint" is what an upstream provider (e.g. Novita) returns as a 400
            # when it can't serve a routed model on the chat-completions endpoint —
            # treat it as model-unavailable so we fall back instead of hard-failing.
            error_msg = str(e).lower()
            if (
                "no model" in error_msg
                or "model not found" in error_msg
                or "does not support endpoint" in error_msg
            ):
                logger.warning(f"Model unavailable error: {e}")
                return True
        if isinstance(e, (APITimeoutError, httpx.TimeoutException)):
            logger.warning(f"OpenRouter primary call timed out: {e}")
            return True
        return False

    def _should_try_fallback(self, e: Exception) -> bool:
        """Check if we should try fallback models for this error."""
        return self._is_rate_limit_error(e) or self._is_model_unavailable_error(e)

    async def chat(  # noqa: C901
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """
        Send a chat completion request to OpenRouter.

        Most fallback handling is done server-side by OpenRouter via the models array
        and provider preferences. Client-side fallback is kept as a safety net for
        errors that OpenRouter doesn't handle automatically.
        """
        converted_messages = self._convert_messages(messages)
        model_override = kwargs.pop("model_override", None)
        if model_override:
            logger.info(f"Using language-based model override: {model_override}")
        # Overrides flow through the same routing builder so they keep the
        # server-side fallback array + throughput routing (see method docstring).
        model_to_use, extra_body = self._get_model_and_extra_body(primary_override=model_override)

        # If the breaker is open, skip the primary call entirely and jump
        # straight to the fallback list. This trades fidelity for not paying
        # the primary timeout on every request during a sustained outage.
        # The breaker models the *default* primary; don't let it divert an
        # override request (a different model with its own fallback array).
        breaker_skip_primary = (
            self._breaker.is_open()
            and self.fallback_models
            and self.allow_fallbacks
            and not model_override
        )

        try:
            if breaker_skip_primary:
                raise _BreakerOpenError()
            response = await self._client.chat.completions.create(
                model=model_to_use,
                messages=converted_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
            )
            # The breaker tracks the *default* primary's health; an override is a
            # different model, so don't fold its success/failure into that signal.
            if not model_override:
                self._breaker.record_success()
        except (RateLimitError, APIStatusError, APITimeoutError, _BreakerOpenError) as e:
            # Client-side fallback as safety net (most cases handled by OpenRouter server-side)
            should_fallback = isinstance(e, _BreakerOpenError) or self._should_try_fallback(e)
            if not isinstance(e, _BreakerOpenError) and not model_override:
                self._breaker.record_failure()

            if should_fallback and self.fallback_models and self.allow_fallbacks:
                if not isinstance(e, _BreakerOpenError):
                    logger.warning(
                        f"Server-side routing failed, trying client-side fallback. "
                        f"Model={model_to_use}, Error: {e}"
                    )
                openrouter_fallback_counter.add(
                    1,
                    {
                        "reason": _classify_failure(e),
                        "stream": "false",
                    },
                )
                for fallback_model in self.fallback_models:
                    try:
                        logger.info(f"Client-side fallback to: {fallback_model}")
                        response = await self._client.chat.completions.create(
                            model=fallback_model,
                            messages=converted_messages,  # type: ignore[arg-type]
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        # Fallback success path — keep at INFO, not ERROR, so
                        # the log-based alert doesn't fire on every hiccup.
                        logger.info(f"Client-side fallback to {fallback_model} succeeded")
                        # Return response with the fallback model name
                        content = response.choices[0].message.content or ""
                        return LLMResponse(
                            content=content,
                            model=fallback_model,
                            provider=self.provider_name,
                            tokens_used=(
                                (response.usage.prompt_tokens if response.usage else 0)
                                + (response.usage.completion_tokens if response.usage else 0)
                            ),
                            finish_reason=response.choices[0].finish_reason,
                        )
                    except Exception as fallback_error:
                        logger.warning(
                            f"Client-side fallback {fallback_model} failed: {fallback_error}"
                        )
                        continue
                # All fallbacks exhausted — this *is* an error condition
                logger.error(
                    "All OpenRouter models unavailable. primary=%s fallbacks=%s",
                    model_to_use,
                    self.fallback_models,
                )
                is_rate_limited = isinstance(e, RateLimitError) or (
                    isinstance(e, APIStatusError) and e.status_code == 429
                )
                raise AllModelsExhaustedError(
                    "All models unavailable or rate limited. "
                    f"Primary: {model_to_use}, "
                    f"Fallbacks: {self.fallback_models}. "
                    "Check model names at https://openrouter.ai/models",
                    reason="rate_limited" if is_rate_limited else "unavailable",
                    models_tried=[model_to_use, *self.fallback_models],
                ) from (e if not isinstance(e, _BreakerOpenError) else None)
            else:
                if isinstance(e, _BreakerOpenError):
                    # Breaker open but no fallbacks available — surface as a clear error.
                    # Unreachable in practice: breaker_skip_primary already requires
                    # fallback_models/allow_fallbacks, which is mutually exclusive with
                    # this branch. Kept typed for consistency, not test coverage.
                    raise AllModelsExhaustedError(
                        "OpenRouter circuit breaker open and no fallback models configured",
                        reason="unavailable",
                        models_tried=[self.model],
                    )
                # No fallbacks configured or not a recoverable error
                raise

        # Handle cases where response might be malformed
        if not response or not response.choices:
            raise ValueError("OpenRouter returned empty response - API may be overloaded")

        # Extract response content
        content = response.choices[0].message.content or ""

        # Use actual model from response (may differ if auto-router selected different model)
        actual_model = response.model if response.model else self.model
        logger.info(f"OpenRouter response from model: {actual_model}")

        return LLMResponse(
            content=content,
            model=actual_model,
            provider=self.provider_name,
            tokens_used=(
                (response.usage.prompt_tokens if response.usage else 0)
                + (response.usage.completion_tokens if response.usage else 0)
            ),
            finish_reason=response.choices[0].finish_reason,
        )

    async def _try_stream_with_fallback(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        model: str,
        extra_body: dict | None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Try to stream with a specific model, yielding chunks."""
        stream = cast(
            AsyncIterator[ChatCompletionChunk],
            await self._client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                extra_body=extra_body,
            ),
        )
        return stream

    async def chat_stream(  # type: ignore[override]  # noqa: C901
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion from OpenRouter.

        Most fallback handling is done server-side by OpenRouter via the models array
        and provider preferences. Client-side fallback is kept as a safety net for
        errors that OpenRouter doesn't handle automatically.
        """
        converted_messages = self._convert_messages(messages)
        model_override = kwargs.pop("model_override", None)
        if model_override:
            logger.info(f"Using language-based model override: {model_override}")
        # Overrides flow through the same routing builder so they keep the
        # server-side fallback array + throughput routing (see method docstring).
        model_to_use, extra_body = self._get_model_and_extra_body(primary_override=model_override)

        logger.info(f"OpenRouter streaming request - model: {model_to_use}")

        current_model = model_to_use
        fallback_index = 0

        # If the breaker is open, skip primary and start at first fallback.
        if (
            self._breaker.is_open()
            and self.fallback_models
            and self.allow_fallbacks
            and not model_override
        ):
            logger.info("OpenRouter breaker open; skipping primary, starting at first fallback")
            current_model = self.fallback_models[0]
            fallback_index = 1
            extra_body = None
            openrouter_fallback_counter.add(1, {"reason": "breaker_open", "stream": "true"})

        while True:
            try:
                stream = cast(
                    AsyncIterator[ChatCompletionChunk],
                    await self._client.chat.completions.create(
                        model=current_model,
                        messages=converted_messages,  # type: ignore[arg-type]
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                        extra_body=extra_body if current_model == model_to_use else None,
                    ),
                )

                stream_start = time.perf_counter()
                first_chunk = True
                total_chars = 0
                used_fallback = current_model != model_to_use

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content_text = chunk.choices[0].delta.content
                        if first_chunk:
                            ttft_ms = (time.perf_counter() - stream_start) * 1000
                            llm_ttft_histogram.record(
                                ttft_ms, {"provider": "openrouter", "model": current_model}
                            )
                            first_chunk = False
                        total_chars += len(content_text)
                        yield content_text

                total_duration_ms = (time.perf_counter() - stream_start) * 1000
                llm_total_duration_histogram.record(
                    total_duration_ms, {"provider": "openrouter", "model": current_model}
                )
                if total_duration_ms > 0 and total_chars > 0:
                    approx_tokens = total_chars / 4
                    tokens_per_sec = approx_tokens / (total_duration_ms / 1000)
                    llm_tokens_per_second_histogram.record(
                        tokens_per_sec, {"provider": "openrouter", "model": current_model}
                    )
                if used_fallback:
                    llm_fallback_counter.add(1, {"provider": "openrouter", "model": current_model})
                # Successful stream — the *default* primary succeeded (or we recovered)
                # → reset breaker. An override is a different model, so its success is
                # not a signal about the default primary's health.
                if current_model == self.model:
                    self._breaker.record_success()

                return  # Success, exit the generator

            except (RateLimitError, APIStatusError, APITimeoutError) as e:
                # Client-side fallback as safety net (most cases handled by OpenRouter server-side)
                should_fallback = self._should_try_fallback(e)
                # Only the default primary's failures feed the breaker (see above).
                if current_model == self.model:
                    self._breaker.record_failure()

                if not should_fallback:
                    # Not a recoverable error, re-raise
                    raise

                logger.warning(f"Server-side routing failed in streaming: {e}")
                openrouter_fallback_counter.add(
                    1, {"reason": _classify_failure(e), "stream": "true"}
                )

                # Try next fallback model. Overrides get the safety net too: if the
                # override model 400s/429s on every upstream, fall back client-side.
                if (
                    self.fallback_models
                    and self.allow_fallbacks
                    and fallback_index < len(self.fallback_models)
                ):
                    current_model = self.fallback_models[fallback_index]
                    fallback_index += 1
                    extra_body = None  # Don't use routing config for direct fallback
                    logger.info(f"Client-side streaming fallback to: {current_model}")
                    continue
                else:
                    # No more fallbacks — this is a real failure
                    logger.error(
                        "All OpenRouter streaming models unavailable. tried=%s,%s",
                        model_to_use,
                        self.fallback_models[:fallback_index],
                    )
                    is_rate_limited = isinstance(e, RateLimitError) or (
                        isinstance(e, APIStatusError) and e.status_code == 429
                    )
                    raise AllModelsExhaustedError(
                        "All models unavailable in streaming. "
                        f"Tried: {model_to_use}, {self.fallback_models[:fallback_index]}. "
                        "Check model names at https://openrouter.ai/models",
                        reason="rate_limited" if is_rate_limited else "unavailable",
                        models_tried=[model_to_use, *self.fallback_models[:fallback_index]],
                    ) from e

    async def verify_model_available(self, model: str) -> tuple[bool, str]:
        """
        Verify that a specific model is available on OpenRouter.

        Args:
            model: Model name to check

        Returns:
            Tuple of (is_available, error_message)
        """
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            if response and response.choices:
                return True, ""
            return False, "Empty response from model"
        except APIStatusError as e:
            if e.status_code == 404:
                return False, f"Model '{model}' not found on OpenRouter"
            elif e.status_code == 429:
                # Rate limited means model exists but is busy
                return True, "Model exists but rate limited"
            else:
                return False, f"API error {e.status_code}: {e.message}"
        except Exception as e:
            return False, f"Error checking model: {str(e)}"

    async def verify_all_models(self) -> dict[str, tuple[bool, str]]:
        """
        Verify that all configured models (primary + fallbacks) are available.

        Returns:
            Dict mapping model name to (is_available, error_message)
        """
        results = {}
        all_models = [self.model] + self.fallback_models

        for model in all_models:
            is_available, error = await self.verify_model_available(model)
            results[model] = (is_available, error)
            if is_available:
                logger.info(f"Model '{model}' is available")
            else:
                logger.warning(f"Model '{model}' unavailable: {error}")

        return results

    async def health_check(self) -> bool:
        """
        Check if OpenRouter API is accessible.

        Note: This makes a minimal API call to verify connectivity.
        Uses native models array with provider preferences if configured.
        """
        result = await self.health_check_detailed()
        return result["healthy"]

    async def health_check_detailed(self) -> dict[str, Any]:
        """
        Structured health check — distinguishes 404 (model gone) from
        timeout / network failure, so /health/ready can surface the cause.
        """
        # Breaker state is itself a useful signal.
        if self._breaker.is_open():
            return {
                "healthy": False,
                "reason": "breaker_open",
                "breaker_state": self._breaker.state,
            }
        try:
            model_to_use, extra_body = self._get_model_and_extra_body()
            response = await self._client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                extra_body=extra_body,
            )
            return {
                "healthy": response is not None,
                "reason": "ok" if response is not None else "empty_response",
                "breaker_state": self._breaker.state,
            }
        except Exception as e:
            return {
                "healthy": False,
                "reason": _classify_failure(e),
                "breaker_state": self._breaker.state,
                "error": str(e),
            }

    async def close(self) -> None:
        """Close the OpenAI HTTP client."""
        await self._client.close()

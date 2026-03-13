"""
OpenRouter LLM Provider implementation.
OpenRouter provides access to various LLMs including free models via an OpenAI-compatible API.
"""

from typing import AsyncIterator, cast

from openai import APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionChunk

from utils.logging_config import get_logger

from .base import ChatMessage, LLMProvider, LLMResponse

logger = get_logger(__name__)


class OpenRouterProvider(LLMProvider):
    """
    LLM Provider for OpenRouter.

    OpenRouter provides access to various LLMs including free models like:
    - meta-llama/llama-3.3-70b-instruct:free
    - google/gemma-2-9b-it:free

    Uses OpenAI-compatible API for easy integration.
    Supports automatic fallback to paid models via auto-router plugin.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        base_url: str = "https://openrouter.ai/api/v1",
        fallback_models: list[str] | None = None,
        allow_fallbacks: bool = True,
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model name (default: meta-llama/llama-3.3-70b-instruct:free)
            base_url: OpenRouter API base URL (default: https://openrouter.ai/api/v1)
            fallback_models: List of fallback models to try if primary fails
            allow_fallbacks: Whether to allow automatic fallback (default: True)
        """
        self.model = model
        self.fallback_models = fallback_models or []
        self.allow_fallbacks = allow_fallbacks
        # Disable SDK auto-retry for rate limits - we handle fallbacks ourselves
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
        )
        logger.info(
            f"OpenRouterProvider initialized: model={model}, "
            f"fallbacks={self.fallback_models}, allow_fallbacks={allow_fallbacks}"
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

    def _get_model_and_extra_body(self) -> tuple[str, dict | None]:
        """
        Get model name and extra_body for OpenRouter request.

        When fallback models are configured, uses openrouter/auto with the
        auto-router plugin to enable automatic model selection and failover.

        Returns:
            Tuple of (model_name, extra_body) where extra_body may be None
        """
        if not self.fallback_models or not self.allow_fallbacks:
            # No fallback configured, use direct model
            return self.model, None

        # Use auto-router with allowed models for automatic failover
        # Primary model listed first, then fallbacks
        allowed_models = [self.model] + self.fallback_models
        logger.info(f"Using auto-router with allowed models: {allowed_models}")

        extra_body = {
            "plugins": [
                {
                    "id": "auto-router",
                    "allowed_models": allowed_models,
                }
            ]
        }

        return "openrouter/auto", extra_body

    def _is_rate_limit_error(self, e: Exception) -> bool:
        """Check if an exception is a rate limit error and log it."""
        if isinstance(e, RateLimitError):
            logger.warning(f"RateLimitError from OpenRouter: {e}")
            return True
        if isinstance(e, APIStatusError) and e.status_code == 429:
            logger.warning(f"APIStatusError 429 from OpenRouter: {e}")
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
            # Check error message for model-related issues
            error_msg = str(e).lower()
            if "no model" in error_msg or "model not found" in error_msg:
                logger.warning(f"Model unavailable error: {e}")
                return True
        return False

    def _should_try_fallback(self, e: Exception) -> bool:
        """Check if we should try fallback models for this error."""
        return self._is_rate_limit_error(e) or self._is_model_unavailable_error(e)

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter with explicit 429 fallback."""
        converted_messages = self._convert_messages(messages)
        model_to_use, extra_body = self._get_model_and_extra_body()

        try:
            response = await self._client.chat.completions.create(
                model=model_to_use,
                messages=converted_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
            )
        except (RateLimitError, APIStatusError) as e:
            should_fallback = self._should_try_fallback(e)

            if should_fallback and self.fallback_models and self.allow_fallbacks:
                logger.warning(
                    f"Primary model failed (model={model_to_use}, primary={self.model}), "
                    f"attempting fallback to: {self.fallback_models}"
                )
                for fallback_model in self.fallback_models:
                    try:
                        logger.info(f"Trying fallback model: {fallback_model}")
                        response = await self._client.chat.completions.create(
                            model=fallback_model,
                            messages=converted_messages,  # type: ignore[arg-type]
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        logger.info(f"Fallback to {fallback_model} succeeded")
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
                    except (RateLimitError, APIStatusError) as fallback_e:
                        if self._should_try_fallback(fallback_e):
                            logger.warning(
                                f"Fallback model {fallback_model} also failed: {fallback_e}"
                            )
                        else:
                            logger.error(f"Fallback model {fallback_model} failed: {fallback_e}")
                        continue
                    except Exception as fallback_error:
                        logger.error(f"Fallback model {fallback_model} failed: {fallback_error}")
                        continue
                # All fallbacks exhausted
                raise RuntimeError(
                    "All models unavailable or rate limited. "
                    f"Primary: {self.model}, "
                    f"Fallbacks: {self.fallback_models}. "
                    "Check model names at https://openrouter.ai/models"
                ) from e
            else:
                # No fallbacks configured or not a recoverable error
                if should_fallback:
                    logger.error(
                        f"Model failed but no fallbacks available: "
                        f"fallback_models={self.fallback_models}, allow_fallbacks={self.allow_fallbacks}"
                    )
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

    async def chat_stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion from OpenRouter with explicit 429 fallback."""
        converted_messages = self._convert_messages(messages)
        model_to_use, extra_body = self._get_model_and_extra_body()

        logger.info(f"OpenRouter streaming request - model: {model_to_use}")

        current_model = model_to_use
        fallback_index = 0

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

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return  # Success, exit the generator

            except (RateLimitError, APIStatusError) as e:
                # Check if this error should trigger fallback
                should_fallback = self._should_try_fallback(e)

                if not should_fallback:
                    # Not a recoverable error, re-raise
                    raise

                logger.warning(f"Model {current_model} failed in streaming: {e}")

                # Try next fallback model
                if (
                    self.fallback_models
                    and self.allow_fallbacks
                    and fallback_index < len(self.fallback_models)
                ):
                    current_model = self.fallback_models[fallback_index]
                    fallback_index += 1
                    extra_body = None  # Don't use auto-router for direct fallback
                    logger.info(f"Streaming fallback to: {current_model}")
                    continue
                else:
                    # No more fallbacks
                    raise RuntimeError(
                        "All models unavailable in streaming. "
                        f"Tried: {model_to_use}, {self.fallback_models[:fallback_index]}. "
                        "Check model names at https://openrouter.ai/models"
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
        Uses auto-router with fallback models if configured.
        """
        try:
            model_to_use, extra_body = self._get_model_and_extra_body()
            response = await self._client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                extra_body=extra_body,
            )
            return response is not None
        except Exception:
            return False

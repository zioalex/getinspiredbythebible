"""
OpenRouter LLM Provider implementation.
OpenRouter provides access to various LLMs including free models via an OpenAI-compatible API.
"""

import logging
from typing import AsyncIterator, cast

from openai import AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionChunk

from .base import ChatMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """
    LLM Provider for OpenRouter.

    OpenRouter provides access to various LLMs including free models like:
    - meta-llama/llama-3.3-70b-instruct:free
    - google/gemma-2-9b-it:free

    Uses OpenAI-compatible API for easy integration.
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
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
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

        extra_body = {
            "plugins": [
                {
                    "id": "auto-router",
                    "allowed_models": allowed_models,
                }
            ]
        }

        return "openrouter/auto", extra_body

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
        except RateLimitError as e:
            # If we get a 429 and have fallback models, try them directly
            if self.fallback_models and self.allow_fallbacks:
                logger.warning(
                    f"Rate limit hit for {self.model}, trying fallback models: {self.fallback_models}"
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
                    except RateLimitError:
                        logger.warning(f"Fallback model {fallback_model} also rate limited")
                        continue
                    except Exception as fallback_error:
                        logger.error(f"Fallback model {fallback_model} failed: {fallback_error}")
                        continue
                # All fallbacks exhausted
                raise RuntimeError(
                    "All models rate limited. "
                    f"Primary: {self.model}, "
                    f"Fallbacks: {self.fallback_models}"
                ) from e
            else:
                # No fallbacks configured, re-raise the original error
                raise

        # Handle cases where response might be malformed
        if not response or not response.choices:
            raise ValueError("OpenRouter returned empty response - API may be overloaded")

        # Extract response content
        content = response.choices[0].message.content or ""

        # Use actual model from response (may differ if auto-router selected different model)
        actual_model = response.model if response.model else self.model

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

            except RateLimitError as e:
                logger.warning(f"Rate limit hit for {current_model} in streaming")

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
                        "All models rate limited in streaming. "
                        f"Tried: {model_to_use}, {self.fallback_models[:fallback_index]}"
                    ) from e
            except Exception:
                # Other errors, re-raise
                raise

    async def health_check(self) -> bool:
        """
        Check if OpenRouter API is accessible.

        Note: This makes a minimal API call to verify connectivity.
        Uses auto-router with fallback models if configured.
        """
        try:
            model_to_use, extra_body = self._get_model_and_extra_body()
            # Make a minimal request to check connectivity
            response = await self._client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                extra_body=extra_body,
            )
            return response is not None
        except Exception:
            return False

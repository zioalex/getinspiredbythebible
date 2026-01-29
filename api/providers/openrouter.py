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
    Supports automatic fallback to paid models when free models are rate-limited.
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
            fallback_models: List of fallback models to try if primary fails (rate limit)
            allow_fallbacks: Whether to allow automatic fallback (default: True)
        """
        self.model = model
        self.fallback_models = fallback_models or []
        self.allow_fallbacks = allow_fallbacks
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,  # Disable auto-retry so we can handle fallback ourselves
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

    def _get_models_to_try(self) -> list[str]:
        """
        Get list of models to try in order.

        Returns primary model first, followed by fallback models if configured.
        """
        if not self.fallback_models or not self.allow_fallbacks:
            return [self.model]
        return [self.model] + self.fallback_models

    async def _try_chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ):
        """Make a single chat completion request to a specific model."""
        return await self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter with fallback support."""
        converted_messages = self._convert_messages(messages)
        models_to_try = self._get_models_to_try()

        last_error = None
        for model in models_to_try:
            try:
                logger.info(f"Trying OpenRouter model: {model}")
                response = await self._try_chat_completion(
                    model=model,
                    messages=converted_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # Handle cases where response might be malformed
                if not response or not response.choices:
                    raise ValueError("OpenRouter returned empty response")

                # Extract response content
                content = response.choices[0].message.content or ""

                # Use actual model from response
                actual_model = response.model if response.model else model
                logger.info(f"OpenRouter request successful with model: {actual_model}")

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

            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit hit for model {model}: {e}")
                # Continue to next model in fallback list
                continue
            except Exception:
                # For other errors, don't try fallback - re-raise immediately
                raise

        # All models failed with rate limit
        raise last_error or ValueError("All OpenRouter models failed")

    async def chat_stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion from OpenRouter with fallback support."""
        converted_messages = self._convert_messages(messages)
        models_to_try = self._get_models_to_try()

        last_error = None
        for model in models_to_try:
            try:
                logger.info(f"Trying OpenRouter streaming with model: {model}")
                stream = cast(
                    AsyncIterator[ChatCompletionChunk],
                    await self._client.chat.completions.create(
                        model=model,
                        messages=converted_messages,  # type: ignore[arg-type]
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                    ),
                )

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

                # If we get here, streaming succeeded
                return

            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit hit for streaming model {model}: {e}")
                continue
            except Exception:
                raise

        # All models failed
        if last_error:
            raise last_error

    async def health_check(self) -> bool:
        """
        Check if OpenRouter API is accessible.

        Note: This makes a minimal API call to verify connectivity.
        Tries fallback models if primary is rate-limited.
        """
        models_to_try = self._get_models_to_try()

        for model in models_to_try:
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=10,
                )
                return response is not None
            except RateLimitError:
                logger.warning(f"Health check rate limited for model {model}, trying fallback")
                continue
            except Exception:
                return False

        return False

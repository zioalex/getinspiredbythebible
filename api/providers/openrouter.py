"""
OpenRouter LLM Provider implementation.
OpenRouter provides access to various LLMs including free models via an OpenAI-compatible API.
"""

from typing import AsyncIterator, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from .base import ChatMessage, LLMProvider, LLMResponse


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

    def _build_extra_body(self) -> dict | None:
        """
        Build extra_body for OpenRouter-specific features like model fallback.

        Returns None if no fallback is configured, otherwise returns the
        routing configuration for OpenRouter.
        """
        if not self.fallback_models:
            return None

        # Build models list: primary model first, then fallbacks
        models = [self.model] + self.fallback_models

        return {
            "models": models,
            "provider": {
                "allow_fallbacks": self.allow_fallbacks,
            },
        }

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter."""
        converted_messages = self._convert_messages(messages)
        extra_body = self._build_extra_body()

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=converted_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )

        # Handle cases where response might be malformed
        if not response or not response.choices:
            raise ValueError("OpenRouter returned empty response - API may be overloaded")

        # Extract response content
        content = response.choices[0].message.content or ""

        # Use actual model from response (may differ if fallback was used)
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

    async def chat_stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion from OpenRouter."""
        converted_messages = self._convert_messages(messages)
        extra_body = self._build_extra_body()

        stream = cast(
            AsyncIterator[ChatCompletionChunk],
            await self._client.chat.completions.create(
                model=self.model,
                messages=converted_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                extra_body=extra_body,
            ),
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        """
        Check if OpenRouter API is accessible.

        Note: This makes a minimal API call to verify connectivity.
        Uses fallback models if configured.
        """
        try:
            extra_body = self._build_extra_body()
            # Make a minimal request to check connectivity
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                extra_body=extra_body,
            )
            return response is not None
        except Exception:
            return False

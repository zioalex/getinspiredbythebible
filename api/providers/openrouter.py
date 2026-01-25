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
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model name (default: meta-llama/llama-3.3-70b-instruct:free)
            base_url: OpenRouter API base URL (default: https://openrouter.ai/api/v1)
        """
        self.model = model
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

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter."""
        converted_messages = self._convert_messages(messages)

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=converted_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Extract response content
        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
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

        stream = cast(
            AsyncIterator[ChatCompletionChunk],
            await self._client.chat.completions.create(
                model=self.model,
                messages=converted_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            ),
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        """
        Check if OpenRouter API is accessible.

        Note: This makes a minimal API call to verify connectivity.
        """
        try:
            # Make a minimal request to check connectivity
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
            )
            return response is not None
        except Exception:
            return False

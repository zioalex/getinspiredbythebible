"""
Claude (Anthropic) LLM Provider implementation.
For production use when you want to use Claude's API.
"""

from typing import AsyncIterator

import anthropic

from .base import ChatMessage, LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    """
    LLM Provider for Anthropic's Claude.

    Use this for production deployments or when you need
    Claude's advanced reasoning capabilities.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-sonnet-4-20250514)
        """
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "claude"

    def _convert_messages(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        """
        Convert messages to Anthropic format.

        Anthropic uses a separate system parameter, so we extract it.
        """
        system_prompt = None
        converted = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                converted.append({"role": msg.role, "content": msg.content})

        return system_prompt, converted

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to Claude."""
        system_prompt, converted_messages = self._convert_messages(messages)

        request_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": converted_messages,
            "temperature": temperature,
        }

        if system_prompt:
            request_params["system"] = system_prompt

        response = await self._client.messages.create(**request_params)  # type: ignore[call-overload]

        # Extract text from response
        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_name,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
        )

    async def chat_stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion from Claude."""
        system_prompt, converted_messages = self._convert_messages(messages)

        async with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            messages=converted_messages,  # type: ignore[arg-type]
            temperature=temperature,
            system=system_prompt if system_prompt else None,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        """
        Check if Claude API is accessible.

        Note: This makes a minimal API call to verify connectivity.
        """
        try:
            # Make a minimal request to check connectivity
            response = await self._client.messages.create(
                model=self.model, max_tokens=10, messages=[{"role": "user", "content": "Hi"}]
            )
            return response is not None
        except Exception:
            return False

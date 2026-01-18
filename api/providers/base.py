"""
Base interface for LLM providers.
All providers must implement this interface for consistent behavior.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: str  # 'user', 'assistant', 'system'
    content: str


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str
    model: str
    provider: str
    tokens_used: int | None = None
    finish_reason: str | None = None


class EmbeddingResponse(BaseModel):
    """Response from an embedding request."""

    embedding: list[float]
    model: str
    provider: str


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implement this interface to add support for new LLM backends.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with the generated content
        """
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Send a streaming chat completion request.

        Yields:
            Chunks of generated text as they arrive
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is available and responding.

        Returns:
            True if healthy, False otherwise
        """
        pass


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResponse:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResponse with the embedding vector
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResponse]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingResponse objects
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass

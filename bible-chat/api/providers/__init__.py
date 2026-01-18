"""
LLM and Embedding Providers package.

This package provides a unified interface for different LLM backends,
making it easy to switch between Ollama (local), Claude, OpenAI, etc.
"""

from .base import (
    LLMProvider,
    EmbeddingProvider,
    ChatMessage,
    LLMResponse,
    EmbeddingResponse
)
from .ollama import OllamaProvider, OllamaEmbeddingProvider
from .claude import ClaudeProvider
from .factory import (
    get_llm_provider,
    get_embedding_provider,
    LLMProviderDep,
    EmbeddingProviderDep,
    check_providers_health,
    ProviderError
)

__all__ = [
    # Base classes
    "LLMProvider",
    "EmbeddingProvider",
    "ChatMessage",
    "LLMResponse",
    "EmbeddingResponse",
    # Implementations
    "OllamaProvider",
    "OllamaEmbeddingProvider",
    "ClaudeProvider",
    # Factory
    "get_llm_provider",
    "get_embedding_provider",
    "LLMProviderDep",
    "EmbeddingProviderDep",
    "check_providers_health",
    "ProviderError",
]

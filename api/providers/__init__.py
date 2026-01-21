"""
LLM and Embedding Providers package.

This package provides a unified interface for different LLM backends,
making it easy to switch between Ollama (local), Claude, OpenAI, etc.
"""

from .base import ChatMessage, EmbeddingProvider, EmbeddingResponse, LLMProvider, LLMResponse
from .claude import ClaudeProvider
from .factory import (
    EmbeddingProviderDep,
    LLMProviderDep,
    ProviderError,
    check_providers_health,
    get_embedding_provider,
    get_llm_provider,
)
from .ollama import OllamaEmbeddingProvider, OllamaProvider
from .openrouter import OpenRouterProvider

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
    "OpenRouterProvider",
    # Factory
    "get_llm_provider",
    "get_embedding_provider",
    "LLMProviderDep",
    "EmbeddingProviderDep",
    "check_providers_health",
    "ProviderError",
]

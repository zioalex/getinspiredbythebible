"""
Provider Factory - Creates LLM and Embedding providers based on configuration.

This module provides dependency injection for FastAPI routes.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from config import Settings, settings

from .azure_openai import AzureOpenAIEmbeddingProvider
from .base import EmbeddingProvider, LLMProvider
from .claude import ClaudeProvider
from .ollama import OllamaEmbeddingProvider, OllamaProvider
from .openrouter import OpenRouterProvider


class ProviderError(Exception):
    """Raised when provider initialization fails."""

    pass


def create_llm_provider(config: Settings) -> LLMProvider:
    """
    Create an LLM provider based on configuration.

    Args:
        config: Application settings

    Returns:
        Configured LLM provider instance

    Raises:
        ProviderError: If provider type is unknown or misconfigured
    """
    match config.llm_provider:
        case "ollama":
            return OllamaProvider(host=config.ollama_host, model=config.llm_model)
        case "claude":
            if not config.anthropic_api_key:
                raise ProviderError(
                    "Claude provider requires ANTHROPIC_API_KEY environment variable"
                )
            return ClaudeProvider(api_key=config.anthropic_api_key, model=config.llm_model)
        case "openrouter":
            if not config.openrouter_api_key:
                raise ProviderError(
                    "OpenRouter provider requires OPENROUTER_API_KEY environment variable"
                )
            return OpenRouterProvider(
                api_key=config.openrouter_api_key,
                model=config.openrouter_model,
                base_url=config.openrouter_base_url,
            )
        case "openai":
            # Future implementation
            raise ProviderError("OpenAI provider not yet implemented")
        case _:
            raise ProviderError(f"Unknown LLM provider: {config.llm_provider}")


def create_embedding_provider(config: Settings) -> EmbeddingProvider:
    """
    Create an embedding provider based on configuration.

    Args:
        config: Application settings

    Returns:
        Configured embedding provider instance
    """
    match config.embedding_provider:
        case "ollama":
            return OllamaEmbeddingProvider(
                host=config.ollama_host,
                model=config.embedding_model,
                dimensions=config.embedding_dimensions,
            )
        case "azure_openai":
            if not config.azure_openai_endpoint:
                raise ProviderError(
                    "Azure OpenAI provider requires AZURE_OPENAI_ENDPOINT environment variable"
                )
            if not config.azure_openai_api_key:
                raise ProviderError(
                    "Azure OpenAI provider requires AZURE_OPENAI_API_KEY environment variable"
                )
            return AzureOpenAIEmbeddingProvider(
                endpoint=config.azure_openai_endpoint,
                api_key=config.azure_openai_api_key,
                deployment_name=config.azure_embedding_deployment,
                dimensions=config.embedding_dimensions,
            )
        case "openrouter":
            # OpenRouter embeddings currently use Ollama as fallback
            # Most OpenRouter models don't support embeddings API
            raise ProviderError("OpenRouter doesn't support embeddings. Use ollama for embeddings.")
        case "openai":
            # Future implementation
            raise ProviderError("OpenAI embedding provider not yet implemented")
        case _:
            raise ProviderError(f"Unknown embedding provider: {config.embedding_provider}")


# Cached provider instances (singletons)
@lru_cache()
def get_llm_provider() -> LLMProvider:
    """Get the configured LLM provider (cached singleton)."""
    return create_llm_provider(settings)


@lru_cache()
def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider (cached singleton)."""
    return create_embedding_provider(settings)


# FastAPI dependency injection types
LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


async def check_providers_health() -> dict:
    """
    Check health of all configured providers.

    Returns:
        Dictionary with health status for each provider
    """
    llm = get_llm_provider()
    embedding = get_embedding_provider()

    return {
        "llm": {"provider": llm.provider_name, "healthy": await llm.health_check()},
        "embedding": {
            "provider": embedding.provider_name,
            "healthy": await embedding.health_check(),
        },
    }

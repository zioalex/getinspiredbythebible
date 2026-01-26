"""
Application configuration using Pydantic Settings.
Supports environment variables and .env files.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Bible Inspiration Chat"
    app_version: str = "0.1.0"
    debug: bool = True

    # LLM Configuration
    llm_provider: Literal["ollama", "claude", "openai", "openrouter"] = "ollama"
    llm_model: str = "llama3:8b"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024

    # Ollama Settings
    ollama_host: str = "http://localhost:11434"

    # Claude Settings
    anthropic_api_key: str | None = None

    # OpenAI Settings
    openai_api_key: str | None = None

    # OpenRouter Settings (OpenAI-compatible API with free models)
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Free models: meta-llama/llama-3.3-70b-instruct:free, google/gemma-2-9b-it:free
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Embedding Configuration
    embedding_provider: Literal["ollama", "openai", "openrouter"] = "ollama"
    embedding_model: str = "mxbai-embed-large"  # Multilingual model (100+ languages)
    embedding_dimensions: int = 1024  # mxbai-embed-large dimension (was 768 for nomic)

    # Database
    database_url: str = (
        "postgresql://bible:bible123@localhost:5432/bibledb"  # pragma: allowlist secret
    )

    # Chat Settings
    max_context_verses: int = 10  # Max verses to include in context
    max_conversation_history: int = 10  # Max messages to keep in context

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export singleton
settings = get_settings()

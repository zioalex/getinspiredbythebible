"""
Application configuration using Pydantic Settings.
Supports environment variables and .env files.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Bible Inspiration Chat"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # LLM Configuration
    llm_provider: Literal["ollama", "claude", "openai"] = "ollama"
    llm_model: str = "llama3:8b"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
    
    # Ollama Settings
    ollama_host: str = "http://localhost:11434"
    
    # Claude Settings (for future use)
    anthropic_api_key: str | None = None
    
    # OpenAI Settings (for future use)
    openai_api_key: str | None = None
    
    # Embedding Configuration
    embedding_provider: Literal["ollama", "openai"] = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768  # nomic-embed-text dimension
    
    # Database
    database_url: str = "postgresql://bible:bible123@localhost:5432/bibledb"
    
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

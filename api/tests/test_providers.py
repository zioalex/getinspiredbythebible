"""
Tests for LLM provider factory
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Settings
from providers.base import LLMProvider
from providers.factory import create_llm_provider


def test_provider_factory_returns_provider():
    """Test that factory returns a provider instance"""
    # Create a minimal settings object for Ollama
    settings = Settings(
        llm_provider="ollama", llm_model="llama3:8b", ollama_host="http://localhost:11434"
    )

    provider = create_llm_provider(settings)
    assert provider is not None
    assert isinstance(provider, LLMProvider)


def test_provider_has_required_methods():
    """Test that provider has required interface methods"""
    settings = Settings(
        llm_provider="ollama", llm_model="llama3:8b", ollama_host="http://localhost:11434"
    )

    provider = create_llm_provider(settings)
    assert hasattr(provider, "chat")
    assert hasattr(provider, "chat_stream")
    assert callable(provider.chat)
    assert callable(provider.chat_stream)

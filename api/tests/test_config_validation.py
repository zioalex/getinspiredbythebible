"""
Tests for configuration validation in config.py.

Tests ensure that Settings fails fast on invalid configurations
rather than allowing the app to start with broken settings.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Settings


def test_database_url_placeholder_rejected():
    """Test that placeholder DATABASE_URL is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://CONFIGURE_ME:CONFIGURE_ME@localhost:5432/bibledb",  # pragma: allowlist secret
        )
    error_msg = str(exc_info.value)
    assert "DATABASE_URL must be configured" in error_msg
    assert "placeholder value" in error_msg


def test_database_url_valid_passes():
    """Test that a valid DATABASE_URL passes validation."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
    )
    assert (
        settings.database_url
        == "postgresql://user:pass@localhost:5432/bibledb"  # pragma: allowlist secret
    )


def test_claude_requires_api_key():
    """Test that llm_provider=claude requires anthropic_api_key."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            llm_provider="claude",
            anthropic_api_key=None,
        )
    error_msg = str(exc_info.value)
    assert "anthropic_api_key is required when llm_provider=claude" in error_msg
    assert "ANTHROPIC_API_KEY" in error_msg


def test_claude_with_api_key_passes():
    """Test that llm_provider=claude with anthropic_api_key passes."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        llm_provider="claude",
        anthropic_api_key="sk-ant-test123",  # pragma: allowlist secret
    )
    assert settings.llm_provider == "claude"
    assert settings.anthropic_api_key == "sk-ant-test123"  # pragma: allowlist secret


def test_openai_requires_api_key():
    """Test that llm_provider=openai requires openai_api_key."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            llm_provider="openai",
            openai_api_key=None,
        )
    error_msg = str(exc_info.value)
    assert "openai_api_key is required when llm_provider=openai" in error_msg
    assert "OPENAI_API_KEY" in error_msg


def test_openrouter_requires_api_key():
    """Test that llm_provider=openrouter requires openrouter_api_key."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            llm_provider="openrouter",
            openrouter_api_key=None,
        )
    error_msg = str(exc_info.value)
    assert "openrouter_api_key is required when llm_provider=openrouter" in error_msg
    assert "OPENROUTER_API_KEY" in error_msg


def test_ollama_no_key_required():
    """Test that llm_provider=ollama does not require API keys."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        llm_provider="ollama",
        anthropic_api_key=None,
        openai_api_key=None,
        openrouter_api_key=None,
    )
    assert settings.llm_provider == "ollama"


def test_embedding_openai_requires_api_key():
    """Test that embedding_provider=openai requires openai_api_key."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            embedding_provider="openai",
            openai_api_key=None,
        )
    error_msg = str(exc_info.value)
    assert "openai_api_key is required when embedding_provider=openai" in error_msg
    assert "OPENAI_API_KEY" in error_msg


def test_embedding_azure_requires_endpoint_and_key():
    """Test that embedding_provider=azure_openai requires endpoint and key."""
    # Missing both endpoint and key
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            embedding_provider="azure_openai",
            azure_openai_endpoint=None,
            azure_openai_api_key=None,
        )
    error_msg = str(exc_info.value)
    assert "azure_openai_endpoint and azure_openai_api_key are required" in error_msg
    assert "azure_openai" in error_msg

    # Missing endpoint only
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            embedding_provider="azure_openai",
            azure_openai_endpoint=None,
            azure_openai_api_key="test-key",  # pragma: allowlist secret
        )
    error_msg = str(exc_info.value)
    assert "azure_openai_endpoint and azure_openai_api_key are required" in error_msg

    # Missing key only
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            embedding_provider="azure_openai",
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_api_key=None,
        )
    error_msg = str(exc_info.value)
    assert "azure_openai_endpoint and azure_openai_api_key are required" in error_msg


def test_embedding_dimensions_mismatch_detected():
    """Test that embedding dimension mismatches are detected."""
    # mxbai-embed-large requires 1024, not 768
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            embedding_model="mxbai-embed-large",
            embedding_dimensions=768,
        )
    error_msg = str(exc_info.value)
    assert "Embedding dimensions mismatch" in error_msg
    assert "mxbai-embed-large" in error_msg
    assert "1024" in error_msg
    assert "768" in error_msg

    # nomic-embed-text requires 768, not 1024
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            embedding_model="nomic-embed-text",
            embedding_dimensions=1024,
        )
    error_msg = str(exc_info.value)
    assert "Embedding dimensions mismatch" in error_msg
    assert "nomic-embed-text" in error_msg
    assert "768" in error_msg
    assert "1024" in error_msg


def test_embedding_dimensions_correct_passes():
    """Test that correct embedding dimensions pass validation."""
    # mxbai-embed-large with 1024
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        embedding_model="mxbai-embed-large",
        embedding_dimensions=1024,
    )
    assert settings.embedding_dimensions == 1024

    # nomic-embed-text with 768
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        embedding_model="nomic-embed-text",
        embedding_dimensions=768,
    )
    assert settings.embedding_dimensions == 768

    # Unknown model (no validation)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        embedding_model="custom-model",
        embedding_dimensions=512,
    )
    assert settings.embedding_dimensions == 512


def test_azure_openai_embedding_skips_dimension_validation():
    """Test that azure_openai embedding provider skips local-model dimension validation.

    Azure OpenAI uses a deployment name (e.g. text-embedding-3-small) and its own
    dimensions (1536), independent of the Ollama dimension_map. The embedding_model
    field defaults to 'mxbai-embed-large' and must not trigger a mismatch error.
    This is exactly the production configuration (EMBEDDING_PROVIDER=azure_openai,
    EMBEDDING_DIMENSIONS=1536, EMBEDDING_MODEL=mxbai-embed-large default).
    """
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        embedding_provider="azure_openai",
        embedding_model="mxbai-embed-large",  # default value — not used by azure_openai
        embedding_dimensions=1536,  # text-embedding-3-small dimension
        azure_openai_endpoint="https://eastus.api.cognitive.microsoft.com/",
        azure_openai_api_key="test-key",  # pragma: allowlist secret
    )
    assert settings.embedding_provider == "azure_openai"
    assert settings.embedding_dimensions == 1536


def test_turnstile_requires_keys_when_enabled():
    """Test that turnstile_enabled=true requires secret_key and site_key."""
    # Missing both keys
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            turnstile_enabled=True,
            turnstile_secret_key=None,
            turnstile_site_key=None,
        )
    error_msg = str(exc_info.value)
    # Should fail on secret_key first (validator checks secret_key, then site_key)
    assert "turnstile_secret_key is required when turnstile_enabled=true" in error_msg
    assert "TURNSTILE_SECRET_KEY" in error_msg

    # Missing secret_key only
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            turnstile_enabled=True,
            turnstile_secret_key=None,
            turnstile_site_key="test-site-key",  # pragma: allowlist secret
        )
    error_msg = str(exc_info.value)
    assert "turnstile_secret_key is required when turnstile_enabled=true" in error_msg

    # Missing site_key only
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
            turnstile_enabled=True,
            turnstile_secret_key="test-secret-key",  # pragma: allowlist secret
            turnstile_site_key=None,
        )
    error_msg = str(exc_info.value)
    assert "turnstile_site_key is required when turnstile_enabled=true" in error_msg
    assert "TURNSTILE_SITE_KEY" in error_msg


def test_turnstile_skips_validation_when_disabled():
    """Test that turnstile_enabled=false skips key validation."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        turnstile_enabled=False,
        turnstile_secret_key=None,
        turnstile_site_key=None,
    )
    assert settings.turnstile_enabled is False


def test_valid_config_passes():
    """Test that a valid configuration with all defaults passes."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
        llm_provider="ollama",
        embedding_provider="ollama",
        turnstile_enabled=False,
    )
    assert settings.llm_provider == "ollama"
    assert settings.embedding_provider == "ollama"
    assert settings.turnstile_enabled is False

"""
Application configuration using Pydantic Settings.
Supports environment variables and .env files.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Vox Quieta"
    app_version: str = "0.1.0"
    debug: bool = False  # Set DEBUG=true in .env for development

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
    # Fallback models (comma-separated) - used when primary model is rate limited
    # Default: paid version of llama-3.3-70b for when free tier hits limits
    openrouter_fallback_models: str = "meta-llama/llama-3.3-70b-instruct"
    # Allow automatic fallback to other providers/models
    openrouter_allow_fallbacks: bool = True
    # Preferred minimum throughput (tokens/sec at p50) for provider selection.
    # Providers below this threshold are deprioritized in favour of faster ones,
    # including paid fallbacks. Set to 0 to disable throughput-based routing.
    openrouter_preferred_min_throughput_p50: int = 50
    # Language-specific model overrides (comma-separated lang=model pairs)
    # Routes requests in unsupported languages to a model that handles them better
    # Example: "ar=qwen/qwen-2.5-72b-instruct,zh=qwen/qwen-2.5-72b-instruct"
    language_model_overrides: str = "ar=qwen/qwen-2.5-72b-instruct"

    # Embedding Configuration
    embedding_provider: Literal["ollama", "openai", "openrouter", "azure_openai"] = "ollama"
    embedding_model: str = "mxbai-embed-large"  # Multilingual model (100+ languages)
    embedding_dimensions: int = 1024  # mxbai-embed-large dimension (was 768 for nomic)

    # Azure OpenAI Settings (optional - for Azure deployment)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_embedding_deployment: str = "text-embedding-3-small"

    # Database - MUST be configured via DATABASE_URL environment variable
    # Default is a non-functional placeholder to prevent accidental use of hardcoded credentials
    database_url: str = (
        "postgresql://CONFIGURE_ME:CONFIGURE_ME@localhost:5432/bibledb"  # pragma: allowlist secret
    )

    # Chat Settings
    max_context_verses: int = 10  # Max verses to include in context
    max_conversation_history: int = 10  # Max messages to keep in context

    # Query Expansion Settings
    query_expansion_enabled: bool = False  # Feature flag for A/B testing

    # Hybrid Search Settings
    hybrid_search_enabled: bool = False  # Feature flag for A/B testing
    hybrid_search_semantic_weight: float = 0.7
    hybrid_search_keyword_weight: float = 0.3

    # Topic Boosting Settings
    topic_boosting_enabled: bool = False  # Feature flag for topic-based search boosting
    topic_boost_factor: float = 0.2  # 20% boost per matching topic

    # Email Settings (SMTP2GO HTTP API)
    smtp2go_enabled: bool = False  # Set to True to enable email notifications
    smtp2go_api_key: str | None = None  # SMTP2GO API key
    smtp2go_sender_email: str = "noreply@voxquieta.org"
    smtp2go_sender_name: str = "Vox Quieta"
    contact_notification_email: str = "support@voxquieta.org"

    # Production frontend URL (used for CORS, access audit, and Referer headers)
    # Change this when migrating to a new domain.
    production_frontend_url: str = "https://voxquieta.org"

    # CORS Settings
    # Comma-separated list of allowed origins (in addition to localhost and production_frontend_url)
    # Example: "https://myapp.azurecontainerapps.io,https://example.com"
    cors_origins: str = ""

    # Logging
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Health Checks
    health_check_timeout: int = (
        15  # Timeout for dependency checks in seconds (longer for free APIs)
    )
    memory_warning_threshold_mb: int = 512  # Memory usage warning threshold

    # Security Settings
    max_message_length: int = 200  # Max characters per chat message
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 20  # Per IP address
    rate_limit_requests_per_session_minute: int = 10  # Per session per minute
    rate_limit_session_max_requests: int = 10  # Lifetime max per session (encourages breaks)
    content_filter_enabled: bool = True
    content_filter_block_profanity: bool = True
    content_filter_block_spam: bool = True
    content_filter_max_repeated_chars: int = 5  # Block excessive repeated chars
    content_filter_max_urls: int = 0  # Block URLs (0 = no URLs allowed)
    content_filter_intent_detection: bool = True  # Pre-LLM intent classification
    security_log_violations: bool = True  # Log security violations

    # Performance Monitoring
    slow_query_threshold_ms: int = 100  # Log queries slower than this (milliseconds)
    # Per-query timeout for verse/chapter lookups. A hung PostgreSQL call is
    # aborted after this many seconds so the API returns 504 instead of blocking
    # forever. Well above normal latency (single-digit ms) but below upstream
    # proxy/client timeouts.
    verse_query_timeout_s: float = 5.0

    # Cloudflare Turnstile (Bot Protection)
    # Get keys from: https://dash.cloudflare.com/?to=/:account/turnstile
    turnstile_enabled: bool = False  # Enable Turnstile verification
    turnstile_secret_key: str | None = None  # Server-side secret key
    turnstile_site_key: str | None = None  # Client-side site key (for /config endpoint)
    # Skip verification for these paths (prefix match).
    # Health probes, docs, and info endpoints don't go through the frontend
    # Turnstile widget and must work without a token.
    turnstile_skip_paths: str = "/health,/docs,/redoc,/openapi.json,/config,/,/api/v1/client-errors"
    # Development: Use Cloudflare test keys for local testing
    # Test secret: 1x0000000000000000000000000000000AA (always passes)
    # Test secret: 2x0000000000000000000000000000000AA (always fails)
    # Test secret: 3x0000000000000000000000000000000AA (forces interactive challenge)

    # Synthetic monitor probe — shared secret that lets an authorized
    # server-to-server probe bypass Turnstile and rate limits via the
    # X-Monitor-Probe-Secret header. Leave None/empty to disable bypass.
    monitor_probe_secret: str | None = None

    # Azure Content Safety Settings
    azure_content_safety_enabled: bool = False  # Enable Azure Content Safety API
    azure_content_safety_endpoint: str | None = None  # Azure endpoint URL
    azure_content_safety_key: str | None = None  # Azure API key
    azure_content_safety_threshold: int = 4  # Severity 0-6, block >= threshold

    # Content Safety Mode
    # Content safety pipeline mode:
    #   keyword_only — Stage 1 (directed harm + hate speech keywords) +
    #                  Stage 2 (OpenAI Moderation API, ~100-150ms, free).
    #                  Recommended production setting: context-aware, no false positives.
    #   ml_only      — Stage 1 + Stage 2 (Llama Guard 3 via OpenRouter, ~270ms overhead).
    #                  Best balance of accuracy and cost (free tier available).
    #   hybrid       — Stage 1 + Stage 2 (OpenAI Moderation) + Stage 3 (Azure Content Safety).
    #                  Maximum accuracy, requires Azure Content Safety resource.
    content_safety_enabled: bool = False  # Master switch (default False for gradual rollout)
    content_safety_mode: Literal["keyword_only", "hybrid", "ml_only"] = "ml_only"

    # Llama Guard Settings
    # Note: These settings only apply when content_safety_mode is ml_only.
    llama_guard_threshold: float = 0.5  # Unused (binary safe/unsafe output), kept for consistency
    llama_guard_timeout: int = 10  # LLM inference timeout (seconds)

    # OpenAI Moderation Settings
    # Used as Stage 2 in keyword_only and hybrid modes (ml_only uses Llama Guard instead).
    # Free, no rate limits, ~100-150ms. Endpoint: https://api.openai.com/v1/moderations
    # Requires OPENAI_API_KEY. OpenRouter does not proxy /v1/moderations.
    openai_moderation_threshold: float = 0.5  # Block if score >= threshold
    openai_moderation_timeout: int = 3  # Seconds before fail-open fallback

    # Blocked-message sample capture (for filter tuning).
    # Stores a privacy-minimal record of messages the safety system blocked:
    # truncated text, stage/categories, hashed session id, TTL-bounded.
    # Default off — operators opt in per environment so tests and local dev
    # don't accidentally write capture rows.
    blocked_sample_capture_enabled: bool = False
    blocked_sample_retention_days: int = 30
    blocked_sample_max_chars: int = 500

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate that database_url is not using placeholder value."""
        if "CONFIGURE_ME" in v:
            raise ValueError(
                "DATABASE_URL must be configured (currently set to placeholder value). "
                "Set the DATABASE_URL environment variable."
            )
        return v

    @model_validator(mode="after")
    def validate_llm_provider_keys(self) -> "Settings":
        """Validate LLM provider API keys."""
        if self.llm_provider == "claude" and self.anthropic_api_key is None:
            raise ValueError(
                "anthropic_api_key is required when llm_provider=claude. "
                "Set ANTHROPIC_API_KEY environment variable."
            )
        if self.llm_provider == "openai" and self.openai_api_key is None:
            raise ValueError(
                "openai_api_key is required when llm_provider=openai. "
                "Set OPENAI_API_KEY environment variable."
            )
        if self.llm_provider == "openrouter" and self.openrouter_api_key is None:
            raise ValueError(
                "openrouter_api_key is required when llm_provider=openrouter. "
                "Set OPENROUTER_API_KEY environment variable."
            )
        return self

    @model_validator(mode="after")
    def validate_embedding_provider_keys(self) -> "Settings":
        """Validate embedding provider API keys and configuration."""
        if self.embedding_provider == "openai" and self.openai_api_key is None:
            raise ValueError(
                "openai_api_key is required when embedding_provider=openai. "
                "Set OPENAI_API_KEY environment variable."
            )
        if self.embedding_provider == "azure_openai" and (
            self.azure_openai_endpoint is None or self.azure_openai_api_key is None
        ):
            raise ValueError(
                "azure_openai_endpoint and azure_openai_api_key are required "
                "when embedding_provider=azure_openai."
            )
        return self

    @model_validator(mode="after")
    def validate_embedding_dimensions(self) -> "Settings":
        """Validate embedding dimensions match the model requirements.

        Only validates Ollama local models (mxbai-embed-large, nomic-embed-text).
        Azure OpenAI uses a separate deployment name (azure_embedding_deployment) and
        its own dimensions (e.g. 1536 for text-embedding-3-small), so we skip this
        check when embedding_provider=azure_openai.
        """
        if self.embedding_provider == "azure_openai":
            # Azure OpenAI uses azure_embedding_deployment, not embedding_model.
            # The embedding_model field is irrelevant when azure_openai is the provider,
            # so dimension validation is skipped.
            return self
        dimension_map = {
            "mxbai-embed-large": 1024,
            "nomic-embed-text": 768,
        }
        if self.embedding_model in dimension_map:
            expected = dimension_map[self.embedding_model]
            if self.embedding_dimensions != expected:
                raise ValueError(
                    f"Embedding dimensions mismatch: {self.embedding_model} requires "
                    f"{expected} dimensions, but config has {self.embedding_dimensions}"
                )
        return self

    @model_validator(mode="after")
    def validate_turnstile_keys(self) -> "Settings":
        """Validate Turnstile configuration when enabled."""
        if self.turnstile_enabled:
            if self.turnstile_secret_key is None:
                raise ValueError(
                    "turnstile_secret_key is required when turnstile_enabled=true. "
                    "Set TURNSTILE_SECRET_KEY environment variable."
                )
            if self.turnstile_site_key is None:
                raise ValueError(
                    "turnstile_site_key is required when turnstile_enabled=true. "
                    "Set TURNSTILE_SITE_KEY environment variable."
                )
        return self

    @model_validator(mode="after")
    def validate_hybrid_weights(self) -> "Settings":
        """Ensure hybrid search weights sum to 1.0."""
        semantic = self.hybrid_search_semantic_weight
        keyword = self.hybrid_search_keyword_weight
        if not (0.0 <= semantic <= 1.0):
            raise ValueError(
                f"hybrid_search_semantic_weight must be between 0.0 and 1.0, got {semantic}"
            )
        if not (0.0 <= keyword <= 1.0):
            raise ValueError(
                f"hybrid_search_keyword_weight must be between 0.0 and 1.0, got {keyword}"
            )
        if abs((semantic + keyword) - 1.0) > 0.01:
            raise ValueError(
                f"Hybrid search weights must sum to 1.0, got "
                f"semantic={semantic}, keyword={keyword}, sum={semantic + keyword}"
            )
        return self

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

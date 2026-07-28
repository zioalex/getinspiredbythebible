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

    # Embedding resilience (BITB-057 Phase 2). Mirrors the circuit-breaker/timeout
    # pattern already used for OpenRouter (providers/openrouter.py) and Llama Guard
    # (providers/llama_guard.py), applied to the embedding call path via
    # providers/embedding_resilience.py::ResilientEmbeddingProvider.
    embedding_request_timeout: float = 15.0  # Seconds before an embed() call is abandoned
    embedding_breaker_failure_threshold: int = 5  # Consecutive failures before the breaker opens
    embedding_breaker_cooldown_seconds: float = 30.0  # Time before a half-open probe is allowed
    embedding_retry_max_attempts: int = 2  # Total attempts (including the first) per embed call
    embedding_retry_base_delay_seconds: float = 0.5  # Base for jittered exponential backoff

    # Embedding cache (BITB-057 Phase 2). In-process only - no Redis or other
    # shared cache exists anywhere in this stack, so a hit on one replica does
    # not help another. See providers/embedding_cache.py::CachingEmbeddingProvider.
    embedding_cache_enabled: bool = True
    embedding_cache_max_size: int = 1024  # Entries; hot-query working set is small
    embedding_cache_ttl_seconds: float = 3600.0  # 1h - mainly a memory/staleness bound

    # Azure OpenAI Settings (optional - for Azure deployment)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_embedding_deployment: str = "text-embedding-3-small"

    # Database - MUST be configured via DATABASE_URL environment variable
    # Default is a non-functional placeholder to prevent accidental use of hardcoded credentials
    database_url: str = (
        "postgresql://CONFIGURE_ME:CONFIGURE_ME@localhost:5432/bibledb"  # pragma: allowlist secret
    )

    # Async SQLAlchemy connection pool. Replaces the previous NullPool (no pooling):
    # a bounded pool removes per-request connect/TLS overhead and caps the number of
    # concurrent backends well under the PostgreSQL server's max_connections for a
    # single API worker. db_pool_size + db_max_overflow is the hard ceiling on backends.
    db_pool_size: int = 10
    db_max_overflow: int = 10  # burst capacity above pool_size
    db_pool_timeout: int = 30  # seconds to wait for a free connection before erroring
    db_pool_recycle: int = 1800  # recycle a connection after 30 min (avoid stale/idle drops)
    # Per-query ceilings so a slow/hung backend fails fast and *visibly* (raises ->
    # logged + metric + retried) instead of holding a pooled connection until
    # db_pool_timeout (30s) and cascading into pool exhaustion. Sizing: normal queries
    # run <100ms (slow_query_threshold_ms); the p95 *saturation* SLOs are 1s (verse
    # reads, BITB-041) and 2s (semantic search, BITB-056). These ceilings sit ~4x above
    # the 2s saturation line — high enough never to cancel a legitimately slow query
    # even during a concurrency spike (~8x baseline at conc 64), low enough to free the
    # connection well before the 30s pool timeout. statement_timeout (server) is set
    # below command_timeout (client) so Postgres cancels first and asyncpg surfaces a
    # clean "canceling statement due to statement timeout" error instead of a raw
    # socket timeout.
    db_command_timeout: int = 10  # asyncpg client-side per-query timeout (seconds)
    db_statement_timeout_ms: int = 8000  # server-side statement_timeout (milliseconds)

    # Chat Settings
    max_context_verses: int = 10  # Max verses to include in context
    max_conversation_history: int = 10  # Max messages to keep in context
    # BITB-058: fail closed when a scripture-seeking request cannot be grounded in any
    # verse (hard retrieval failure OR zero results). Rather than answer without
    # scripture — which undercuts a Bible-grounded product — return a localized
    # "try again" message. Greetings / off-topic / GENERAL chit-chat are exempt so we
    # never nag when no citation was expected.
    require_scripture_grounding: bool = True

    # Query Expansion Settings
    query_expansion_enabled: bool = (
        True  # BITB-043: enabled (improved theme-focused expansion, BITB-050)
    )

    # Hybrid Search Settings
    hybrid_search_enabled: bool = True  # BITB-043: enabled (semantic + FTS keyword, no LLM cost)
    hybrid_search_semantic_weight: float = 0.7
    hybrid_search_keyword_weight: float = 0.3
    # Size of the HNSW ANN candidate pool fetched per query embedding before
    # threshold + hybrid re-ranking. Keeps vector search index-backed (the index
    # only accelerates `ORDER BY embedding <=> q LIMIT k`) instead of a full scan.
    vector_candidate_pool: int = 100
    # HNSW query-time exploration depth (hnsw.ef_search). MUST be >= vector_candidate_pool,
    # otherwise the ANN cannot return a full candidate pool and recall is silently capped
    # (pgvector default is 40; migration 002 set 80 — below the pool of 100). The runtime
    # source of truth is the connection pool, which applies this per session on connect
    # (api/scripture/database.py); migration 007 also tries to set the DB-wide default via
    # `ALTER DATABASE ... SET hnsw.ef_search`, but that is best-effort (the managed-Postgres
    # app role lacks the privilege), so the per-session SET is what the search path relies on.
    hnsw_ef_search: int = 120

    # Topic Boosting Settings
    topic_boosting_enabled: bool = False  # Feature flag for topic-based search boosting
    topic_boost_factor: float = 0.2  # 20% boost per matching topic

    # Email Settings (SMTP2GO HTTP API)
    smtp2go_enabled: bool = False  # Set to True to enable email notifications
    smtp2go_api_key: str | None = None  # SMTP2GO API key
    smtp2go_sender_email: str = "noreply@voxquieta.org"
    smtp2go_sender_name: str = "Vox Quieta"
    contact_notification_email: str = "support@voxquieta.org"
    # Recipient for the weekly activity digest (kept separate from the
    # contact-form recipient so the two can be retargeted independently).
    weekly_report_recipient: str = "support@voxquieta.org"

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
    # Readiness probe checks ONLY the database and must answer well within the
    # platform readiness-probe deadline (deployment/main.tf readiness_probe.timeout,
    # currently 5s), so it uses a short timeout independent of the 15s budget the
    # comprehensive /health endpoint allows for slow free-tier inference providers.
    readiness_check_timeout: int = 3
    memory_warning_threshold_mb: int = 512  # Memory usage warning threshold

    # Security Settings
    max_message_length: int = 500  # Max characters per chat message
    rate_limit_enabled: bool = True
    # BITB-061: "postgres" shares counters across replicas and survives
    # restarts/deploys (the whole point of this setting); "memory" is the
    # legacy in-process behavior, kept reachable for tests and local dev
    # without a database.
    rate_limit_backend: Literal["postgres", "memory"] = "postgres"
    rate_limit_requests_per_minute: int = 20  # Per IP address
    rate_limit_requests_per_session_minute: int = 10  # Per session per minute
    rate_limit_session_max_requests: int = 10  # Lifetime max per session (encourages breaks)
    rate_limit_session_ttl_seconds: int = (
        3600  # Retain a session's lifetime counter for this long after its last request
    )
    content_filter_enabled: bool = True
    content_filter_block_profanity: bool = True
    content_filter_block_spam: bool = True
    content_filter_max_repeated_chars: int = 5  # Block excessive repeated chars
    content_filter_max_urls: int = 0  # Block URLs (0 = no URLs allowed)
    content_filter_intent_detection: bool = True  # Pre-LLM intent classification
    security_log_violations: bool = True  # Log security violations

    # Verse grounding (post-generation scripture fidelity)
    verse_grounding_enabled: bool = True  # Correct fabricated/mismatched inline verse quotes
    # BITB-054: how to handle an inline-quoted citation that cannot be resolved to any
    # canonical DB text (translation not loaded/partial, or the reference is invalid).
    #   keep   — leave the model's text untouched (a Correction is still recorded).
    #   strip  — remove the invented quotation, keeping the reference and surrounding prose.
    #   notice — replace the invented quotation with a short localized message
    #            ("this verse isn't available in <language> yet").
    # Default "strip": per BITB-054 analysis, leaving an unverifiable, possibly
    # hallucinated quotation untouched is not least-user-harm even though it was the
    # historical default (grounding_strip_unresolved=False) — stripping the
    # unverifiable text while keeping the reference is the safer default.
    grounding_unresolved_behavior: Literal["keep", "strip", "notice"] = "strip"
    # BITB-053: ground unquoted/paraphrased verse citations — the LLM presenting a
    # verse as plain prose without quotation marks, which pass 1 (quoted-span
    # grounding) can never see.
    #   off    — pass 2 does not run.
    #   detect — classify every response and count detections
    #            (chat.verse_grounding.paraphrase_detections, applied=false) but
    #            never edit the text. Zero user-visible effect.
    #   append — additionally append the canonical verse text in quotes right
    #            after the reference, so the user sees the real wording.
    # Default "detect": the append is additive (injects verse text into the
    # user-facing reply), so it must earn its way in with data. Run detect on all
    # traffic first, then follow docs/HOW-TO-ROLLOUT-PARAPHRASE-GROUNDING.md to
    # decide whether the detection rate and sampled precision justify "append".
    grounding_paraphrases_mode: Literal["off", "detect", "append"] = "detect"

    # Performance Monitoring
    slow_query_threshold_ms: int = 100  # Log queries slower than this (milliseconds)
    verse_query_timeout_s: float = 10.0  # Max seconds for a verse/chapter DB query before 504

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
    # Separate, rotatable secret for the browser smoke test (BITB-064). Kept
    # distinct from monitor_probe_secret so a leak (it transits a real, if
    # ephemeral, CI browser) is revocable without disturbing the server-to-server
    # probes. Same X-Monitor-Probe-Secret header; leave None/empty to disable.
    smoke_probe_secret: str | None = None

    # Client-side error reporting (BITB-066). The frontend POSTs JS/render/API
    # errors to /api/v1/client-errors; the endpoint records a metric so a spike
    # (e.g. a browser-only outage) alerts. Cap the free-text detail to bound
    # log/metric size and abuse.
    client_error_reporting_enabled: bool = True
    client_error_max_detail_chars: int = 500

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
    content_safety_enabled: bool = True  # Master switch (matches Terraform prod default)
    content_safety_mode: Literal["keyword_only", "hybrid", "ml_only"] = "ml_only"

    # Llama Guard Settings
    # Note: These settings only apply when content_safety_mode is ml_only.
    llama_guard_threshold: float = 0.5  # Unused (binary safe/unsafe output), kept for consistency
    # Primary-model timeout (seconds). A 2026-07 100-sample production benchmark measured
    # primary p50/p95/p99 ~338/1450/2341ms, so 3s comfortably covers normal latency while
    # capping how long a hung/slow primary call blocks the chat request before the secondary
    # model (providers/llama_guard.py, LlamaGuardProvider.SECONDARY_TIMEOUT_SECONDS) is tried.
    # Previously 10s — combined with the secondary's own timeout, worst case could reach ~20s
    # on a single chat message, which is too slow for a synchronous pre-generation safety check.
    llama_guard_timeout: int = 3  # LLM inference timeout (seconds)

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
    def validate_hnsw_ef_search(self) -> "Settings":
        """hnsw.ef_search must be >= the ANN candidate pool, else recall is silently capped."""
        if self.hnsw_ef_search < self.vector_candidate_pool:
            raise ValueError(
                f"hnsw_ef_search ({self.hnsw_ef_search}) must be >= vector_candidate_pool "
                f"({self.vector_candidate_pool}); a smaller ef_search caps the candidate pool "
                "the HNSW index can return and degrades search recall."
            )
        return self

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

"""
Custom OpenTelemetry metrics for usage tracking.

Metrics are recorded via the OpenTelemetry API. When Application Insights
(or any OTLP-compatible backend) is configured, they are automatically
exported. When no backend is configured, the API gracefully no-ops.
"""

from opentelemetry import metrics

meter = metrics.get_meter("bible_app")

# ── Chat metrics ──────────────────────────────────────────────────────────
chat_messages_counter = meter.create_counter(
    name="chat.messages.total",
    description="Total chat messages processed",
    unit="1",
)

chat_response_time = meter.create_histogram(
    name="chat.response_time_ms",
    description="Chat response time in milliseconds",
    unit="ms",
)

chat_sessions_counter = meter.create_counter(
    name="chat.sessions.active",
    description="Session activity events (one per chat request with a session token)",
    unit="1",
)

chat_stream_counter = meter.create_counter(
    name="chat.stream.total",
    description="Total streaming chat requests",
    unit="1",
)

# Per-stage latency breakdown within a single chat request. The `stage` attribute
# carries which step the duration belongs to (content_safety | intent |
# query_expansion | retrieval | ttft | generation | grounding | total), so a single
# histogram answers "where does the minute go?" without one metric per stage.
chat_stage_duration_histogram = meter.create_histogram(
    name="chat.stage.duration_ms",
    description="Per-stage latency within a single chat request",
    unit="ms",
)  # attributes: stage, stream (bool), provider

# ── Verse grounding / scripture-fidelity metrics ──────────────────────────
# Post-generation grounding rewrites fabricated/mismatched inline verse quotes
# to the canonical DB text. These metrics make recurrences visible and track the
# latency the step adds, so we never trade correctness for a silent slowdown.
verse_grounding_quotes_checked_counter = meter.create_counter(
    name="chat.verse_grounding.quotes_checked",
    description="Inline verse quotes inspected by the grounding step",
    unit="1",
)  # attributes: language

verse_grounding_corrections_counter = meter.create_counter(
    name="chat.verse_grounding.corrections",
    description="Inline verse quotes found fabricated/mismatched/unresolved during grounding",
    unit="1",
)  # attributes: language, reason (fabricated|mismatched|unresolved), corrected (bool), book

verse_grounding_duration_histogram = meter.create_histogram(
    name="chat.verse_grounding.duration_ms",
    description="Latency overhead added by the post-generation grounding/correction step",
    unit="ms",
)  # attributes: language, corrected (bool)

# Unquoted-paraphrase grounding (BITB-053, Pass 2). One count per detected
# paraphrase. `applied` is False in detect-only mode (grounding_paraphrases_mode
# = "detect": classified and counted but the text is untouched) and True when
# the canonical text was actually appended ("append" mode). `bracketed` is True
# when the (would-be) append lands before a closing bracket — i.e. the reference
# was parenthesised and the canonical text nests inside, e.g.
# (Isaia 41:10 ("Non temere…")). This metric drives the measurement rollout in
# docs/HOW-TO-ROLLOUT-PARAPHRASE-GROUNDING.md and the nested-parens alert in
# monitoring.tf.
verse_grounding_paraphrase_detections_counter = meter.create_counter(
    name="chat.verse_grounding.paraphrase_detections",
    description="Unquoted-paraphrase detections (BITB-053); applied=True means canonical text was appended, bracketed=True means the append point sits before a closing bracket (nested-parens artifact)",
    unit="1",
)  # attributes: language, bracketed (bool), applied (bool)

# ── Translation data-coverage diagnostics (BITB-054) ──────────────────────
# A supported UI language whose backing translation has zero verses (never
# loaded) or zero embeddings (loaded but unsearchable) degrades silently —
# empty search results, or citations grounding can never resolve. Checked at
# startup (api/main.py) and on-demand via the admin diagnostic endpoint
# (routes/admin.py), both backed by scripture/coverage.py.
translation_data_missing_counter = meter.create_counter(
    name="scripture.translation_data.missing",
    description="Supported language whose backing translation has zero verses or zero embeddings",
    unit="1",
)  # attributes: language, translation, problem (no_verses|no_embeddings)

# ── Scripture metrics ─────────────────────────────────────────────────────
scripture_search_counter = meter.create_counter(
    name="scripture.search.total",
    description="Total scripture search requests",
    unit="1",
)

scripture_verses_returned = meter.create_histogram(
    name="scripture.verses.returned",
    description="Number of verses returned per search",
    unit="1",
)

scripture_fetch_errors_counter = meter.create_counter(
    name="scripture.fetch.errors",
    description="Verse/chapter fetch failures by reason (timeout/db_error/empty_text) and endpoint",
    unit="1",
)

# ── Scripture pipeline failure counters (BITB-055) ───────────────────────
# Emitted by the three fail-open exception handlers in chat/service.py so
# silent pipeline degradations surface as explicit metrics rather than
# disappearing into swallowed log lines.
scripture_pipeline_errors_counter = meter.create_counter(
    name="scripture.pipeline.errors",
    description="Fail-open exceptions in the chat scripture pipeline (stage: search/resolve/grounding)",
    unit="1",
)  # attributes: stage (search|resolve|grounding), error_type

chat_verseless_responses_counter = meter.create_counter(
    name="chat.responses.verseless",
    description="Chat responses with include_search=True but zero DB context verses AND zero resolved citations",
    unit="1",
)  # attributes: language

chat_scripture_unavailable_counter = meter.create_counter(
    name="chat.responses.scripture_unavailable",
    description="Scripture-seeking chat requests answered fail-closed (BITB-058) because no scripture could be retrieved",
    unit="1",
)  # attributes: language

# ── Church metrics ────────────────────────────────────────────────────────
church_search_counter = meter.create_counter(
    name="church.search.total",
    description="Total church search requests",
    unit="1",
)

# ── Feedback metrics ──────────────────────────────────────────────────────
feedback_counter = meter.create_counter(
    name="feedback.total",
    description="Total feedback submissions",
    unit="1",
)

contact_form_counter = meter.create_counter(
    name="feedback.contact.total",
    description="Total contact form submissions",
    unit="1",
)

# ── LLM performance metrics ───────────────────────────────────────────────
llm_ttft_histogram = meter.create_histogram(
    name="llm.ttft_ms",
    description="Time to first token (TTFT) in milliseconds",
    unit="ms",
)

llm_total_duration_histogram = meter.create_histogram(
    name="llm.total_duration_ms",
    description="Total LLM generation duration in milliseconds",
    unit="ms",
)

llm_fallback_counter = meter.create_counter(
    name="llm.fallback_count",
    description="Count of LLM fallback invocations",
    unit="1",
)

llm_rate_limit_counter = meter.create_counter(
    name="llm.rate_limit_hits",
    description="Count of HTTP 429 rate limit responses from LLM provider",
    unit="1",
)

llm_tokens_per_second_histogram = meter.create_histogram(
    name="llm.tokens_per_second",
    description="Token generation throughput (tokens/sec)",
    unit="1",
)

# ── Database performance metrics ──────────────────────────────────────────
db_search_duration_histogram = meter.create_histogram(
    name="db.search.duration_ms",
    description="Semantic search (pgvector cosine similarity) duration in milliseconds",
    unit="ms",
)

db_query_duration_histogram = meter.create_histogram(
    name="db.query.duration_ms",
    description="General SQL query duration in milliseconds",
    unit="ms",
)

db_connections_active_gauge = meter.create_up_down_counter(
    name="db.connections.active",
    description="Number of active database connections",
    unit="1",
)

db_slow_queries_counter = meter.create_counter(
    name="db.slow_queries",
    description="Count of queries exceeding slow query threshold (default 100ms)",
    unit="1",
)

# ── Access audit metrics ─────────────────────────────────────────────────
api_access_counter = meter.create_counter(
    name="api.access.total",
    description="Total API requests by source classification (official/unofficial)",
    unit="1",
)

# ── External dependency resilience metrics ───────────────────────────────
# These exist so log-based alerts can be replaced with metric-based alerts:
# alert when the fallback rate spikes, not when ERROR logs appear.
llama_guard_fallback_counter = meter.create_counter(
    name="llama_guard.fallback_total",
    description="Count of Llama Guard failures that fell back to the keyword filter",
    unit="1",
)

openrouter_fallback_counter = meter.create_counter(
    name="openrouter.fallback_total",
    description="Count of OpenRouter primary-model failures that triggered client-side fallback",
    unit="1",
)

embedding_fallback_counter = meter.create_counter(
    name="embedding.fallback_total",
    description=(
        "Count of embedding provider retries, timeouts, and circuit-open events "
        "handled by ResilientEmbeddingProvider"
    ),
    unit="1",
)

circuit_breaker_state_counter = meter.create_counter(
    name="circuit_breaker.state_transitions",
    description="Circuit breaker state transitions (open/half_open/closed)",
    unit="1",
)

turnstile_fail_open_counter = meter.create_counter(
    name="turnstile.fail_open_total",
    description="Count of Turnstile siteverify transient failures that were allowed through (failed open)",
    unit="1",
)  # attributes: reason (timeout|http_<status>|http_error|<exc_name>)

client_errors_counter = meter.create_counter(
    name="client.errors_total",
    description="Client-side error reports received at /api/v1/client-errors (BITB-066)",
    unit="1",
)  # attributes: type (window_onerror|unhandledrejection|api_failure|react_render|turnstile|other)

preflight_errors_counter = meter.create_counter(
    name="api.preflight_errors_total",
    description="CORS preflight (OPTIONS) requests that returned HTTP 5xx — browser-only failure signal (BITB-066)",
    unit="1",
)  # attributes: status, path

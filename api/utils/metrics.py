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

circuit_breaker_state_counter = meter.create_counter(
    name="circuit_breaker.state_transitions",
    description="Circuit breaker state transitions (open/half_open/closed)",
    unit="1",
)

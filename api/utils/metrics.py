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

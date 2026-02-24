"""
OpenTelemetry tracer configuration for Bible Inspiration Chat API.

Provides pre-configured tracers and metrics for database and LLM instrumentation.
The tracers automatically integrate with Azure Monitor when
APPLICATIONINSIGHTS_CONNECTION_STRING is set.
"""

from opentelemetry import metrics, trace

# Tracer for database/scripture operations.
# When configure_azure_monitor() has been called (in main.py), spans created
# by this tracer will be exported to Azure Application Insights.
# When no exporter is configured, the OTel API is a graceful no-op.
tracer = trace.get_tracer("bible_app.scripture")

# LLM tracer for provider operations (OpenRouter, Claude, Ollama)
llm_tracer = trace.get_tracer("bible_app.llm")

# Metrics for LLM performance monitoring
meter = metrics.get_meter("bible_app.llm")

llm_duration_histogram = meter.create_histogram(
    "llm.duration_ms",
    description="Total LLM call duration in milliseconds",
    unit="ms",
)
llm_ttft_histogram = meter.create_histogram(
    "llm.ttft_ms",
    description="Time to first token in streaming responses",
    unit="ms",
)
llm_tokens_per_second_histogram = meter.create_histogram(
    "llm.tokens_per_second",
    description="Generation speed in tokens per second",
)
llm_tokens_total_counter = meter.create_counter(
    "llm.tokens.total",
    description="Total tokens consumed (prompt + completion)",
)
llm_fallback_attempts_counter = meter.create_counter(
    "llm.fallback.attempts",
    description="Number of times fallback models were attempted",
)
llm_rate_limit_hits_counter = meter.create_counter(
    "llm.rate_limit.hits",
    description="Number of rate limit errors encountered",
)

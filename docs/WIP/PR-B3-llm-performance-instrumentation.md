# PR B3: LLM Performance Instrumentation (OpenTelemetry)

**Status:** In Progress
**PR URL:** (Will be created after implementation)
**Branch:** `feat/llm-performance-instrumentation`
**Base Branch:** `feat/db-performance-instrumentation` (PR B2)
**Started:** 2026-02-24

## Summary

Adds comprehensive OpenTelemetry instrumentation for all LLM provider operations (OpenRouter, Claude, Ollama).
Tracks performance metrics including:

- Total call duration
- Time to First Token (TTFT) for streaming responses
- Tokens per second throughput
- Fallback attempts (OpenRouter)
- Rate limit hits
- Request correlation via correlation IDs from PR B1

## Dependencies

- **PR B1** (feat/correlation-ids): Provides `REQUEST_ID_CTX_VAR` for correlation
- **PR B2** (feat/db-performance-instrumentation): Establishes OTel telemetry patterns

## Changes Made

### 1. `api/utils/telemetry.py`

- Added `llm_tracer` (separate from DB tracer)
- Added OTel metrics:
  - `llm_duration_histogram` — total call duration in ms
  - `llm_ttft_histogram` — time to first token for streaming
  - `llm_tokens_per_second_histogram` — generation speed
  - `llm_tokens_total_counter` — total tokens consumed
  - `llm_fallback_attempts_counter` — fallback attempts
  - `llm_rate_limit_hits_counter` — rate limit errors

### 2. `api/chat/service.py`

- `chat()`: Added span `llm.chat` with attributes:
  - `llm.provider`, `llm.model`, `llm.streaming=False`
  - `llm.duration_ms`, `request_id`
- `chat_stream()`: Added span `llm.chat_stream` with TTFT tracking:
  - Uses try/finally pattern (cannot use `with` across `yield`)
  - Tracks time to first non-empty chunk
  - Sets `llm.ttft_ms` when first token received

### 3. `api/providers/openrouter.py`

- `chat()`: Added span `llm.openrouter.chat` with full token tracking:
  - `llm.tokens.total`, `llm.tokens.prompt`, `llm.tokens.completion`
  - `llm.tokens_per_second` calculated from completion_tokens / duration
  - `llm.model.actual` from response (may differ from request due to auto-router)
  - `llm.fallback.triggered=True` when fallback used
  - `llm.fallback.model` set to fallback model name
  - `llm.rate_limit.hit=True` on 429 errors
- `chat_stream()`: Same as above with TTFT tracking

### 4. `api/providers/claude.py`

- `chat()`: Basic span `llm.claude.chat` with duration and request_id
- `chat_stream()`: Span with TTFT tracking using try/finally

### 5. `api/providers/ollama.py`

- `chat()`: Basic span `llm.ollama.chat` with duration and request_id
- `chat_stream()`: Span with TTFT tracking using try/finally

### 6. `api/tests/test_llm_instrumentation.py`

- `TestLLMTelemetryModule` — verify tracer and metrics are initialized
- `TestChatServiceSpans` — verify chat() creates span with correct attributes
- `TestChatStreamSpans` — verify TTFT tracking in streaming
- `TestOpenRouterFallback` — verify fallback detection sets attributes
- `TestOpenRouterRateLimit` — verify rate limit detection
- `TestClaudeProviderSpans` — verify Claude instrumentation
- `TestOllamaProviderSpans` — verify Ollama instrumentation

## Span Attributes

### Common Attributes (all providers)

- `llm.provider` — "openrouter", "claude", or "ollama"
- `llm.model` — requested model name
- `llm.streaming` — boolean (True for streaming, False for chat)
- `llm.duration_ms` — total call duration in milliseconds
- `request_id` — correlation ID from PR B1 (only set if non-empty)

### OpenRouter-Specific

- `llm.model.actual` — actual model used (may differ from request due to auto-router)
- `llm.tokens.total` — prompt + completion tokens
- `llm.tokens.prompt` — input tokens
- `llm.tokens.completion` — output tokens
- `llm.tokens_per_second` — generation speed (completion_tokens / duration_ms * 1000)
- `llm.fallback.triggered` — boolean, set when fallback activated
- `llm.fallback.model` — name of successful fallback model
- `llm.rate_limit.hit` — boolean, set on 429 errors

### Streaming-Specific

- `llm.ttft_ms` — time to first token (milliseconds from call start to first content chunk)

## Azure Monitor KQL Queries

### LLM Call Duration Percentiles

```kql
dependencies
| where name startswith "llm."
| summarize p50=percentile(duration, 50), p95=percentile(duration, 95), p99=percentile(duration, 99)
  by name, tostring(customDimensions.llm_provider), tostring(customDimensions.llm_model)
| order by p95 desc
```

### Time to First Token for Streaming

```kql
dependencies
| where name in ("llm.chat_stream", "llm.openrouter.chat_stream", "llm.claude.chat_stream", "llm.ollama.chat_stream")
| extend ttft_ms = todouble(customDimensions.llm_ttft_ms)
| where isnotnull(ttft_ms)
| summarize avg(ttft_ms), percentile(ttft_ms, 95), percentile(ttft_ms, 99) by bin(timestamp, 5m)
| render timechart
```

### Fallback Attempts Over Time

```kql
dependencies
| where tostring(customDimensions.llm_fallback_triggered) == "true"
| summarize count() by bin(timestamp, 5m), tostring(customDimensions.llm_provider)
| render timechart
```

### Rate Limit Hits

```kql
dependencies
| where tostring(customDimensions.llm_rate_limit_hit) == "true"
| summarize count() by bin(timestamp, 1h), tostring(customDimensions.llm_provider), tostring(customDimensions.llm_model)
| order by timestamp desc
```

### Tokens Per Second Distribution

```kql
dependencies
| where name startswith "llm.openrouter"
| extend tokens_per_sec = todouble(customDimensions.llm_tokens_per_second)
| where isnotnull(tokens_per_sec)
| summarize avg(tokens_per_sec), percentile(tokens_per_sec, 50), percentile(tokens_per_sec, 95)
  by tostring(customDimensions.llm_model)
| order by avg_tokens_per_sec desc
```

### Correlated LLM + DB Trace

```kql
dependencies
| where customDimensions.request_id == "YOUR-REQUEST-ID"
| project timestamp, name, duration, customDimensions
| order by timestamp asc
```

### End-to-End Request Performance

```kql
dependencies
| where customDimensions.request_id == "YOUR-REQUEST-ID"
| summarize
    total_duration = sum(duration),
    llm_duration = sumif(duration, name startswith "llm."),
    db_duration = sumif(duration, name startswith "db."),
    operation_count = count()
  by request_id = tostring(customDimensions.request_id)
| extend overhead_pct = (total_duration - llm_duration - db_duration) / total_duration * 100
```

## Design Decisions

### 1. Async Generator Instrumentation Pattern

**Issue:** Python async generators cannot use `with span:` context managers across `yield` statements.

**Solution:** Use manual span management with try/finally:

```python
span = llm_tracer.start_span("llm.chat_stream")
start_time = time.perf_counter()
first_token_time: float | None = None
try:
    # ... async for chunk loop with yields ...
finally:
    span.set_attribute("llm.duration_ms", ...)
    span.end()
```

### 2. TTFT Tracking

Track time to **first non-empty chunk** to exclude network latency from initial connection setup.
Set `first_token_time` only when `chunk` is truthy.

### 3. Token Metrics in OpenRouter Only

Claude and Ollama do not expose token usage in the same way (Ollama uses `eval_count` instead).
Only OpenRouter provider sets:

- `llm.tokens.total`, `llm.tokens.prompt`, `llm.tokens.completion`
- `llm.tokens_per_second`

### 4. Fallback and Rate Limit Detection

Only OpenRouter has explicit fallback logic. Set:

- `llm.fallback.triggered=True` when entering fallback loop
- `llm.fallback.model` when fallback succeeds
- `llm.rate_limit.hit=True` when `_is_rate_limit_error()` returns True

### 5. Request Correlation

Include `request_id` from `REQUEST_ID_CTX_VAR` (PR B1) in all spans.
Only set attribute if context var is non-empty to avoid cluttering traces.

## Tasks

- [x] Update `utils/telemetry.py` with LLM tracer and metrics
- [x] Instrument `chat/service.py` chat() and chat_stream()
- [x] Instrument `providers/openrouter.py` with full token tracking
- [x] Instrument `providers/claude.py` with basic spans
- [x] Instrument `providers/ollama.py` with basic spans
- [x] Create comprehensive test suite in `test_llm_instrumentation.py`
- [ ] Run `make test-backend` — verify all tests pass
- [ ] Run `make pre-commit` — verify formatting/linting
- [ ] Push branch and create PR
- [ ] Verify CI passes
- [ ] Merge to `feat/db-performance-instrumentation`

## Progress Log

### 2026-02-24

- Created branch `feat/llm-performance-instrumentation` from `feat/db-performance-instrumentation`
- Implemented all instrumentation changes across 5 files
- Created comprehensive test suite with 8 test classes
- Ready for test validation

## Notes

- All existing DB instrumentation tests (`test_instrumentation.py`) must still pass
- Metrics collection requires Azure Monitor exporter configured via `APPLICATIONINSIGHTS_CONNECTION_STRING`
- Without exporter, OTel API is a graceful no-op (no errors, no overhead)
- TTFT is most valuable for comparing streaming model performance across providers

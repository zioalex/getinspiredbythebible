# BITB-021: Instrument LLM and Database Performance Metrics

**Priority:** P1 (High — dashboard is deployed but shows no data)
**Status:** 🚧 In Progress (dashboard/workbook dependencies complete; backend metrics instrumentation pending)
**Size:** M (4-6 hours)
**Created:** 2026-03-06
**Updated:** 2026-04-20

---

## Background

The Azure Monitor Performance Dashboard was deployed on 2026-03-04 as part of the observability
initiative (PRs B1-B5). The workbook is live in Azure Portal and queries are configured correctly,
but **all panels show "No data"** because the backend is not emitting the specific custom metrics
that the dashboard expects.

**Gap identified:**

The dashboard KQL queries expect these OpenTelemetry custom metrics:

- `llm.ttft_ms` - Time to first token (TTFT) in milliseconds
- `llm.total_duration_ms` - Total LLM generation duration
- `llm.fallback_count` - Count of fallback model invocations
- `llm.rate_limit_hits` - Count of HTTP 429 rate limit responses
- `llm.tokens_per_second` - Token generation throughput
- `db.search.duration_ms` - Semantic search (pgvector) duration
- `db.query.duration_ms` - General SQL query duration
- `db.slow_queries` - Count of queries exceeding 100ms threshold

The backend currently only emits generic metrics (`chat.messages.total`, `chat.response_time_ms`)
that don't match the dashboard's queries.

**Reference docs:**

- Dashboard README: `deployment/azure-monitor/README.md`
- Dashboard JSON: `deployment/azure-monitor/workbook-performance-dashboard.json`
- Current metrics: `api/utils/metrics.py`

---

## User Story

**As a** site reliability engineer monitoring the Bible app in production,
**I want** the Performance Dashboard to display real-time LLM and database metrics,
**so that** I can detect performance degradation, identify bottlenecks (slow queries, high TTFT,
rate limit exhaustion), and correlate errors with infrastructure health without needing to write
custom KQL queries or dig through raw logs.

---

## Problem Statement

### Dashboard Panels Showing "No Data"

The workbook has 5 panels with specific queries:

1. **📊 Overview — Error Detection:** Works (uses built-in `requests` table)
2. **🤖 LLM Performance:** ❌ Empty — expects `llm.ttft_ms`, `llm.total_duration_ms`,
   `llm.fallback_count`, `llm.rate_limit_hits`, `llm.tokens_per_second`
3. **🗄️ Database Performance:** ❌ Empty — expects `db.search.duration_ms`,
   `db.query.duration_ms`, `db.slow_queries`
4. **🚨 Error Analysis:** Works (uses built-in `requests` table with `customDimensions["correlation_id"]`)
5. **🖥️ Infrastructure:** Works (uses built-in `performanceCounters` table)

### Why the Metrics Are Missing

**LLM metrics:**

- `OpenRouterProvider` and `ClaudeProvider` do not record:
  - Time to first token (TTFT) during streaming
  - Total generation duration
  - Fallback invocations (when primary model fails and fallback succeeds)
  - Rate limit hits (HTTP 429 responses)
  - Token throughput (tokens/sec)

**Database metrics:**

- `ScriptureRepository` uses OpenTelemetry **spans** (`utils/telemetry.py`) to record duration on
  traces, but does not emit **metrics** to the `customMetrics` table
- The slow query logger writes to logs but doesn't increment a counter metric

**Root cause:** The dashboard was designed with these metrics in mind, but the backend instrumentation was never implemented.

---

## Functional Requirements

### 1. LLM Metrics Instrumentation

Add new metrics to `api/utils/metrics.py`:

```python
# LLM performance metrics
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
```

**Instrument `OpenRouterProvider` (`api/providers/openrouter.py`):**

- [ ] In `chat_completion_stream()`:
  - Record timestamp before first chunk
  - When first chunk arrives: calculate TTFT, emit `llm_ttft_histogram.record(ttft_ms)`
  - Track total tokens generated and total duration
  - After stream completes: calculate `tokens_per_sec = total_tokens / total_duration`, emit
    `llm_tokens_per_second_histogram.record(tokens_per_sec)` and
    `llm_total_duration_histogram.record(total_duration_ms)`

- [ ] In `_attempt_chat_with_model()`:
  - When catching `RateLimitError` (HTTP 429): emit `llm_rate_limit_counter.add(1)`

- [ ] In `chat_completion_stream()` (fallback handling):
  - When primary model fails and fallback succeeds: emit `llm_fallback_counter.add(1)`

**Instrument `ClaudeProvider` (`api/providers/claude.py`):**

- [ ] Same instrumentation as OpenRouter: TTFT, total duration, tokens/sec
- [ ] Claude API uses different error types — check for rate limit indicators and emit `llm_rate_limit_counter.add(1)`
- [ ] Claude does not have fallback logic (single-model provider), so no fallback counter needed

**Instrument `OllamaProvider` (`api/providers/ollama.py`):**

- [ ] Same TTFT and duration instrumentation
- [ ] Ollama is local and does not rate-limit, so no rate limit counter needed
- [ ] No fallback logic, so no fallback counter needed

---

### 2. Database Metrics Instrumentation

Add new metrics to `api/utils/metrics.py`:

```python
# Database performance metrics
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

db_slow_queries_counter = meter.create_counter(
    name="db.slow_queries",
    description="Count of queries exceeding slow query threshold (default 100ms)",
    unit="1",
)
```

**Instrument `ScriptureRepository` (`api/scripture/repository.py`):**

The repository already has `_record_duration()` helper that:

- Calculates `duration_ms`
- Sets span attributes (`db.duration_ms`, `db.results.count`)
- Logs slow queries when `duration_ms > settings.slow_query_threshold_ms`

- [ ] Modify `_record_duration()` to **also** emit metrics:
  - Determine if operation is a vector search (`operation == "semantic_search"`):
    - If yes: emit `db_search_duration_histogram.record(duration_ms)`
    - If no: emit `db_query_duration_histogram.record(duration_ms)`
  - If `duration_ms > settings.slow_query_threshold_ms`: emit `db_slow_queries_counter.add(1)`

- [ ] Import the new metrics at the top of `scripture/repository.py`

---

### 3. Metrics Export to Application Insights

No changes needed here — the OpenTelemetry `configure_azure_monitor()` in `api/main.py` already
exports all metrics created via `metrics.get_meter("bible_app")` to Application Insights. The new
metrics will automatically appear in the `customMetrics` table.

---

## Non-Functional Requirements

### Performance

- [ ] Metric recording must be lightweight (< 1ms overhead per request)
- [ ] Must not block streaming responses (record TTFT asynchronously after first chunk arrives)
- [ ] Must not introduce memory leaks (use histograms for unbounded values like duration)

### UX

- [ ] Metrics must appear in Application Insights within 60 seconds of emission (guaranteed by Azure Monitor SDK)
- [ ] Dashboard panels must populate with real data after the first production request following deployment

### Reliability

- [ ] Metric recording must never cause request failures (wrap in try/except if necessary)
- [ ] Must work correctly when `APPLICATIONINSIGHTS_CONNECTION_STRING` is not set (OpenTelemetry API gracefully no-ops)
- [ ] Must not break existing instrumentation (tracing spans, logging)

### Testing

- [ ] Add unit tests for new metrics in `api/tests/test_metrics.py`:
  - Verify metrics are defined and callable
  - Verify mock recording succeeds without errors
- [ ] Add integration test for LLM TTFT recording:
  - Send a streaming chat request
  - Verify `llm_ttft_histogram.record()` was called with a positive value
- [ ] Add integration test for database duration recording:
  - Execute a semantic search query
  - Verify `db_search_duration_histogram.record()` was called
- [ ] Run full test suite (`make test`) — must pass 1,033 existing tests

---

## Acceptance Criteria

### LLM Metrics

- [ ] `llm.ttft_ms` appears in Application Insights `customMetrics` table after a streaming chat request
- [ ] `llm.total_duration_ms` appears with a value >= TTFT value
- [ ] `llm.tokens_per_second` appears with a positive value (e.g., 20-50 tokens/sec for typical models)
- [ ] `llm.fallback_count` increments when OpenRouter primary model fails and fallback succeeds
- [ ] `llm.rate_limit_hits` increments when LLM provider returns HTTP 429

### Database Metrics

- [ ] `db.search.duration_ms` appears after a semantic search query (e.g., `/api/chat` endpoint)
- [ ] `db.query.duration_ms` appears after a direct verse lookup (e.g., `/api/scripture/verses`)
- [ ] `db.slow_queries` increments when a query exceeds 100ms (configurable via `settings.slow_query_threshold_ms`)

### Dashboard Validation

- [ ] Open Performance Dashboard in Azure Portal: `https://portal.azure.com/#resource/.../workbook`
- [ ] **🤖 LLM Performance panel:**
  - [ ] "Time to First Token (TTFT)" tile shows P50/P95/P99 values (not "No data")
  - [ ] "Total LLM Duration" tile shows P50/P95/P99 values
  - [ ] "Fallback Rate" tile shows count and percentage (may be 0% if no fallbacks occurred)
  - [ ] "Rate Limit Hits" tile shows count (may be 0 if no rate limits hit)
  - [ ] "Tokens per Second Trend" line chart shows hourly average throughput
- [ ] **🗄️ Database Performance panel:**
  - [ ] "Semantic Search Duration" tile shows P50/P95/P99 values
  - [ ] "General Query Duration" tile shows P50/P95/P99 values
  - [ ] "Slow Query Count Trend" line chart shows count per hour (may be 0 if all queries fast)

### Code Quality

- [ ] All pre-commit hooks pass (Black, Ruff, MyPy, Bandit)
- [ ] Full test suite passes: `make test` (1,033+ tests)
- [ ] No new security issues detected by Bandit
- [ ] Code reviewed and approved in PR

---

## Tech Constraints

### Must Not Break Existing Instrumentation

- The app already uses OpenTelemetry tracing (`utils/telemetry.py`) and logging (`utils/logging_config.py`)
- New metrics instrumentation must coexist with existing traces and logs
- Must not modify or remove existing metrics (`chat.messages.total`, `scripture.search.total`, etc.)

### Must Follow OpenTelemetry Semantic Conventions

- Metric names should follow OTel naming patterns: `component.metric_name` (e.g., `llm.ttft_ms`, `db.query.duration_ms`)
- Use appropriate metric types:
  - **Counter** for monotonically increasing values (fallback count, rate limit hits, slow queries)
  - **Histogram** for distributions (TTFT, duration, tokens/sec)
- Units must be explicit: `ms` for milliseconds, `1` for dimensionless counts

### Must Work in All Environments

- Local development (Docker Compose) — metrics recorded but not exported (no Application Insights configured)
- Production (Azure Container Apps) — metrics exported to Application Insights
- CI/CD (GitHub Actions) — metrics recorded during tests but not exported

---

## Out of Scope

### Not Included in This Story

- [ ] Creating additional dashboard panels beyond the 5 already defined
- [ ] Instrumenting frontend Next.js metrics (separate story)
- [ ] Setting up alert rules in Azure Monitor (separate story)
- [ ] Creating SLOs/SLIs based on these metrics (separate story)
- [ ] Historical backfill of metrics (metrics only appear after deployment)
- [ ] Embedding instrumentation — this story focuses on LLM chat and DB queries only

### Future Enhancements

- **BITB-022:** Add alert rules for high error rate, slow TTFT, rate limit exhaustion
- **BITB-023:** Instrument embedding provider metrics (`embedding.duration_ms`, `embedding.vector_dimensions`)
- **BITB-024:** Add frontend Web Vitals to dashboard (LCP, FID, CLS)

---

## Implementation Notes

### Where to Add Metric Recording

**LLM Providers (`api/providers/`):**

1. **OpenRouterProvider.chat_completion_stream():**
   - Before entering the async for loop: `start_time = time.perf_counter()`
   - On first chunk: `ttft_ms = (time.perf_counter() - start_time) * 1000; llm_ttft_histogram.record(ttft_ms)`
   - Track total tokens and completion time
   - After loop: calculate tokens/sec and total duration, emit histograms

2. **ClaudeProvider.chat_completion_stream():**
   - Same pattern as OpenRouter
   - Claude uses different chunk structure — adapt token counting logic

3. **OllamaProvider.chat_completion_stream():**
   - Same pattern, simpler (no rate limits or fallbacks)

**ScriptureRepository (`api/scripture/repository.py`):**

1. **Modify `_record_duration()` helper:**

   ```python
   def _record_duration(span, start, operation, result_count, translation):
       duration_ms = (time.perf_counter() - start) * 1000
       span.set_attribute("db.duration_ms", round(duration_ms, 2))
       span.set_attribute("db.results.count", result_count)

       # NEW: Emit metrics
       if operation == "semantic_search":
           db_search_duration_histogram.record(duration_ms)
       else:
           db_query_duration_histogram.record(duration_ms)

       if duration_ms > settings.slow_query_threshold_ms:
           db_slow_queries_counter.add(1)  # NEW
           logger.warning(...)  # existing slow query log
   ```

### Testing Strategy

**Unit tests (`api/tests/test_metrics.py`):**

- Verify new metrics are defined and importable
- Mock `record()` and `add()` calls to ensure they succeed without exceptions

**Integration tests:**

- **LLM metrics:** Add test in `api/tests/test_providers.py` that:
  - Mocks OpenRouter API with a streaming response
  - Verifies `llm_ttft_histogram.record()` was called
- **DB metrics:** Add test in `api/tests/test_scripture_repository.py` that:
  - Executes a real semantic search (requires test DB)
  - Verifies `db_search_duration_histogram.record()` was called

**Manual validation:**

- Deploy to production
- Send 5-10 chat requests via web app
- Wait 2 minutes for metrics to propagate
- Open Performance Dashboard in Azure Portal
- Verify all panels show data

---

## Dependencies

- ✅ PRs B1-B5 merged (OpenTelemetry instrumentation, Application Insights, workbook deployed)
- ✅ `APPLICATIONINSIGHTS_CONNECTION_STRING` configured in production environment
- ✅ Performance Dashboard deployed to Azure Monitor Workbooks

---

## Definition of Done

- [ ] New metrics defined in `api/utils/metrics.py`
- [ ] LLM providers instrumented to record TTFT, duration, tokens/sec, fallbacks, rate limits
- [ ] `ScriptureRepository` instrumented to record search/query duration and slow query count
- [ ] Unit tests added and passing
- [ ] Integration tests added and passing
- [ ] Full test suite passes: `make test` (1,033+ tests)
- [ ] Pre-commit hooks pass
- [ ] PR opened with clear description linking to this story
- [ ] Code reviewed and approved
- [ ] PR merged to main
- [ ] Deployed to production via CI/CD
- [ ] Performance Dashboard validated in Azure Portal — all LLM and DB panels showing real data
- [ ] Story marked ✅ Done in backlog

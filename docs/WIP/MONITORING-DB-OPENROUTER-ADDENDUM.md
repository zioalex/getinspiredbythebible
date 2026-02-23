# Performance Monitoring - Database & OpenRouter Specific Metrics

**Created:** 2026-02-23
**Status:** Research Addendum to Performance Monitoring Report

This document provides detailed instrumentation plans for PostgreSQL and OpenRouter
performance tracking, addressing the specific request to monitor DB and OpenRouter
response times closely.

---

## 📊 Database (PostgreSQL) Performance Monitoring

### Current State Analysis

**What We Have:**

- ✅ PostgreSQL Flexible Server on Azure (`B_Standard_B1ms`: 1 vCore, 2GB RAM)
- ✅ pgvector extension enabled for semantic search
- ✅ Connection pooling via SQLAlchemy `async_sessionmaker` with `NullPool`
- ✅ Basic timing logs in `chat/service.py` (`search_start` → `duration_seconds`)
- ❌ **NO pgvector indexes** (HNSW or IVFFlat) — all searches are full table scans
- ❌ No query-level tracing (which queries are slow, EXPLAIN plans)
- ❌ No connection pool metrics (active connections, waits, timeouts)

**What Azure Provides (Already Provisioned):**

- PostgreSQL server metrics → Log Analytics:
  - CPU percentage
  - Memory percentage
  - Storage percentage
  - Active connections
  - Failed connections
  - Network in/out
- Slow query log (needs to be enabled)
- Query performance insights (Azure portal feature)

---

### 1. PostgreSQL Query Performance — What to Track

#### Critical Metrics

| Metric | Why It Matters | Current Gap | How to Track |
|--------|----------------|-------------|--------------|
| **Semantic search duration** | Core feature — users wait for this | Logged but not visualized | Add OTel span + histogram metric |
| **pgvector scan vs. index usage** | Full scan = 200-2000ms, indexed = 10-50ms | No index exists! | `EXPLAIN ANALYZE` logs |
| **Query plan cache hit rate** | PostgreSQL query planner efficiency | Not tracked | Azure PostgreSQL metrics |
| **Connection pool exhaustion** | SQLAlchemy NullPool creates new connection per request — could hit `max_connections` | Not tracked | Add custom metric in `database.py` |
| **Verse embedding lookup time** | How long to fetch 31K verses × 1024 dims | Not tracked | OTel span in `repository.py` |
| **Transaction rollback rate** | Indicates conflicts or errors | Not tracked | Azure PostgreSQL metrics |

#### Recommended Instrumentation

##### 1.1 — Add OTel Spans to Repository Queries

```python
# api/scripture/repository.py
from opentelemetry import trace

tracer = trace.get_tracer("bible_app.scripture")

async def search_verses_semantic(
    self,
    query_embedding: list[float],
    limit: int = 5,
    similarity_threshold: float = 0.5,
    translation: str | None = None,
) -> list[tuple[Verse, float]]:
    with tracer.start_as_current_span("db.search_verses_semantic") as span:
        span.set_attribute("db.query.limit", limit)
        span.set_attribute("db.query.threshold", similarity_threshold)
        span.set_attribute("db.query.translation", translation or "all")
        span.set_attribute("db.operation", "pgvector_cosine_search")

        start_time = time.perf_counter()

        # Existing query logic...
        query = (
            select(
                Verse, (1 - Verse.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .where(Verse.embedding.isnot(None))
            .where((1 - Verse.embedding.cosine_distance(query_embedding)) >= similarity_threshold)
        )

        if translation:
            query = query.where(Verse.translation == translation)

        query = (
            query.order_by(Verse.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .options(selectinload(Verse.book))
        )

        result = await self.session.execute(query)
        rows = [(row.Verse, row.similarity) for row in result.all()]

        duration_ms = (time.perf_counter() - start_time) * 1000

        span.set_attribute("db.results.count", len(rows))
        span.set_attribute("db.duration_ms", duration_ms)

        # Also record as histogram metric
        db_search_histogram.record(duration_ms, {
            "operation": "semantic_search_verses",
            "translation": translation or "all"
        })

        logger.info(
            f"Semantic search completed: {len(rows)} results in {duration_ms:.2f}ms "
            f"(threshold={similarity_threshold})"
        )

        return rows
```

**Apply the same pattern to:**

- `search_passages_semantic()` — also uses pgvector
- `get_verse()` — indexed lookup (should be fast, baseline measurement)
- `get_chapter_verses()` — batch fetch (measures JOIN performance)

##### 1.2 — Add EXPLAIN ANALYZE Logging for Slow Queries

```python
# api/utils/db_profiler.py (NEW FILE)
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time
from utils.logging_config import get_logger

logger = get_logger("bible_app.db.profiler")

SLOW_QUERY_THRESHOLD_MS = 100  # Log queries slower than 100ms

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = (time.perf_counter() - conn.info["query_start_time"].pop()) * 1000

    if total > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            f"SLOW QUERY ({total:.2f}ms): {statement[:200]}...",
            extra={
                "duration_ms": total,
                "query": statement,
                "params": parameters,
            }
        )

        # Optionally run EXPLAIN ANALYZE for very slow queries
        if total > 500:  # Queries over 500ms get full analysis
            try:
                explain_query = f"EXPLAIN ANALYZE {statement}"
                result = cursor.execute(explain_query, parameters)
                plan = result.fetchall()
                logger.warning(f"Query plan:\n{plan}")
            except Exception as e:
                logger.debug(f"Could not EXPLAIN query: {e}")
```

Enable in `main.py`:

```python
if settings.debug or settings.enable_query_profiling:
    from utils.db_profiler import before_cursor_execute, after_cursor_execute
```

##### 1.3 — Track Connection Pool Metrics

```python
# api/utils/metrics.py (ADD TO EXISTING FILE)

# Database metrics
db_connections_active = meter.create_up_down_counter(
    "db.connections.active",
    description="Number of active database connections"
)

db_connections_idle = meter.create_up_down_counter(
    "db.connections.idle",
    description="Number of idle database connections in pool"
)

db_query_duration = meter.create_histogram(
    "db.query.duration_ms",
    description="Database query execution time in milliseconds"
)

db_search_duration = meter.create_histogram(
    "db.search.duration_ms",
    description="Semantic search duration in milliseconds"
)

db_embedding_fetch_duration = meter.create_histogram(
    "db.embedding_fetch.duration_ms",
    description="Time to fetch embeddings from database"
)
```

##### 1.4 — Enable Azure PostgreSQL Slow Query Log

Add to Terraform (`deployment/main.tf`):

```hcl
resource "azurerm_postgresql_flexible_server_configuration" "slow_query_log" {
  name      = "log_min_duration_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "100"  # Log queries slower than 100ms
}

resource "azurerm_postgresql_flexible_server_configuration" "log_statement" {
  name      = "log_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "all"  # Log all DDL/DML (or "mod" for writes only)
}

resource "azurerm_postgresql_flexible_server_configuration" "log_destination" {
  name      = "log_destination"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "stderr"  # Logs to Azure Monitor
}
```

Logs flow to Log Analytics → query with KQL:

```kql
AzureDiagnostics
| where Category == "PostgreSQLLogs"
| where Message contains "duration:"
| parse Message with * "duration: " Duration:double " ms" *
| where Duration > 100
| project TimeGenerated, Duration, Message
| order by Duration desc
```

---

### 2. pgvector Index Monitoring

**Critical Action: Add HNSW Indexes IMMEDIATELY** (mentioned in Quick Wins)

```sql
-- Run after data load, before production use
CREATE INDEX CONCURRENTLY idx_verses_embedding_hnsw
ON verses USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX CONCURRENTLY idx_passages_embedding_hnsw
ON passages USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Monitor index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE '%embedding%';
```

**Track Index Effectiveness:**

- `idx_scan` = number of times index was used
- If `idx_scan = 0` after 1000 semantic searches → index not being used (query planner issue)
- Add metric to dashboard: "pgvector index hit rate"

---

### 3. Database Dashboard Panels

Add to Azure Monitor Workbook:

```text
┌─────────────────────────────────────────────────────────────┐
│  DATABASE PERFORMANCE                                        │
├─────────────────────────────────────────────────────────────│
│  QUERY TIMING                                                │
│  ┌────────────────────────┐  ┌──────────────────────────┐   │
│  │ Semantic Search (ms)   │  │ Query Duration (ms)      │   │
│  │ p50: __  p95: __       │  │ [Histogram by query type]│   │
│  │ p99: __                │  └──────────────────────────┘   │
│  └────────────────────────┘                                  │
│                                                              │
│  CONNECTION POOL                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │ Active Conns   │  │ Max Conns      │  │ Failed Conns  │ │
│  │ [Gauge: __ ]   │  │ [Gauge: 100]   │  │ [Counter]     │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
│                                                              │
│  RESOURCE USAGE                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐│
│  │ CPU %           │  │ Memory %        │  │ Storage %   ││
│  │ [Line chart]    │  │ [Line chart]    │  │ [Gauge]     ││
│  └─────────────────┘  └─────────────────┘  └─────────────┘│
│                                                              │
│  INDEX USAGE                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ pgvector Index Scan Rate                             │   │
│  │ [Bar chart: verses HNSW scans / total queries]       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  SLOW QUERIES (>500ms in last hour)                          │
│  [Table: timestamp | duration | query_type | params]         │
└─────────────────────────────────────────────────────────────┘
```

**Key KQL Queries:**

```kql
// Semantic search performance over time
customMetrics
| where name == "db.search.duration_ms"
| extend operation = tostring(customDimensions.operation)
| summarize
    p50 = percentile(value, 50),
    p95 = percentile(value, 95),
    p99 = percentile(value, 99)
  by bin(timestamp, 5m), operation
| render timechart

// Database connection pool usage
customMetrics
| where name in ("db.connections.active", "db.connections.idle")
| summarize avg(value) by name, bin(timestamp, 1m)
| render timechart

// Slow query analysis
traces
| where message contains "SLOW QUERY"
| extend duration = todouble(customDimensions.duration_ms)
| where duration > 100
| project timestamp, duration, query = tostring(customDimensions.query)
| order by duration desc
| take 50
```

---

## 🌐 OpenRouter Performance Monitoring

### Current State Analysis — OpenRouter

**What We Have:**

- ✅ OpenRouter client with fallback logic (`providers/openrouter.py`)
- ✅ Rate limit detection and automatic fallback to alternative models
- ✅ Basic logging of model selection (`logger.info(f"OpenRouter response from model: {actual_model}")`)
- ✅ Token usage tracking in `LLMResponse` (`tokens_used`)
- ❌ **NO timing metrics** for LLM calls (time to first token, total duration)
- ❌ No separate tracking of queue time vs. generation time
- ❌ No model-specific performance comparison (is llama-3.3-70b slower than gemma-2-9b?)
- ❌ No tracking of fallback frequency (how often does primary model fail?)

**What OpenRouter Provides (Via API Headers):**

- `X-RateLimit-Limit-Requests`: Request limit per time window
- `X-RateLimit-Remaining-Requests`: Remaining requests
- `X-RateLimit-Reset-Requests`: Timestamp when limit resets
- Response includes `response.model` (actual model used, may differ from requested due to auto-router)
- Response includes `response.usage` (prompt tokens, completion tokens)

---

### 1. OpenRouter Response Time — What to Track

#### Critical Metrics — OpenRouter

| Metric | Why It Matters | Current Gap | How to Track |
|--------|----------------|-------------|--------------|
| **Time to First Token (TTFT)** | User perceived latency in streaming mode | Not tracked | Measure time from request start to first chunk yielded |
| **Total LLM duration** | End-to-end LLM call time | Logged but not as metric | OTel span + histogram |
| **Queue time** | Free-tier models queue 3-10s during peak | Not tracked | Infer from TTFT (high TTFT = queued) |
| **Tokens per second** | Generation speed (varies by model) | Not tracked | `completion_tokens / generation_duration` |
| **Model fallback rate** | How often primary fails (429/503) | Not tracked | Counter for fallback attempts |
| **Rate limit exhaustion** | When we hit API limits | Not tracked | Parse `X-RateLimit-*` headers |
| **Model-specific performance** | Compare llama-3.3 vs gemma-2 | Not tracked | Tag metrics by `model` attribute |

#### Recommended Instrumentation — OpenRouter

##### 2.1 — Add OTel Spans & Metrics to OpenRouter Provider

```python
# api/providers/openrouter.py
from opentelemetry import trace
import time

tracer = trace.get_tracer("bible_app.llm")

# Add to utils/metrics.py
llm_duration_total = meter.create_histogram(
    "llm.duration_ms",
    description="Total LLM call duration in milliseconds"
)

llm_ttft = meter.create_histogram(
    "llm.time_to_first_token_ms",
    description="Time to first token in streaming responses"
)

llm_tokens_per_second = meter.create_histogram(
    "llm.tokens_per_second",
    description="Generation speed (completion tokens / generation time)"
)

llm_tokens_total = meter.create_counter(
    "llm.tokens.total",
    description="Total tokens consumed (prompt + completion)"
)

llm_fallback_attempts = meter.create_counter(
    "llm.fallback.attempts",
    description="Number of times fallback models were attempted"
)

llm_rate_limit_hits = meter.create_counter(
    "llm.rate_limit.hits",
    description="Number of rate limit errors encountered"
)

async def chat(
    self,
    messages: list[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    **kwargs,
) -> LLMResponse:
    with tracer.start_as_current_span("llm.chat") as span:
        span.set_attribute("llm.provider", self.provider_name)
        span.set_attribute("llm.model", self.model)
        span.set_attribute("llm.temperature", temperature)
        span.set_attribute("llm.max_tokens", max_tokens)

        start_time = time.perf_counter()

        try:
            # Existing request logic...
            response = await self._client.chat.completions.create(...)

            duration_ms = (time.perf_counter() - start_time) * 1000

            actual_model = response.model if response.model else self.model
            tokens_used = (
                (response.usage.prompt_tokens if response.usage else 0)
                + (response.usage.completion_tokens if response.usage else 0)
            )
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            # Record metrics
            span.set_attribute("llm.model.actual", actual_model)
            span.set_attribute("llm.tokens.total", tokens_used)
            span.set_attribute("llm.tokens.prompt", response.usage.prompt_tokens if response.usage else 0)
            span.set_attribute("llm.tokens.completion", completion_tokens)
            span.set_attribute("llm.duration_ms", duration_ms)

            llm_duration_total.record(duration_ms, {
                "provider": self.provider_name,
                "model": actual_model,
                "operation": "chat"
            })

            llm_tokens_total.add(tokens_used, {
                "provider": self.provider_name,
                "model": actual_model
            })

            # Calculate tokens per second
            if duration_ms > 0 and completion_tokens > 0:
                tokens_per_sec = (completion_tokens / duration_ms) * 1000
                llm_tokens_per_second.record(tokens_per_sec, {
                    "provider": self.provider_name,
                    "model": actual_model
                })
                span.set_attribute("llm.tokens_per_second", tokens_per_sec)

            logger.info(
                f"LLM response: model={actual_model}, "
                f"tokens={tokens_used}, duration={duration_ms:.2f}ms, "
                f"tps={tokens_per_sec:.1f if duration_ms > 0 else 0}"
            )

            return LLMResponse(...)

        except (RateLimitError, APIStatusError) as e:
            llm_rate_limit_hits.add(1, {"provider": self.provider_name})
            span.set_attribute("llm.error", "rate_limit")

            if self._should_try_fallback(e) and self.fallback_models:
                llm_fallback_attempts.add(1, {
                    "provider": self.provider_name,
                    "primary_model": self.model
                })
                # Existing fallback logic...
            raise
```

##### 2.2 — Add TTFT Tracking for Streaming

```python
async def chat_stream(
    self,
    messages: list[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    **kwargs,
) -> AsyncIterator[str]:
    with tracer.start_as_current_span("llm.chat_stream") as span:
        span.set_attribute("llm.provider", self.provider_name)
        span.set_attribute("llm.model", self.model)

        start_time = time.perf_counter()
        first_token_time = None
        token_count = 0

        try:
            stream = await self._client.chat.completions.create(...)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token_count += 1

                    # Track time to first token
                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                        ttft_ms = (first_token_time - start_time) * 1000

                        span.set_attribute("llm.ttft_ms", ttft_ms)
                        llm_ttft.record(ttft_ms, {
                            "provider": self.provider_name,
                            "model": self.model
                        })

                        logger.info(f"First token received in {ttft_ms:.2f}ms")

                    yield chunk.choices[0].delta.content

            # After stream completes
            total_duration_ms = (time.perf_counter() - start_time) * 1000
            generation_duration_ms = (time.perf_counter() - first_token_time) * 1000 if first_token_time else 0

            span.set_attribute("llm.duration_ms", total_duration_ms)
            span.set_attribute("llm.generation_duration_ms", generation_duration_ms)
            span.set_attribute("llm.tokens.completion", token_count)

            llm_duration_total.record(total_duration_ms, {
                "provider": self.provider_name,
                "model": self.model,
                "operation": "chat_stream"
            })

            if generation_duration_ms > 0:
                tokens_per_sec = (token_count / generation_duration_ms) * 1000
                llm_tokens_per_second.record(tokens_per_sec, {
                    "provider": self.provider_name,
                    "model": self.model
                })

        except Exception as e:
            span.record_exception(e)
            raise
```

##### 2.3 — Parse OpenRouter Rate Limit Headers

```python
# After API response
if hasattr(response, "headers"):
    rate_limit_remaining = response.headers.get("X-RateLimit-Remaining-Requests")
    rate_limit_limit = response.headers.get("X-RateLimit-Limit-Requests")

    if rate_limit_remaining and rate_limit_limit:
        span.set_attribute("llm.rate_limit.remaining", int(rate_limit_remaining))
        span.set_attribute("llm.rate_limit.limit", int(rate_limit_limit))

        # Record as gauge metric
        llm_rate_limit_remaining.set(int(rate_limit_remaining), {
            "provider": self.provider_name
        })

        # Alert if getting close to limit
        if int(rate_limit_remaining) < int(rate_limit_limit) * 0.1:  # <10% remaining
            logger.warning(
                f"OpenRouter rate limit low: {rate_limit_remaining}/{rate_limit_limit} remaining"
            )
```

---

### 2. OpenRouter Dashboard Panels

Add to Azure Monitor Workbook:

```text
┌─────────────────────────────────────────────────────────────┐
│  LLM (OpenRouter) PERFORMANCE                                │
├─────────────────────────────────────────────────────────────│
│  RESPONSE TIMING                                             │
│  ┌────────────────────────┐  ┌──────────────────────────┐   │
│  │ Time to First Token    │  │ Total LLM Duration (ms)  │   │
│  │ p50: __  p95: __       │  │ p50: __  p95: __  p99:__ │   │
│  │ [Line chart by model]  │  │ [Histogram by model]     │   │
│  └────────────────────────┘  └──────────────────────────┘   │
│                                                              │
│  GENERATION SPEED                                            │
│  ┌────────────────────────┐  ┌──────────────────────────┐   │
│  │ Tokens Per Second      │  │ Tokens Consumed (total)  │   │
│  │ avg: __ (by model)     │  │ [Counter + line chart]   │   │
│  └────────────────────────┘  └──────────────────────────┘   │
│                                                              │
│  MODEL USAGE                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Requests by Model                                    │   │
│  │ [Pie chart: llama-3.3-70b-free vs gemma-2-9b vs...]  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  RELIABILITY                                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │ Fallback Rate  │  │ Rate Limits    │  │ API Errors    │ │
│  │ [Counter]      │  │ [Gauge/Chart]  │  │ [Counter]     │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
│                                                              │
│  MODEL PERFORMANCE COMPARISON                                │
│  [Table: model | avg_duration | p95_duration | tokens/sec]  │
└─────────────────────────────────────────────────────────────┘
```

**Key KQL Queries:**

```kql
// Time to first token by model
customMetrics
| where name == "llm.time_to_first_token_ms"
| extend model = tostring(customDimensions.model)
| summarize
    p50 = percentile(value, 50),
    p95 = percentile(value, 95)
  by bin(timestamp, 5m), model
| render timechart

// Tokens per second by model
customMetrics
| where name == "llm.tokens_per_second"
| extend model = tostring(customDimensions.model)
| summarize avg_tps = avg(value) by model
| render barchart

// Fallback frequency
customMetrics
| where name == "llm.fallback.attempts"
| summarize fallback_count = sum(value) by bin(timestamp, 1h)
| render timechart

// Model usage distribution
customMetrics
| where name == "llm.duration_ms"
| extend model = tostring(customDimensions.model)
| summarize request_count = count() by model
| render piechart

// LLM performance comparison table
customMetrics
| where name == "llm.duration_ms"
| extend model = tostring(customDimensions.model)
| summarize
    avg_duration_ms = avg(value),
    p95_duration_ms = percentile(value, 95),
    request_count = count()
  by model
| join kind=leftouter (
    customMetrics
    | where name == "llm.tokens_per_second"
    | extend model = tostring(customDimensions.model)
    | summarize avg_tps = avg(value) by model
  ) on model
| project model, avg_duration_ms, p95_duration_ms, avg_tps, request_count
| order by request_count desc
```

---

## 🎯 Combined Monitoring: End-to-End Request Flow

Track the full journey of a chat request:

```text
User sends message
  ↓ [Frontend: page.tsx]
  ↓ POST /api/v1/chat
  ↓ [Backend: routes/chat.py]
  ↓ ChatService.chat()
    ↓ [1] _detect_intent() → LLM call (intent classification)
        → SPAN: llm.chat (provider=openrouter, model=llama-3.3, duration=1200ms)
    ↓ [2] EmbeddingProvider.embed() → Generate query embedding
        → SPAN: embedding.generate (provider=ollama, duration=50ms)
    ↓ [3] ScriptureSearchService.search()
        ↓ [3a] search_verses_semantic() → pgvector query
            → SPAN: db.search_verses_semantic (duration=180ms, results=5)
        ↓ [3b] search_passages_semantic() → pgvector query
            → SPAN: db.search_passages_semantic (duration=140ms, results=3)
    ↓ [4] LLMProvider.chat_stream() → Main LLM response
        → SPAN: llm.chat_stream (ttft=2800ms, total_duration=8500ms, tokens=450)
  ↓ [Backend: routes/chat.py] Return streaming response
  ↓ [Frontend: page.tsx] Render streamed response
```

**Add Correlation ID to link all spans** (BITB-008):

```python
# api/middleware/correlation.py
from opentelemetry import trace
from opentelemetry.trace import set_span_in_context

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))

        # Set in OTel context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("http.request") as span:
            span.set_attribute("http.request_id", request_id)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.path", request.url.path)

            # Add to response header
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            return response
```

In Application Insights, all spans for a single request will be grouped under the same
`operation_Id` → distributed trace view.

---

## 📋 Updated BITB-013 Acceptance Criteria

Add to the user story:

```markdown
**Database-Specific Metrics:**
- [ ] OTel spans added to `search_verses_semantic()` and `search_passages_semantic()`
- [ ] Histogram metric `db.search.duration_ms` tracking semantic search performance
- [ ] Histogram metric `db.query.duration_ms` tracking all query types
- [ ] Counter metric `db.connections.active` tracking connection pool usage
- [ ] PostgreSQL slow query log enabled (log_min_duration_statement = 100ms)
- [ ] HNSW indexes created on verses.embedding and passages.embedding
- [ ] Index usage tracked via `pg_stat_user_indexes` queries in dashboard

**OpenRouter-Specific Metrics:**
- [ ] Histogram metric `llm.time_to_first_token_ms` (TTFT) for streaming responses
- [ ] Histogram metric `llm.duration_ms` for total LLM call duration
- [ ] Histogram metric `llm.tokens_per_second` for generation speed
- [ ] Counter metric `llm.tokens.total` for token consumption tracking
- [ ] Counter metric `llm.fallback.attempts` for model fallback frequency
- [ ] Counter metric `llm.rate_limit.hits` for rate limit errors
- [ ] Gauge metric `llm.rate_limit.remaining` parsed from API response headers
- [ ] OTel spans for `llm.chat` and `llm.chat_stream` with model/provider attributes

**End-to-End Tracing:**
- [ ] Correlation ID middleware added (X-Request-ID header propagation)
- [ ] All OTel spans linked via operation_Id for distributed tracing
- [ ] Application Insights distributed trace view shows full request flow:
      Frontend → Backend → DB → LLM → Backend → Frontend
```

---

## 📊 Estimated Performance Impact After Implementation

| Metric | Before | After (Expected) | Improvement |
|--------|--------|------------------|-------------|
| **Semantic search (pgvector)** | 200-2000ms (full scan) | 10-50ms (HNSW index) | **40-200x faster** |
| **LLM time to first token** | Unknown (not tracked) | 1-3s (free tier), <1s (paid) | Visibility gain |
| **Total response time (streaming)** | 10-30s (perceived) | 1-3s perceived (TTFT), 8-15s total | **10x UX improvement** |
| **Database CPU usage** | 60-80% during search | <20% during search | **4x efficiency** |
| **Connection pool exhaustion** | Unknown (not tracked) | Alerts before hitting max | Proactive prevention |
| **Model fallback transparency** | Silent failures | Logged + alerted | Operational visibility |

---

## 🚀 Implementation Priority

**Phase 1 (Immediate — < 1 day):**

1. ✅ Add pgvector HNSW indexes (biggest DB perf win)
2. ✅ Add OTel spans to `search_verses_semantic()` / `search_passages_semantic()`
3. ✅ Add OTel spans to `OpenRouterProvider.chat()` / `chat_stream()` with TTFT tracking
4. ✅ Enable PostgreSQL slow query log in Terraform

**Phase 2 (This Week — 2-3 days):**

1. Add histogram metrics: `db.search.duration_ms`, `llm.duration_ms`, `llm.ttft_ms`
2. Add counter metrics: `llm.tokens.total`, `llm.fallback.attempts`
3. Add correlation ID middleware (BITB-008)
4. Build DB + OpenRouter panels in Azure Monitor Workbook

**Phase 3 (Next Sprint — 1-2 days):**

1. Add rate limit header parsing to OpenRouter provider
2. Add connection pool metrics to database.py
3. Add EXPLAIN ANALYZE logging for slow queries (>500ms)
4. Set up alerts: slow DB queries, LLM timeouts, rate limit warnings

---

**Total Additional Development Time:** +2-3 days (on top of base monitoring effort)

This gives you **deep visibility** into the two most critical performance bottlenecks:
database semantic search and OpenRouter LLM response times. 🎯

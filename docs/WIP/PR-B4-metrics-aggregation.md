# PR B4: Metrics Aggregation & Export

**Status:** In Progress
**PR URL:** TBD
**Started:** 2026-02-24
**Base Branch:** `feat/llm-performance-instrumentation` (B1+B2+B3)

## Summary

Add database performance metrics (histograms/counters) to complement the LLM metrics built in
PR B3. This enables comprehensive monitoring of both LLM and DB performance in Azure Monitor.

## What Was Already Built

- **PR B1** (✅ merged to B3 branch): Correlation ID middleware
- **PR B2** (✅ merged to B3 branch): DB performance spans in `repository.py`
- **PR B3** (✅ on branch): LLM performance spans + metrics in `telemetry.py` + providers

## What This PR Adds

### 1. DB Metrics Definitions (`api/utils/metrics.py`)

Four new metric instruments added to the existing `bible_app` meter:

- `db_search_duration_histogram` - Semantic search query duration (ms)
- `db_query_duration_histogram` - General DB query duration (ms)
- `db_connections_active_gauge` - Active DB connections (UpDownCounter)
- `db_slow_query_counter` - Count of queries exceeding threshold

### 2. Metrics Recording (`api/scripture/repository.py`)

Updated `_record_duration()` helper to record metrics:

- Search operations → `db_search_duration_histogram` with `{operation, translation}` dimensions
- Other operations → `db_query_duration_histogram` with `{operation}` dimension
- Slow queries → increment `db_slow_query_counter` with `{operation}` dimension

### 3. Testing

**`test_metrics.py`**: Added `TestDBMetrics` class with 5 tests:

- Verify all 4 DB metrics are defined
- Test search duration histogram recording
- Test query duration histogram recording
- Test slow query counter increment
- Test connections gauge add/subtract

**`test_instrumentation.py`**: Added `TestDBMetricsRecording` class with 5 tests:

- Verify `search_verses_semantic()` records metric
- Verify search operations route to search histogram
- Verify non-search operations route to query histogram
- Verify slow query counter incremented when threshold exceeded
- Verify counter not incremented for fast queries

## Implementation Notes

### Design Decisions

1. **Manual Recording Pattern**: Follows the same pattern as LLM metrics (manual `record()`
   calls), not using SpanProcessor auto-aggregation
2. **Operation-Based Routing**: Uses `"search" in operation` to determine which histogram to use
3. **Dimension Strategy**:
   - Search operations include `translation` dimension (to track per-translation performance)
   - Non-search operations only include `operation` dimension
   - Slow query counter only includes `operation` dimension

### Connections Gauge Note

The `db_connections_active_gauge` is defined but NOT yet implemented in repository.py.
To track actual connections, we would need SQLAlchemy pool event hooks:

```python
from sqlalchemy import event
from sqlalchemy.pool import Pool

@event.listens_for(Pool, "connect")
def on_connect(dbapi_conn, conn_record):
    db_connections_active_gauge.add(1)

@event.listens_for(Pool, "close")
def on_close(dbapi_conn, conn_record):
    db_connections_active_gauge.add(-1)
```

This is out of scope for B4 and tracked as future enhancement.

## Azure Monitor Integration

### How Metrics Appear

- **Table**: `customMetrics` (NOT `dependencies` - that's for spans)
- **Exporter**: Already configured via `configure_azure_monitor()` in `main.py`
- **Pipeline**: OpenTelemetry SDK → OTLP → Azure Monitor

### KQL Queries for Monitoring

```kql
// ══════════════════════════════════════════════════════════════════════════
// LLM Metrics (from PR B3)
// ══════════════════════════════════════════════════════════════════════════

// Average LLM duration by model
customMetrics
| where name == "llm.duration_ms"
| summarize avg(value) by tostring(customDimensions.model)

// P95 Time-to-First-Token by provider
customMetrics
| where name == "llm.ttft_ms"
| summarize p95=percentile(value, 95) by tostring(customDimensions.provider)

// Token throughput (tokens/sec) distribution
customMetrics
| where name == "llm.tokens_per_second"
| summarize avg(value), p50=percentile(value, 50), p95=percentile(value, 95)

// Total tokens consumed over time
customMetrics
| where name == "llm.tokens.total"
| summarize sum(value) by bin(timestamp, 1h)
| render timechart

// Fallback attempts by provider/model
customMetrics
| where name == "llm.fallback.attempts"
| summarize sum(value) by tostring(customDimensions.provider), tostring(customDimensions.model)

// Rate limit hits over time
customMetrics
| where name == "llm.rate_limit.hits"
| summarize sum(value) by bin(timestamp, 1h), tostring(customDimensions.model)
| render timechart

// ══════════════════════════════════════════════════════════════════════════
// DB Metrics (from PR B4 - this PR)
// ══════════════════════════════════════════════════════════════════════════

// Database search duration trends (P50, P95, P99)
customMetrics
| where name == "db.search.duration_ms"
| summarize
    p50=percentile(value, 50),
    p95=percentile(value, 95),
    p99=percentile(value, 99)
    by bin(timestamp, 5m), tostring(customDimensions.operation), tostring(customDimensions.translation)
| render timechart

// Average search duration by translation
customMetrics
| where name == "db.search.duration_ms"
| summarize avg(value) by tostring(customDimensions.translation)
| render barchart

// Average query duration by operation type
customMetrics
| where name == "db.query.duration_ms"
| summarize avg(value), count() by tostring(customDimensions.operation)

// Slow query count over time
customMetrics
| where name == "db.slow_query.count"
| summarize sum(value) by bin(timestamp, 1h), tostring(customDimensions.operation)
| render timechart

// Slow query hot spots (which operations are slowest?)
customMetrics
| where name == "db.slow_query.count"
| summarize total_slow_queries=sum(value) by tostring(customDimensions.operation)
| order by total_slow_queries desc

// Active DB connections (if implemented)
customMetrics
| where name == "db.connections.active"
| summarize avg(value), max(value) by bin(timestamp, 1m)
| render timechart

// ══════════════════════════════════════════════════════════════════════════
// Combined Analysis
// ══════════════════════════════════════════════════════════════════════════

// Total latency breakdown: LLM vs DB
let llm_latency = customMetrics
| where name == "llm.duration_ms"
| summarize avg_llm_ms=avg(value) by bin(timestamp, 5m);
let db_latency = customMetrics
| where name == "db.search.duration_ms"
| summarize avg_db_ms=avg(value) by bin(timestamp, 5m);
llm_latency
| join kind=inner db_latency on timestamp
| project timestamp, avg_llm_ms, avg_db_ms
| render timechart

// Correlate slow queries with LLM fallbacks
let slow_queries = customMetrics
| where name == "db.slow_query.count"
| summarize slow_query_count=sum(value) by bin(timestamp, 1h);
let fallbacks = customMetrics
| where name == "llm.fallback.attempts"
| summarize fallback_count=sum(value) by bin(timestamp, 1h);
slow_queries
| join kind=fullouter fallbacks on timestamp
| project timestamp, slow_query_count, fallback_count
| render timechart
```

## Tasks

- [x] Add DB metrics to `api/utils/metrics.py`
- [x] Update `_record_duration()` in `api/scripture/repository.py` to record metrics
- [x] Extend `api/tests/test_metrics.py` with `TestDBMetrics` class
- [x] Extend `api/tests/test_instrumentation.py` with `TestDBMetricsRecording` class
- [x] Create tracking document with KQL queries
- [ ] Run `make test-backend` to verify all tests pass
- [ ] Run `make pre-commit` before pushing
- [ ] Create PR against `feat/llm-performance-instrumentation` base branch
- [ ] Verify PR is focused and human-digestible

## Progress Log

### 2026-02-24

**Implementation Complete**:

- ✅ Added 4 DB metric instruments to `utils/metrics.py`
- ✅ Updated `_record_duration()` to record metrics with proper routing logic
- ✅ Added `TestDBMetrics` class with 5 tests
- ✅ Added `TestDBMetricsRecording` class with 5 tests
- ✅ Created tracking document with comprehensive KQL queries

**Next Steps**:

- Run backend tests to verify implementation
- Run pre-commit checks
- Create PR

## Notes

### Metrics Export Flow

```text
ScriptureRepository._record_duration()
    ↓
db_*_histogram.record() / db_*_counter.add()
    ↓
OpenTelemetry Metrics SDK
    ↓
Azure Monitor OTLP Exporter (configured in main.py)
    ↓
Azure Application Insights (customMetrics table)
```

### Testing Strategy

- **Unit tests**: Mock metric instruments, verify `record()` and `add()` calls
- **Integration tests**: Verify repository methods trigger metrics recording
- **No mocking of OTel SDK**: Trust the SDK to handle export (already tested in B3)

### Future Enhancements

1. **Connection Pool Metrics**: Implement SQLAlchemy event hooks for `db_connections_active_gauge`
2. **Per-Query Attributes**: Add query plan hash or table name dimensions
3. **Cache Hit Rate**: Track pgvector index cache performance
4. **Batch Operations**: Metrics for bulk insert/update operations

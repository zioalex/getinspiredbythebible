# PR #B2: Database Performance Instrumentation (OpenTelemetry spans + slow query logging)

**Status:** In Progress
**Started:** Feb 24, 2026
**Base Branch:** `feat/correlation-id-middleware` (PR B1)

## Summary

Implements comprehensive database performance monitoring by adding OpenTelemetry tracing spans
and slow query logging to all key database operations in the ScriptureRepository.

## Changes Made

### 1. Configuration (`api/config.py`)

- Added `slow_query_threshold_ms: int = 100` setting under "Performance Monitoring" section
- Configurable threshold for slow query detection (default: 100ms)

### 2. Telemetry Module (`api/utils/telemetry.py` - NEW)

- Created OTel tracer for database/scripture operations
- Uses instrumentation scope `bible_app.scripture`
- Automatically integrates with Azure Monitor when configured
- Gracefully no-ops when no exporter is configured

### 3. Repository Instrumentation (`api/scripture/repository.py`)

Added imports:

- `time` for perf_counter measurements
- `Span` from opentelemetry.trace
- `REQUEST_ID_CTX_VAR` for correlation
- `get_logger` for structured logging
- `tracer` from new telemetry module
- `settings` for threshold configuration

Added helper functions:

- `_set_common_span_attrs()`: Sets standard span attributes (operation, translation, request_id)
- `_record_duration()`: Records duration on span and emits slow query warning if threshold exceeded

Instrumented 4 methods:

- `search_verses_semantic()`: Vector similarity search with pgvector
- `search_passages_semantic()`: Passage-level semantic search
- `get_verse()`: Single verse lookup
- `get_chapter_verses()`: Full chapter retrieval

Each instrumented method:

- Creates a named span (e.g., `db.search_verses_semantic`)
- Sets common attributes (operation, translation, request_id)
- Sets method-specific attributes (e.g., `similarity_threshold`)
- Times the database execution
- Records duration and result count on the span
- Emits structured warning log if query exceeds threshold

### 4. Tests (`api/tests/test_instrumentation.py` - NEW)

Created comprehensive test suite with 4 test classes:

**TestTelemetryModule:**

- Verifies tracer is initialized correctly
- Validates tracer uses correct instrumentation scope

**TestSpanAttributes:**

- Tests `_set_common_span_attrs()` with/without translation
- Tests `_set_common_span_attrs()` with/without request_id
- Tests `_record_duration()` sets duration and count attributes
- Tests slow query logging triggers when threshold exceeded
- Tests fast queries don't trigger slow query log

**TestSlowQueryLogging:**

- Verifies slow query logs include operation name
- Verifies slow query logs include correlation ID

**TestRepositorySpans:**

- Verifies each of 4 methods creates correctly named span
- Verifies similarity_threshold attribute is set on semantic search spans

### 5. Documentation

- Updated `api/.env.example` with `SLOW_QUERY_THRESHOLD_MS` setting

## Span Attributes

All spans include:

- `db.operation`: Operation name (e.g., "semantic_search_verses", "get_verse")
- `db.translation`: Translation code or "all"
- `db.duration_ms`: Query duration in milliseconds (rounded to 2 decimals)
- `db.results.count`: Number of results returned
- `request_id`: Correlation ID from context (if present)

Semantic search spans also include:

- `db.similarity_threshold`: Minimum similarity score

## Azure Monitor Integration

When `APPLICATIONINSIGHTS_CONNECTION_STRING` is set:

- All spans are automatically exported to Application Insights
- Spans appear in the `dependencies` table with type `InProc`
- Can query slow queries using KQL (see below)

## KQL Query Examples

```kql
// Find slow database queries
dependencies
| where name startswith "db."
| where duration > 100
| project timestamp, name, duration, customDimensions
| order by duration desc

// Semantic search performance over time
dependencies
| where name == "db.search_verses_semantic"
| summarize avg(duration), percentile(duration, 95), count() by bin(timestamp, 5m)
| order by timestamp desc
```

## Design Decisions

1. **Helper Functions**: Extracted `_set_common_span_attrs()` and `_record_duration()` to avoid
   code duplication across 4 instrumented methods.

2. **Timing Scope**: Query construction happens outside the span context manager to exclude
   SQLAlchemy query building overhead. Only the actual database execute call is timed.

3. **Synchronous Context Manager**: Used `with tracer.start_as_current_span()` (synchronous)
   which is compatible with async code. The span tracks wall-clock time from entering to exiting
   the block, including the `await` call.

4. **No Transitive Dependencies**: Did not add `opentelemetry-api` or `opentelemetry-sdk` to
   requirements.txt because they're already pulled in by `azure-monitor-opentelemetry==1.8.6`.

5. **Correlation ID Integration**: Uses `REQUEST_ID_CTX_VAR` from PR B1 (correlation-id-middleware)
   to link spans with request logs.

6. **Slow Query Threshold**: Made configurable via env var with sensible 100ms default.
   Different applications may need different thresholds.

## Tasks

- [x] Add `slow_query_threshold_ms` to config.py
- [x] Create `api/utils/telemetry.py`
- [x] Instrument `search_verses_semantic()`
- [x] Instrument `search_passages_semantic()`
- [x] Instrument `get_verse()`
- [x] Instrument `get_chapter_verses()`
- [x] Create comprehensive test suite
- [x] Update `.env.example`
- [x] Create WIP tracking document
- [ ] Run `make pre-commit`
- [ ] Run `make test-backend`
- [ ] Push branch and create PR
- [ ] Verify PR targets correct base branch

## Notes

- This PR depends on PR B1 (`feat/correlation-id-middleware`) for `REQUEST_ID_CTX_VAR`
- The PR should target `feat/correlation-id-middleware` as the base branch
- Once both PRs are merged to main, the instrumentation will be fully active

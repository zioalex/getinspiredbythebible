# How to Read Chat Stage Timings

Every `/chat` request emits a per-stage latency breakdown so you can see exactly
where time goes in the pipeline (intent detection, scripture retrieval, LLM
generation, grounding, …). This is the baseline used to validate latency work:
each optimization is only "done" once the stage it targets drops here.

See also: [`api/chat/service.py`](../api/chat/service.py) (the orchestration that
records each stage) and [`api/utils/timing.py`](../api/utils/timing.py)
(`record_stage`, the `@timed_stage` decorator, `format_timings`, and the
`chat.stage.duration_ms` histogram).

## What gets recorded

Each request writes its stages into two places (both best-effort — instrumentation
never breaks a chat response):

1. A single structured log line, `chat_stage_timings`, emitted once per request.
2. The `chat.stage.duration_ms` OpenTelemetry **histogram**, tagged with
   `stage`, `stream` (bool), and `provider`.

### Stages

| Stage             | What it measures                                                        |
| ----------------- | ---------------------------------------------------------------------- |
| `content_safety`  | Pre-LLM safety check (0 when the safety filter is disabled).            |
| `intent`          | Intent-classification LLM round-trip.                                   |
| `query_expansion` | Query-expansion LLM call + its embedding (only when expansion is on).   |
| `retrieval`       | Full scripture search (includes `query_expansion` as a sub-stage).     |
| `ttft`            | Time to first streamed token — what the user actually waits (stream).   |
| `generation`      | LLM answer generation (token stream for `chat_stream`).                 |
| `grounding`       | Resolving cited verses + rewriting fabricated/mismatched quotes.        |
| `total`           | Whole request, end to end.                                              |

All values are milliseconds. `ttft` is stream-only; the `stream` field
distinguishes `chat()` (`stream=false`) from `chat_stream()` (`stream=true`).

## Where to find it

The backend is deployed as an Azure Container App (`bible-app-backend`, resource
group `bible-app-rg`); telemetry flows to Application Insights
(`bible-app-insights`).

### 1. Plain logs / stdout (quickest)

The log line carries the breakdown in its **message text**, so it is readable
straight from the container logs:

```
chat_stage_timings content_safety=0.0 intent=3100.5 query_expansion=2900.3 retrieval=8200.1 ttft=14210.7 generation=4300.2 grounding=180.4 total=18650.9
```

```bash
az containerapp logs show \
  --name bible-app-backend \
  --resource-group bible-app-rg \
  --follow \
  | grep chat_stage_timings
```

Locally (dev), the same line prints to stdout when you run the API
(`uvicorn main:app`). Set `LOG_LEVEL=INFO` (the default) so it is emitted.

### 2. Application Insights — structured `traces` (best for querying)

The `extra` fields are exported as `customDimensions`, so you can filter and
extract them. Portal → Application Insights `bible-app-insights` → **Logs**:

```kusto
traces
| where message startswith "chat_stage_timings"
| order by timestamp desc
| project timestamp,
          stream      = tostring(customDimensions.stream),
          timings_ms  = tostring(customDimensions.timings_ms)
| take 20
```

Or from the CLI:

```bash
az monitor app-insights query \
  --app bible-app-insights --resource-group bible-app-rg \
  --analytics-query "traces | where message startswith 'chat_stage_timings' | order by timestamp desc | project timestamp, customDimensions | take 5"
```

### 3. Application Insights — the histogram (best for "which stage dominates")

The metric form aggregates across many requests, so you can rank stages by
percentile instead of reading individual lines:

```kusto
customMetrics
| where name == "chat.stage.duration_ms"
| extend stage  = tostring(customDimensions.stage),
         stream = tostring(customDimensions.stream)
| summarize p50 = percentile(value, 50),
            p95 = percentile(value, 95),
            n   = count()
        by stage
| order by p95 desc
```

To split streaming vs non-streaming, add `, stream` to the `by` clause.

## Tips

- **Reproduce a slow query.** The known-slow case is a non-English topical
  question (e.g. German, translation `schlachter`); these exercise intent +
  expansion + retrieval on the full pipeline.
- **`total` ≈ sum of stages** for the non-stream path; on the stream path,
  `ttft` is the number users feel, and `generation` runs after it.
- **A `0.0` stage** usually means that stage is disabled by a feature flag
  (e.g. `content_safety` when `CONTENT_SAFETY_ENABLED=false`, or
  `query_expansion` when `QUERY_EXPANSION_ENABLED=false`).

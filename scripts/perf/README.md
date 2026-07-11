# Performance tests

Ad-hoc load/performance scripts for the Vox Quieta backend. These run **against a
deployed API** (or a local one) — they are not part of the unit-test suite.

## `search_concurrency_test.py` — scripture search concurrency / degradation

Finds the concurrency at which scripture vector search starts to degrade, and
contrasts **same-language** vs **multi-language** load. This validates Phase 2
Step B (per-translation partial HNSW indexes in migration `007`, the `B2s` SKU,
and the connection pool): if 4 GB RAM is too small, `multi` mode degrades far
earlier than `same` because the per-translation partial indexes thrash the buffer
cache.

### Why this endpoint

It hits `GET /api/v1/scripture/search`, which is:

- **public** — no Turnstile/auth token needed,
- **not rate-limited** — rate limiting is applied only to chat routes
  (`require_rate_limit` in `api/routes/chat.py`), so it won't throttle the test,
- **LLM-free** — it embeds the query and runs the verses/passages vector SQL, so
  the measured latency reflects embedding + DB, not paid LLM generation.

### Workload modes

| mode    | behaviour                                                                 | exposes |
|---------|--------------------------------------------------------------------------|---------|
| `same`  | every request uses one translation (rotates the query pool)              | single partial index, best cache |
| `multi` | requests round-robin across translations (language-matched queries)      | many partial indexes competing for cache (thrash) |
| `both`  | runs `same` then `multi`                                                  | the gap between them = cache pressure |

### Usage

```bash
pip install httpx   # already in api/requirements.txt

python scripts/perf/search_concurrency_test.py \
    --base-url https://api.voxquieta.org \
    --mode both \
    --concurrency 1,2,4,8,16,32,64 \
    --requests-per-level 200
```

Common flags:

- `--base-url` / `BACKEND_URL` env — API base URL (required).
- `--mode {same,multi,both}` — workload shape (default `both`).
- `--concurrency 1,2,4,8,...` — concurrency levels to ramp through.
- `--requests-per-level N` — requests sent at each level (default 200).
- `--translation kjv` — fix the translation for `same` mode.
- `--translations web,kjv,schlachter,...` — pool for `multi` mode.
- `--max-passages 0` — isolate the verses partial index (skip passages).
- `--degradation-factor 2.0` — flag a level when p95 ≥ this × the baseline p95.
- `--max-error-rate 0.05` — flag a level when the error rate exceeds this.
- `--out results.json` — JSON results path (default `search_perf_results.json`).

### Output

Per concurrency level: requests, ok/err, p50/p95/p99/max latency (ms), throughput
(req/s), and p95 vs the lowest-concurrency baseline. The first level breaching the
degradation thresholds is marked `<-- DEGRADED`, and a summary line reports the
degradation concurrency. Full results are written to JSON; when run in GitHub
Actions (`GITHUB_STEP_SUMMARY` set) a markdown table is appended to the job summary.

**Exit code** is non-zero if any level degraded — usable as a CI gate.

### Interpreting results

- `same` flat but `multi` degrades early → the box can't cache all active
  partials at once. Levers (in order): drop the full `idx_verse_embedding_hnsw`
  index to free ~2.6 GB, then step the SKU up to `B2ms` (8 GB).
- Both degrade together at low concurrency → CPU-bound (burstable credit
  exhaustion); a dedicated-CPU SKU is the fix.
- Rising error rate before latency → connection-pool ceiling or DB
  `max_connections`; revisit `db_pool_size` / `db_max_overflow`.

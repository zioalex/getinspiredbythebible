# How to Export Retrieval-Miss Insights

When scripture retrieval comes back empty or weak, or the reply cites verses that were
never retrieved, the backend can record a privacy-safe row in the `retrieval_miss_samples`
table (BITB-256). The rows describe *what kind of question* retrieval struggled with —
topic, language, translation, scores — so embeddings, topic curation and query expansion
can be tuned against real traffic **without storing what users typed**.

See also: [`api/feedback/retrieval_misses.py`](../api/feedback/retrieval_misses.py),
[`api/feedback/models.py`](../api/feedback/models.py),
the public [Privacy Policy](../frontend/public/legal/privacy-policy.md),
[`HOW-TO-EXPORT-BLOCKED-SAMPLES.md`](HOW-TO-EXPORT-BLOCKED-SAMPLES.md) (the sibling,
text-bearing safety table).

## What counts as a miss

A turn can carry several reasons at once:

| Reason               | Meaning                                                                         |
| -------------------- | ------------------------------------------------------------------------------- |
| `empty`              | Retrieval returned no verses/passages, or raised (incl. the BITB-058 fail-closed reply). |
| `low_score`          | The best similarity is below the per-embedding-model threshold (see below).     |
| `cited_outside_pool` | The reply cites verses that were not in the retrieved context nor discussed earlier in the conversation. |

Never recorded: blocked, off-topic and clarification turns, crisis/compassionate turns,
`include_search=false`, and anything while capture is off. `low_score` is additionally
skipped for the `GENERAL` intent and for explicit verse lookups (direct lookups have no
similarity). `empty` is still reported for `GENERAL` turns, so greetings that match nothing
show up as `empty` — filter on `intent` when reading the data.

> When `CONTENT_FILTER_INTENT_DETECTION` is off, every turn is treated as `GENERAL`, so
> `low_score` is never recorded. Keep intent detection on if you rely on that reason.

## Stored vs not stored

Stored (derived signals only):

| Column                 | Meaning                                                                       |
| ---------------------- | ----------------------------------------------------------------------------- |
| `reasons`              | Array of the reasons above.                                                   |
| `intent`, `language`, `translation` | Intent label, language code and the Bible translation used.     |
| `topics`               | Canonical English topic ids from the keyword map (e.g. `anxiety`).            |
| `expansion_terms`      | Sanitized query-expansion keywords (see *Privacy boundary*).                  |
| `top_refs`             | Top 5 `{ref, score, source}`; `source` is `direct` (exact lookup, no score) or `search`. |
| `top_score`, `threshold` | Best similarity and the threshold it was compared with.                     |
| `cited_outside_pool`   | Verse refs the reply cited that were not retrieved.                           |
| `retrieval_mode`       | `hybrid`, `hybrid_boosted`, `semantic`, `boosted`, or `none` (search failed). |
| `embedding_provider`, `embedding_model` | Which embedding stack produced the scores.                   |
| `session_id_hash`      | sha256 of the session id (never the raw id). Set on first insert only.        |
| `signature_sha256`     | Dedup key: reasons + intent + language + translation + sorted topics + retrieval mode + embedding model. |
| `hit_count`            | How often this signature recurred.                                            |
| `created_at`, `last_seen_at`, `expires_at` | First/last occurrence and the fixed expiry.               |

**Not stored, anywhere (table, log, counter):** the user's message, the model's reply,
the expanded query sentence, IP address, account or user-agent. There is no text column.

`top_refs.source` does not distinguish semantic from keyword hits: in hybrid mode the
engine returns one blended score (`0.7*semantic + 0.3*keyword`), so only `direct` vs
`search` is recorded. Scores are not comparable across modes; always group by
`retrieval_mode` and `embedding_model`.

## Privacy boundary: allow-list-only expansion terms

The query expansion is LLM-written and can echo user words (a name, a place, an id).
`sanitize_expansion_terms` is therefore the only gate between that text and the database,
and it is **allow-list only**: a term survives solely if, case-folded, it equals as a whole
term an entry of the fixed topic vocabulary (`TOPIC_KEYWORD_MAP`, all supported languages)
or a Bible book name in any language. There is no length or word-count pass, so free text,
names, places and ids are dropped by construction.

1. Split on `, ; newline • · 、 ， ； ، ؛` and ` - `; strip bullet/numbering markers
   (`-`, `*`, `•`, `1.`, `1)`), quotes and brackets; case-fold.
2. Drop terms containing a digit, `@`, `://`, `www.` or a bare domain (`example.com`).
3. Keep only exact allow-list matches (for unspaced scripts such as Han that is an exact
   whole-term match).
4. A book-name term is dropped when it appears in the user's message as a standalone token
   (Daniel, Mark, James, John ... are also first names), unless the message contains a
   parsed verse reference to that same book.
5. De-duplicate, cut to 40 characters, keep at most 10.

Tests drive adversarial inputs for all 11 languages and run a sentinel (English and Chinese
names, bullet-formatted expansions) through `chat()` and `chat_stream()`, asserting nothing
reaches the persisted row or any `rag_retrieval_miss` log record.

## Enabling capture (operator)

Capture is **off by default** (`RETRIEVAL_MISS_CAPTURE_ENABLED=false`). Nothing is recorded,
logged or counted until you turn it on. It is a plain backend environment variable; there is
no Terraform variable or make target for it.

- **Azure (production):** set the env var on the backend Container App, for example
  `az containerapp update -g <rg> -n <backend-app> --set-env-vars RETRIEVAL_MISS_CAPTURE_ENABLED=true`
  (or Portal > Container App > Containers > Environment variables). Terraform does not manage
  this variable, but a later `terraform apply` that rewrites the app's env list can drop it;
  re-check after infra changes.
- **Local docker:** add `RETRIEVAL_MISS_CAPTURE_ENABLED=true` to `.env.local` (or `.env.dev`)
  and add the variable under the backend `environment:` in the compose file in use if it is not
  forwarded, then restart with `make docker-up`.
- **Bare `uvicorn`:** export the variable before starting the API.

Other settings:

```bash
RETRIEVAL_MISS_RETENTION_DAYS=90           # default 90, validated to 1..90 (policy: up to 90 days)
RETRIEVAL_MISS_LOW_SCORE_THRESHOLD=0.5     # optional explicit override; unset or empty = per-model table
RETRIEVAL_MISS_LOW_SCORE_THRESHOLDS='{"mxbai-embed-large:hybrid": 0.5}'  # JSON, per model
```

The table is created by Alembic revision `r0009`; run `alembic upgrade head` first. The
backend swallows write errors, so a missing table never affects a chat reply.

Writes are fire-and-forget background tasks after the reply path decides the turn was a
miss: zero added latency, one upsert per miss, errors logged and dropped. At most 50 writes
may be pending at once (extra misses still produce the log event and counter), and turns where
the search itself failed are telemetry-only, so a struggling database is not given more work.

### Deriving the `low_score` threshold

`low_score` fires when `max(similarity) < threshold`. Resolution order: explicit
`RETRIEVAL_MISS_LOW_SCORE_THRESHOLD`, then `RETRIEVAL_MISS_LOW_SCORE_THRESHOLDS` key
`<embedding model>:<hybrid|semantic>`, then key `<embedding model>`, then `0.5`.
(The model is `AZURE_EMBEDDING_DEPLOYMENT` for `azure_openai`, else `EMBEDDING_MODEL`.)

The shipped per-model values are **provisional placeholders**. Replace them with the p10 of
top-1 scores of *correct* hits from the BITB-139 golden set, per config:

```bash
DATABASE_URL=... python scripts/run_search_eval.py --run --config hybrid --score-distribution
DATABASE_URL=... python scripts/run_search_eval.py --run --config baseline_semantic --score-distribution
```

This prints `p10/p25/p50/n` of the top-1 similarity over queries whose top-1 verse matched a
relevant reference (add `--json` for a `score_distribution` object). It needs a corpus with
embeddings, which is why the numbers are not yet measured.

## Exporting rows

The exporter is **read-only** and connects through `DATABASE_URL`.

```bash
# Latest 100 rows as JSON
DATABASE_URL=postgresql://... python scripts/export_retrieval_misses.py --limit 100

# Italian empty-retrieval rows since 2026-11-01 as CSV
DATABASE_URL=postgresql://... python scripts/export_retrieval_misses.py \
    --reason empty --language it --since 2026-11-01 --format csv --output it_empty.csv

# Topic x language x reason, summing hit_count
DATABASE_URL=postgresql://... python scripts/export_retrieval_misses.py --aggregate --format csv
```

| Flag                 | Meaning                                                              |
| -------------------- | -------------------------------------------------------------------- |
| `--reason <name>`    | `empty`, `low_score` or `cited_outside_pool`.                        |
| `--language <iso>`   | e.g. `en`, `it`, `ar`.                                               |
| `--translation <c>`  | e.g. `kjv`, `web`.                                                   |
| `--since`/`--until`  | Inclusive / exclusive bounds on `created_at` (`YYYY-MM-DD`).         |
| `--limit N`          | Max rows (or max aggregate groups).                                  |
| `--aggregate`        | Group by topic x language x reason (`(none)` when no topic matched). |
| `--format json\|csv` | Output format (default JSON).                                        |
| `--output FILE`      | Write to a file instead of stdout.                                   |

In `--aggregate` output a multi-reason row counts once per reason, and a multi-topic row once
per topic, so totals across groups exceed the row count. `signatures` counts distinct rows,
`hits` sums `hit_count`.

## Known limitations

- **`topics` is empty for ru, zh, hi and ko.** Topic detection (`chat/topics.py`) is a keyword
  map covering en, it, de, es, fr, pt, ar only. Those four languages still record every other
  field, and aggregate under `(none)`. Extending coverage is tracked as BITB-264.
- **`expansion_terms` is a thin signal.** Because the sanitizer is allow-list only, it is
  empty for ru, zh, hi and ko (the topic vocabulary has no entries for them; only book names
  can match), nearly empty for ar (the vocabulary has no article/inflected forms such as
  `القلق`), and keeps roughly 30-50% of expansion terms for Latin-script languages. Treat it as
  a coarse hint, not a record of what the model searched for.
- Topics come from the keyword map, not from the model, so a miss on an unmapped theme shows
  under `(none)`.

## Retention and purge

`expires_at` is set once, on first insert, to `created_at + RETRIEVAL_MISS_RETENTION_DAYS`
(1..90) and is **not** refreshed by repeats, so a row lives at most 90 days regardless of
recurrence. An upsert never touches a row whose `expires_at` has passed, and the exporter only
returns rows with `expires_at > now()`, so an expired row is invisible even before it is deleted.

An expired-but-not-yet-purged row does not accept new hits: new misses with the same signature
are dropped (log event and counter still fire) for up to one hour, until the purge removes the
row and the next miss inserts a fresh one.

Deletion is done by the API process itself (no `pg_cron` job, unlike blocked samples): once at
startup and then **hourly** by a background loop in `api/main.py` (`_ttl_purge_loop`). A
deployment with several replicas simply runs the same idempotent `DELETE` on each. To force a
purge:

```sql
DELETE FROM retrieval_miss_samples WHERE expires_at < now();
```

Volume is bounded by the number of distinct signatures (reasons x intent x language x
translation x topic set x retrieval mode x embedding model), not by traffic.

## Telemetry

Each recorded miss also emits:

- An OpenTelemetry counter `chat.retrieval_miss` with attributes `reason`, `language`,
  `translation`, `intent` (one increment per reason).
- A structured log event `rag_retrieval_miss` with the same fields as the row minus
  `session_id_hash`. Application Insights (KQL):

  ```kusto
  traces
  | where message == "rag_retrieval_miss"
  | extend reasons = tostring(customDimensions.reasons),
           language = tostring(customDimensions.language),
           topics = tostring(customDimensions.topics)
  | summarize misses = count() by language, reasons, bin(timestamp, 1d)
  | order by timestamp desc
  ```

  Counter query (metrics): `customMetrics | where name == "chat.retrieval_miss"`.

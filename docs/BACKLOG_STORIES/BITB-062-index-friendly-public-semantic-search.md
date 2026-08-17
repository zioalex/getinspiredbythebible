# BITB-062: Route Public Semantic Search Through the Index-Friendly Candidate-Pool Pattern

**Status:** 🚧 In Progress — candidate-pool CTE + topics index + FTS rewrite + persisted `tsvector`
column done; `search_verses_text` query switch to the new column (and retiring
`idx_verses_fts_simple`) split out as **BITB-095** (see Scope Note)
**Priority:** P1 (High) — 2026-07 adversarial audit S2 (HIGH); public unauthenticated endpoint full-scans the production database
**Size:** M (rewrite three query functions onto the existing CTE pattern + one missing index + FTS column)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — S2 (context: S5, S7)

## Scope Note

The original PR shipped acceptance criteria 1, 2, 4 (SQL-shape assertions; a
row-count-independent `EXPLAIN`/Seq-Scan check isn't meaningful against sandbox-scale test
data — see PR description), and 5, plus the `ILIKE` → `@@ plainto_tsquery` half of
criterion 3. The **persisted generated `tsvector` column** half of criterion 3 was
deferred to its own follow-up (this one): it's an `ALTER TABLE` full-table-rewrite on the
31K-row `verses` table (locking implications on the same box this story protects) — a
materially different risk profile from the read-path rewrites in the original PR, and one
PR/day shouldn't carry both.

**This follow-up** adds `verses.text_tsv` (`GENERATED ALWAYS AS (to_tsvector('simple',
text)) STORED`) and its GIN index (`idx_verses_text_tsv`) as a single Alembic revision,
`api/alembic/versions/r0004_add_verses_text_tsv.py`.

> **Changed since this was first written.** The original version shipped the same change
> twice — once as `scripts/migrations/012_*` and once as an Alembic revision — under the
> "interim dual-write window" note in `docs/MIGRATION_GUIDELINES.md`, because the deploy
> pipeline did not yet run Alembic against production. BITB-089 has since shipped: the
> pipeline runs `alembic upgrade head`, production is stamped, and `scripts/migrations/`
> is frozen. The legacy half and the dual-write note are gone, and the revision is
> renumbered `r0004` (`r0002` and `r0003` were taken by BITB-089's pipeline probe).
> The index is now built with `CREATE INDEX CONCURRENTLY` inside an `autocommit_block()`,
> which matters now that this deploys automatically rather than by hand.

It is deliberately additive
only: `search_verses_text` still matches on the raw `to_tsvector('simple', text)`
expression and `idx_verses_fts_simple` is left in place, so there is no functional or
performance regression window. **Split out as BITB-095** (for the same
reason — deploy runs the new app code before `run-migrations`, so shipping the query
switch in the same push as the migration would 500 public search for the deploy window):
switching `search_verses_text` to query `text_tsv` directly and dropping the now-redundant
`idx_verses_fts_simple`. Criterion 6 (prod perf re-run) still needs a deployed environment
and remains a post-merge follow-up.

## User Story

As the operator of a 2-vCPU/4GB production Postgres serving 12 translations, I want every
vector-search path to use the HNSW index, so that a handful of unauthenticated search calls cannot
saturate the database and starve chat — the actual product — of connections and CPU.

## Problem / Motivation

The hybrid search path was deliberately rewritten around an HNSW-friendly candidate-pool CTE
(`api/scripture/repository.py:35–70`) precisely because a similarity-threshold `WHERE` clause
forces a full scan — its own docstring says so (lines 46–48). Yet:

- `search_verses_semantic` (`repository.py:283`) still filters
  `WHERE (1 - cosine_distance) >= threshold` — the exact full-scan predicate — and backs the
  **public** `GET /api/v1/scripture/search` (`routes/scripture.py:303`, `search.py:80`).
- `search_passages_semantic` / `search_topics_semantic` (`repository.py:668–691, 799–811`) do the
  same, and `topics.embedding` has **no vector index at all** (`scripture/models.py:233`).
- `search_verses_text` uses leading-wildcard `ILIKE '%q%'` (`repository.py:247–255`) — unindexable.

Migration 007's README already documents the fear that concurrent multilingual HNSW load makes this
box thrash (BITB-056 measured the saturation knee at concurrency ≈ 32). These full scans spend that
scarce headroom fastest.

## Acceptance Criteria

- [x] Pure semantic verse/passage search goes through the candidate-pool CTE pattern:
      ANN-rank by `embedding <=> q LIMIT :candidate_pool` first, apply the similarity threshold in
      the outer query (`search_verses_semantic`, `search_passages_semantic`). `search_topics_semantic`
      was already index-friendly in shape (no threshold `WHERE`) — it only lacked the index, fixed
      by the criterion-2 migration.
- [x] HNSW index added on `topics.embedding` via a numbered migration (`011_add_topic_hnsw_index.py`,
      `CREATE INDEX CONCURRENTLY`, same pattern as migration 007). Numbered 011, not 009 — PR #866
      already claims 009/010.
- [x] `search_verses_text` replaced `ILIKE '%q%'` with `to_tsvector('simple', text) @@
      plainto_tsquery('simple', :query)`, matching migration 003's existing
      `idx_verses_fts_simple` expression index.
- [x] Persisted generated `tsvector` column: `verses.text_tsv` + `idx_verses_text_tsv`
      (Alembic `r0004`). **Carried by BITB-095:** switching
      `search_verses_text` to query this column instead of the raw expression, and
      retiring `idx_verses_fts_simple` — see Scope Note above.
- [x] SQL-shape regression tests assert the candidate-pool CTE runs before the threshold filter and
      that no `ILIKE` remains (`test_hybrid_search.py`); real-DB integration tests confirm the
      rewritten queries execute and return correct results (`test_hybrid_search_integration.py`).
      A literal `EXPLAIN`/no-Seq-Scan assertion isn't meaningful at the ~1-row scale available in
      CI/sandbox (the planner prefers Seq Scan regardless of predicate shape below a few thousand
      rows) — deferred to a documented post-deploy check against production-scale data.
- [x] `search_eval --validate` (58 cases / 11 languages) passes; the candidate-pool bound
      (`vector_candidate_pool=100`, `hnsw_ef_search=120`) is unchanged from the hybrid path already
      running in production, so ranking recall for these search paths is not expected to regress.
- [ ] Perf re-run of `scripts/perf/search_concurrency_test.py` — needs a deployed environment;
      follow-up post-merge.

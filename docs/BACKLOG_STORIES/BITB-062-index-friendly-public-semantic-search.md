# BITB-062: Route Public Semantic Search Through the Index-Friendly Candidate-Pool Pattern

**Status:** 🚧 In Progress — candidate-pool CTE + topics index + FTS rewrite done; persisted `tsvector` column deferred (see Scope Note)
**Priority:** P1 (High) — 2026-07 adversarial audit S2 (HIGH); public unauthenticated endpoint full-scans the production database
**Size:** M (rewrite three query functions onto the existing CTE pattern + one missing index + FTS column)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — S2 (context: S5, S7)

## Scope Note

This PR ships acceptance criteria 1, 2, 4 (SQL-shape assertions; a row-count-independent
`EXPLAIN`/Seq-Scan check isn't meaningful against sandbox-scale test data — see PR
description), and 5, plus the `ILIKE` → `@@ plainto_tsquery` half of criterion 3. The
**persisted generated `tsvector` column** half of criterion 3 is deferred to a follow-up:
it's an `ALTER TABLE` full-table-rewrite on the 31K-row `verses` table (locking
implications on the same box this story protects) — a materially different risk profile
from the read-path rewrites here, and one PR/day shouldn't carry both. Criterion 6 (prod
perf re-run) needs a deployed environment and is a post-merge follow-up.

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
      `idx_verses_fts_simple` expression index. **Deferred:** the persisted generated `tsvector`
      column — see Scope Note above.
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

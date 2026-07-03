# BITB-062: Route Public Semantic Search Through the Index-Friendly Candidate-Pool Pattern

**Status:** 📋 Backlog
**Priority:** P1 (High) — 2026-07 adversarial audit S2 (HIGH); public unauthenticated endpoint full-scans the production database
**Size:** M (rewrite three query functions onto the existing CTE pattern + one missing index + FTS column)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — S2 (context: S5, S7)

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

- [ ] Pure semantic verse/passage/topic search goes through the candidate-pool CTE pattern:
      ANN-rank by `embedding <=> q LIMIT :candidate_pool` first, apply the similarity threshold in
      the outer query.
- [ ] HNSW index added on `topics.embedding` via a numbered migration (respecting the
      `CREATE INDEX CONCURRENTLY` constraint documented for migration 007).
- [ ] `search_verses_text` replaced with the existing FTS machinery; a persisted generated
      `tsvector` column + GIN index replaces per-query `to_tsvector('simple', v.text)` computation
      (audit S7).
- [ ] `EXPLAIN` verification in tests or eval notes: no `Seq Scan` on `verses`/`passages`/`topics`
      for the search paths at production-like row counts.
- [ ] `search_eval` golden-set results confirm ranking quality is not degraded by the
      candidate-pool bound (tune `candidate_pool` if needed — config knobs already exist).
- [ ] Perf re-run of `scripts/perf/search_concurrency_test.py` shows the saturation knee moved
      meaningfully right, or the result is documented if not.

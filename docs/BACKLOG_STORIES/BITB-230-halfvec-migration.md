# BITB-230: Halve the Vector Footprint — `verses.embedding` to `halfvec(1536)`

**Status:** 🎯 Todo
**Priority:** P2
**Size:** L (migration-shaped: staged column add, backfill, parallel indexes, recall gate, cutover)
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — Part B lever 3; the story BITB-150 explicitly said must stand alone)

## User Story

**As** the owner of a 2 vCore / 4 GB burstable server carrying ~7.7 GB of
1536-dim float32 vectors and HNSW indexes, **I want** the embedding column stored
as pgvector's `halfvec(1536)` (2 bytes/dim instead of 4), **so that** the
vector+index footprint halves, the working set fits in RAM with room to grow,
and the B1ms conversation (BITB-231) becomes evidence-decidable instead of
speculative.

## The evidence-driven case

- `05c`/`05d`: vector path today ≈ 2.48 GB stored + 3.15 GB full HNSW + 2.67 GB
  partial set ≈ **7.7 GB** that halves to **≈3.8 GB**
- Memory p95 is **58.1%** of 4 GB (`06-memory_percent.json`) — the partial-index
  cache that justified the B2s (BITB-150's context) is the pressure point;
  halving index size is the one change that attacks storage *and* RAM at once
- CPU has 10× headroom (p95 8.1%) — the cost of a slightly higher recall-restore
  scan effort (HNSW `ef_search` bump) is available where the RAM saving pays
- Storage ratchet interaction: the transition rewrite must be watched against
  the 64 GB ceiling (p95 63.6% used) — see phases below; BITB-228 must land first

## Recall: the non-negotiable gate

halfvec's precision cost on 1536-dim cosine ANN is small but *not zero*. The
gate is the existing golden set, run before and after:

- `scripts/run_search_eval.py` + the 84-case multilingual golden set
  (Precision@5 / Recall@10 / MRR), **all 11 languages**
- Baseline recorded from current prod behavior; acceptance = MRR/P@5 within an
  explicit tolerance (propose: no worse than −1.5% absolute on P@5, −2% MRR;
  final numbers agreed at implementation time and written here before cutover)
- If recall misses tolerance: raise HNSW `ef_search` first (CPU headroom exists);
  re-gate; only a documented product decision rejects the migration

## Migration design (staged, per `docs/MIGRATION_GUIDELINES.md` and the 2026-08-17 retro)

1. **Add** `embedding_half halfvec(1536)` alongside the existing column — pure
   `ALTER TABLE ADD COLUMN`, no rewrite
2. **Backfill** in batches (`UPDATE ... WHERE id BETWEEN ...`), off-peak, with
   `lock_timeout` + `statement_timeout` per the guidelines; watch storage% and
   pause if it approaches the auto-grow line
3. **Build indexes CONCURRENTLY**: `hnsw (embedding_half halfvec_cosine_ops)`
   full + the per-translation partial set (same predicates as migration 007) —
   no ACCESS EXCLUSIVE on `verses`
4. **Gate:** golden-set A/B (old column vs new) — numbers recorded in this file
5. **Cutover:** app writes both during transition → switch reads to
   `embedding_half` (single config/flag flip, both chat paths + public search) →
   one release of dual-write soak → stop writing float32
6. **Drop** old column + old indexes (the migration-002/007 set) — separate PR
   after a soak window

Each phase is its own PR/deploy with `make test` + prod probes green between.

## Honest savings math

- Direct storage: ~2.4 CHF/mo class (same 0.075 CHF/GB logic; vectors+indexes
  ≈3.8 GB less)
- Ratchet: keeps total DB ≈9-10 GB post-217 — years of headroom on a 32 GB disk
  (post-BITB-229), i.e. the 128 GB scenario becomes unreachable
- RAM: partial HNSW set ~1.3 GB + full ~1.6 GB fits in shared_buffers/effective
  cache with slack — this is the enabler for BITB-231's ~17 CHF/mo
- **This story's own direct saving is small; its value is unlocking 220 and
  ending the storage trajectory.** Do it for the working set, not the bill.

## Acceptance Criteria

- [ ] BITB-228 merged first (never rebuild half of a dead index)
- [ ] Baseline golden-set numbers recorded here before any schema change
- [ ] Backfill batched, lock-gated, storage%-watched — zero ingestion or
      availability alert fires during it (BITB-223's recalibrated rules as the
      canary)
- [ ] Post-migration golden set within agreed tolerance across **all 11
      languages**; `ef_search` bump documented if used
- [ ] Both chat paths (`chat()`, `chat_stream()`) + public search exercise the
      new column (integration tests through the routes, not pure functions)
- [ ] Old column/indexes dropped in a follow-up PR after a dual-write soak
- [ ] Post-cutover: memory% p95 visibly reduced; numbers recorded here

## Out of Scope

- Changing embedding *model* or dimensions (stays `text-embedding-3-small`, 1536)
- Topics table vectors (tiny; only if trivially included at implementation time)
- The B1ms decision itself (BITB-231)

## Related

- BITB-150 — parent; quotes its warning that this is "the most invasive" lever
- BITB-228 — hard prerequisite
- BITB-231 — the payoff this unlocks
- `docs/MIGRATION_GUIDELINES.md`, `docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md`
  — binding process rules
- `docs/GOLDEN_SET_GUIDE.md` — the recall gate

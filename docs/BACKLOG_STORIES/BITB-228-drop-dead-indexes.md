# BITB-228: Drop the Dead Indexes — 6.8 GB of Lifetime-Zero-Scan Weight

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S–M (one migration PR, low-risk DDL)
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — Part B lever 4)
**Supersedes the scope of:** BITB-098 (its two `_english` GIN indexes are a subset of this list)

## User Story

**As** the owner of a 16 GB database that is 12 GB indexes (`05c`), paying for
every write to amplify through dead structures, **I want** the indexes that have
never been read dropped, **so that** writes get cheaper, the next backup and any
future disk conversation starts from a truthful footprint, and the biggest single
storage reclaim available happens with zero feature loss.

## The evidence (lifetime statistics — `stats_reset` is NULL, `05e`)

`05d-postgres-all-indexes.txt`, scans counted since server creation:

| Index | Size | `idx_scan` | Verdict |
|-------|------|-----------|----------|
| `idx_verse_embedding` (legacy **IVFFlat**) | **3,397 MB** | **0** | Dead — superseded by the HNSW indexes (migration 002/007) |
| `idx_verse_embedding_cosine` (legacy **IVFFlat**) | **3,396 MB** | **377** | Near-dead — legacy path from before the HNSW cutover |
| `idx_verses_fts_english` | 59 MB | **0** | Dead (BITB-098's finding) |
| `idx_verses_fts_simple` | 62 MB | **0** | Dead — the story only suspected the `_english` pair; the evidence shows the `simple` pair is equally unread |
| `idx_passages_fts_english` | 16 kB | **0** | Dead |
| `idx_passages_fts_simple` | 16 kB | **0** | Dead |
| `idx_verse_embedding_hnsw` (full) | 3,155 MB | 13,519 | **ALIVE — keep** (no-translation search path is in active use) |
| partial HNSW set (11) | 2,670 MB | 143–17,876 each | **ALIVE — keep** |

**6.8 GB of the 16 GB database has no readers.** The two IVFFlat indexes alone
are ~42% of the entire database — a bigger reclaim than anything the BITB-150
story dared to imagine, because the story didn't know they existed.

## Why the FTS indexes are safe to drop

`backfill_verse_tsv.py` + the persisted `verse_tsv` column carry the hybrid-search
path; the FTS GIN indexes predate it. `idx_scan = 0` across the *lifetime* of the
server (not a short window) with `verse_tsv` at 133 MB (top-tables evidence)
shows the operational path never touches them. Every DROP is preceded by a
`pg_stat_user_indexes` re-check on the day (cheap insurance against a query added
since the evidence was gathered).

## Honest cost framing (from the meters)

- Storage meter averages **4.80 CHF/mo** for 64 GB ≈ 0.075 CHF/GB/mo. Dropping
  6.8 GB of *logical* space saves **~0.5 CHF/mo directly** — small, because
  storage is cheap.
- The real value: (a) write amplification removed from every verse INSERT/UPDATE
  and every embedding backfill; (b) it is the precondition for the disk shrink
  (BITB-229) that stops the 64→128 GB ratchet (~+4.7 CHF/mo avoided) and halves
  backup storage; (c) vacuum/maintenance runs get faster.
- This story deliberately does **not** promise the shrink: a Flexible Server
  disk never shrinks in place. Reclaim-to-money is BITB-229.

## Acceptance Criteria

- [ ] Day-of re-check: `pg_stat_user_indexes` re-queried immediately before each
      drop; any index that gained scans since 2026-10-23 is spared and investigated
- [ ] Drops executed with `DROP INDEX CONCURRENTLY` off-peak (no ACCESS EXCLUSIVE
      lock on `verses`; see `docs/MIGRATION_GUIDELINES.md`)
- [ ] All six indexes above confirmed gone (or spared with documented reason);
      `pg_relation_size` sum for `verses` drops ≈6.8 GB
- [ ] Hybrid search (`verse_tsv` path), semantic search (HNSW full + partials),
      and no-translation search each smoke-tested post-drop (existing test suite
      + one prod probe via `prod-monitor.yml`)
- [ ] Migration recorded per repo convention (Alembic or the scripts/migrations
      runner as appropriate) so a fresh DB never builds these indexes
- [ ] BITB-098 closed as absorbed by this story (with a note in its file)

## Out of Scope

- The full HNSW (alive — 13,519 scans; declined in BITB-150)
- Disk shrink / dump-restore (BITB-229)
- `halfvec` (BITB-230 — orthogonal, but should land *before* it to avoid
  rebuilding half of a dead index)

## Related

- BITB-098 — original two-GIN story; absorbed here
- BITB-150 — parent; the Phase 0 evidence that found the IVFFlat pair
- BITB-229, BITB-230 — downstream stories this unblocks
- `docs/MIGRATION_GUIDELINES.md` — locking rules; `DROP INDEX CONCURRENTLY`
  cannot run inside a transaction block

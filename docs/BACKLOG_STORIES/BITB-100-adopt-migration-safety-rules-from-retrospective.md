# BITB-100: Make the Migration-Safety Rules Enforceable, Not Aspirational

**Status:** ✅ Done (2026-08-25)
**Priority:** P2 (P1 items live in BITB-097; this covers what remains after it)
**Size:** S–M
**Created:** 2026-08-19
**Source:** `docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md`

**What shipped:** a new "Locking & scale (Alembic revisions)" section in
`docs/MIGRATION_GUIDELINES.md` (cross-linked from `api/alembic/README.md`), a
"Migration checklist" block in `.github/pull_request_template.md`, a
DB-free AST check in `api/tests/test_alembic_migrations.py` that fails any
new revision whose `upgrade()` doesn't reach a `lock_timeout` call (r0001–
r0003 exempted as pre-existing), a "Benchmark before you build on a
performance claim" section in `docs/CONTRIBUTING.md`, and a "Retrospectives"
section in `docs/BACKLOG.md` linking the source retrospective.

## User Story

**As** the maintainer, **I want** the retrospective's process rules to live in checked documents
and CI assertions rather than in memory, **so that** the next migration is safe because the system
makes it so, not because whoever writes it remembers August 2026.

## Why

The outage retrospective adopted five rules. Rules in a retrospective file decay; each needs an
enforcement point. BITB-097 owns the pipeline half (ordering, timeouts, triggers, gate). This
story owns the rest — the parts that live in docs, templates, and tests.

## Scope

1. **`docs/MIGRATION_GUIDELINES.md` gains a "Locking & scale" section** (deduplicated with what
   BITB-097 adds for expand/contract):
   - Every revision's docstring must state lock level and expected duration **at production scale
     (≥400k rows, realistic row width)** — or say "unknown" explicitly.
   - Table-rewriting DDL (`ADD COLUMN ... STORED`, type changes, `CLUSTER`, plain `DROP INDEX` on
     hot tables) is banned from the CI pipeline; the manual off-peak procedure is linked.
   - Server-side `lock_timeout`/`statement_timeout` required in every revision until set at
     job/role level.
   - New-code-old-schema compatibility is the default: no migration-dependent columns on hot ORM
     models in the same release (the `VerseTsv` pattern, with the `select(Verse)` failure as the
     example).
   - `CAST(x AS t)`, never `::` in raw SQL (asyncpg bind-guard).

2. **A migration checklist in the PR flow**: extend `.github/pull_request_template.md` with a
   short conditional block ("If this PR contains an Alembic revision: lock level stated? scale
   measured? timeouts set? rollback tested?").

3. **CI assertion where cheap**: extend `api/tests/test_alembic_migrations.py` to fail any new
   revision whose `upgrade()` lacks a `lock_timeout` (regex-level check is enough; it catches
   forgetting, not adversaries). Skip once BITB-097's job-level `PGOPTIONS` lands — the test then
   asserts *that* instead.

4. **Benchmark-before-build rule recorded in `docs/CONTRIBUTING.md`**: a story whose justification
   is performance must carry a measurement at production scale before a second PR builds on it.
   One paragraph, pointing at the retrospective's 37%-slower finding as the cautionary example.

## Acceptance Criteria

- [x] MIGRATION_GUIDELINES section merged, cross-linked from `api/alembic/README.md`
- [x] PR template block added (conditional, short — not a form for non-migration PRs)
- [x] `test_alembic_migrations.py` fails a revision without `lock_timeout` (fixture-tested both ways)
- [x] CONTRIBUTING paragraph added
- [x] Retrospective linked from BACKLOG.md so it stays findable

## Related

- `docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md` — source of every rule here
- BITB-097 — pipeline enforcement (ordering, job timeouts, triggers, gate); this story must not
  duplicate it
- BITB-096 — the incident and the pattern being canonized

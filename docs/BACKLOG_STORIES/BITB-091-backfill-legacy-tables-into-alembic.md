# BITB-091: Backfill the Five Legacy Non-ORM Tables into Alembic

**Status:** 🎯 Todo
**Priority:** P3
**Size:** M
**Created:** 2026-07-31
**Depends on:** BITB-089 (Alembic authoritative in the deploy pipeline).

## User Story

**As a** maintainer, **I want** every table in the database to be managed by one migration system,
**so that** there is no category of table that changes only by hand-edited SQL.

## Why Now — and why this is genuinely optional

Five tables exist in every real database but have no SQLAlchemy model:

`sessions`, `verse_topics`, `rate_limit_hits`, `rate_limit_sessions`, `schema_migrations`

They are created by `scripts/init.sql` / `scripts/migrations/` and are deliberately invisible to
Alembic via the `include_name` / `include_object` allowlist in `api/alembic/env.py`. That filter is
**load-bearing, not an oversight**: without it the first `--autogenerate` would propose
`op.drop_table(...)` for all five, because Alembic sees tables with no corresponding metadata and
concludes they should not exist. `api/alembic/README.md` documents this as invariant #1.

So the current state is safe and stable, and can stay this way indefinitely. The cost of *not*
doing this is narrow but real: changing any of those five means hand-rolled SQL against a frozen
system, with no revision history, no rollback, and no `alembic check` coverage. Worth doing when
one of them next needs to change — not before.

⚠️ **`schema_migrations` is a special case.** It is the legacy system's own bookkeeping table. It
should almost certainly **not** be adopted; it should be retired once nothing writes to it. Adopting
Alembic's `alembic_version` *and* the tracker it replaces is a state worth avoiding.

## Design Notes

The mechanism is the reverse of the usual flow — the tables already exist, so no DDL should run:

1. Add SQLAlchemy models matching the **live** definitions exactly. Verify against a restored copy
   of production (`docs/HOW-TO-BACKUP-RESTORE-DATABASE.md`, Scenario C), not against
   `scripts/init.sql`, which may have drifted from what is actually deployed.
2. Remove those names from the `include_name` allowlist in `env.py`.
3. Run `alembic revision --autogenerate` and confirm it produces an **empty** upgrade. A non-empty
   diff means the models do not match reality — fix the models, never "fix" the database to match.
4. If a difference is genuine, it needs its own reviewed revision, applied deliberately.

The danger throughout is a generated `drop_table` or `drop_column` reaching production. Every
generated revision in this story must be read line by line; `alembic check` passing is necessary
but not sufficient.

## Acceptance Criteria

- [ ] Models added for the four adopted tables (not `schema_migrations` — see above, or justify)
- [ ] Models verified against a restored copy of production, not against `init.sql`
- [ ] `include_name` allowlist narrowed accordingly, with the comment updated to say what remains
      excluded and why
- [ ] `alembic revision --autogenerate` produces an empty diff — evidence in the PR
- [ ] `alembic check` clean against a restored prod copy
- [ ] No `drop_table` / `drop_column` in any generated revision (explicitly reviewed and stated)
- [ ] Roundtrip test (`api/tests/test_alembic_migrations.py`) extended to cover the adopted tables
- [ ] Decision recorded for `schema_migrations`: retire, adopt, or leave excluded
- [ ] `api/alembic/README.md` invariant #1 updated to match the new reality

## Out of Scope

- Deleting or rewriting `scripts/migrations/` — frozen as historical record by BITB-004
- Changing the shape of any of the five tables

## Related

- BITB-089, BITB-090 — the rest of the Alembic adoption sequence
- BITB-004 / PR #948 — listed this explicitly as out of scope
- `api/alembic/env.py` (`include_name` / `include_object`), `api/alembic/README.md` invariant #1
- `scripts/init.sql`, `scripts/migrations/`

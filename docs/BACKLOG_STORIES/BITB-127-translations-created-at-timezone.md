# BITB-127: Make `translations.created_at` Timezone-Aware

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-09-10
**Surfaced by:** BITB-094 (column-type audit) — see
`docs/audits/BITB-094-column-type-audit.md`

## User Story

**As a** maintainer running a UTC-everywhere service, **I want**
`translations.created_at` to carry an explicit timezone like every other
`created_at` column, **so that** the one naive timestamp in the schema stops
being a trap for whoever eventually compares it against a
`DateTime(timezone=True)` value or serializes it across a DST boundary.

## Why Now

BITB-093 found that `translations.created_at` is `TIMESTAMP` (no timezone) —
in both `scripts/init.sql` and `Translation.created_at` — while
`feedback.created_at`, `contact_submissions.created_at` and
`blocked_message_samples.created_at`/`.expires_at` are all
`DateTime(timezone=True)`. Because `api/alembic/env.py` sets
`compare_type=False`, `alembic check` could never have caught this on its
own; BITB-094 ran the first real column-type comparison the project has done
and confirmed model and database agree with each other on the naive form —
i.e. this is faithful-but-questionable, not drift. See
`docs/audits/BITB-094-column-type-audit.md` for the full classification.

Practically, `translations.created_at` is nearly inert today — it's metadata
on a 13-row reference table (bundled Bible translations), never compared
against another timestamp, never used in a query predicate. The risk is
latent, not active: the moment anything does compare it against a
timezone-aware value, or a future report/export serializes it, a naive
timestamp is ambiguous about which zone it's in. `CURRENT_TIMESTAMP`/
`datetime.utcnow()` (the current default) happen to always write UTC, so the
data itself is fine — only the column's declared type fails to say so.

## Approach

1. **Model change.** `Translation.created_at` becomes
   `DateTime(timezone=True)` in `api/scripture/models.py`, matching
   `Feedback.created_at` / `ContactSubmission.created_at`. Keep
   `server_default=sql_text("CURRENT_TIMESTAMP")` — `CURRENT_TIMESTAMP` casts
   cleanly to `timestamptz` and needs no rewording.
2. **Alembic revision.** A new revision (`r0007` or later, whatever is head
   at the time) with:

   ```python
   op.alter_column(
       "translations", "created_at",
       type_=sa.DateTime(timezone=True),
       existing_type=sa.DateTime(timezone=False),
       postgresql_using="created_at AT TIME ZONE 'UTC'",
   )
   ```

   `SET LOCAL lock_timeout` / `statement_timeout` per
   `docs/MIGRATION_GUIDELINES.md` ("Locking & scale (Alembic revisions)"),
   even though `translations` is tiny — the rule is mechanical, not
   row-count-conditional, and `api/tests/test_alembic_migrations.py` enforces
   it for every new revision regardless.
3. **Lock/rewrite assessment (do this before writing the revision, not
   after).** Two things to confirm against the actual production table
   before deciding this is a non-event:
   - **Row count and write pattern.** `translations` holds one row per
     bundled Bible translation (13 today) and is written only by
     `scripts/init.sql`'s seed insert and rare manual additions — never by
     request-path code. Confirm this against production (`SELECT count(*)
     FROM translations`) rather than assuming the local number holds; even
     if it's grown, three digits at most is still trivially fast.
   - **Rewrite avoidance.** PostgreSQL (12+) can convert `timestamp` →
     `timestamptz` *without* a full table rewrite when the conversion is
     driven by `AT TIME ZONE` and the session's time zone is `UTC` — the
     on-disk representation doesn't actually change, only its interpretation
     does. Confirm the production connection's `TimeZone` GUC is `UTC` (or
     set it explicitly for the migration session) before relying on this;
     if it can't be confirmed, treat the ALTER as a full rewrite for planning
     purposes — it is still trivial at this table's size either way.
   - Given the table's size, `ACCESS EXCLUSIVE` for the duration of the
     `ALTER` (rewrite or not) is very unlikely to be user-visible, but state
     the conclusion explicitly in the revision's docstring rather than
     asserting it silently, matching the standard set by `r0004`.
4. **Re-run `scripts/audit_column_types.py`** against a database migrated to
   the new head to confirm `translations.created_at` drops out of the
   flagged bucket entirely (it was never in the *expected-difference*
   bucket — only the three embedding columns are).
5. Update `scripts/init.sql`'s `translations.created_at TIMESTAMP DEFAULT
   CURRENT_TIMESTAMP` to `TIMESTAMPTZ`, so a fresh database created from it
   (rather than via `alembic upgrade head`) still matches the models — same
   convention BITB-093 established for every other reconciled column.

## Acceptance Criteria

- [ ] `Translation.created_at` is `DateTime(timezone=True)` in
      `api/scripture/models.py`
- [ ] `scripts/init.sql`'s `translations.created_at` is `TIMESTAMPTZ`
- [ ] New Alembic revision with `postgresql_using`, `lock_timeout` /
      `statement_timeout`, and a docstring stating the row-count/rewrite
      finding from the Approach section above
- [ ] Row count and rewrite-avoidance both confirmed against production (or
      the ALTER planned as a full rewrite if either can't be confirmed) and
      recorded in the revision's docstring
- [ ] `alembic upgrade head` rehearsed against a local/CI database; existing
      `translations` rows read back with the same instant they had before
      (no silent zone shift from an incorrect `AT TIME ZONE` direction)
- [ ] `scripts/audit_column_types.py` run against the upgraded database shows
      `translations.created_at` no longer flagged
- [ ] Applied to production following the same rehearse-then-run discipline
      as BITB-096/BITB-093

## Out of Scope

- Any other column type change — this story is scoped to exactly the one
  column BITB-094 named as faithful-but-questionable.
- Turning `compare_type=True` globally — still out of scope per BITB-094.

## Related

- BITB-094 — the audit that classified this column and recommended the fix;
  `docs/audits/BITB-094-column-type-audit.md`
- BITB-093 — established the "production is right, or the models are right"
  reconciliation pattern this story follows for `scripts/init.sql`
- BITB-100 / `docs/MIGRATION_GUIDELINES.md` — the lock/rewrite discipline
  ("Locking & scale (Alembic revisions)") this revision must follow
- `api/scripture/models.py` (`Translation.created_at`), `scripts/init.sql`

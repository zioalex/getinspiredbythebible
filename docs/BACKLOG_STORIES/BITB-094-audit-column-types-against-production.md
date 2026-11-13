# BITB-094: Audit Column Types Against Production — the Blind Spot `alembic check` Cannot See

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S–M (an audit; unknown remediation until it runs)
**Created:** 2026-08-15
**Depends on:** BITB-093 (structural reconciliation) — done.

## User Story

**As a** maintainer who has just made Alembic authoritative, **I want** to know whether production's
column *types* match the ORM models, **so that** "the schema is reconciled" is a complete statement
rather than one that quietly excludes an entire category of difference.

## Why Now

`api/alembic/env.py` sets `compare_type=False`. That is deliberate and correct:
`Verse.embedding` is `Vector(settings.embedding_dimensions)`, which is 1024 for the ollama-backed
local/CI default and 1536 for `azure_openai` in production. With type comparison on, `alembic check`
would report drift in every environment purely because two environments run different embedding
providers, and the CI gate would flap for no reason.

The cost is that it suppresses **all** type comparison, not just vectors. Every `alembic check` run
during BITB-089 and BITB-093 — including the clean one against production — compared table, column,
constraint, index and comment *presence*, and compared **no types at all**.

So the reconciliation achieved in BITB-093 is structural. A `varchar(50)` where the model says
`varchar(100)`, an `integer` where the model says `bigint`, or a `timestamp` where the model says
`timestamptz` would all have passed silently.

There is already a concrete candidate. In the models:

| column | model type |
| --- | --- |
| `translations.created_at` | `DateTime` — **no** timezone |
| `feedback.created_at` | `DateTime(timezone=True)` |
| `contact_submissions.created_at` | `DateTime(timezone=True)` |
| `blocked_message_samples.created_at` / `.expires_at` | `DateTime(timezone=True)` |

`scripts/init.sql` declares `translations.created_at` as `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
(no timezone) and the other two as `TIMESTAMP WITH TIME ZONE DEFAULT NOW()`. Model and SQL agree
on the inconsistency, so it is most likely faithfully reflected in production rather than drift —
but "most likely" is exactly the standard this story exists to replace, and a naive timestamp on a
UTC-everywhere service is worth a deliberate decision either way.

## Approach

This is an audit first. Remediation, if any, is scoped by what it finds.

1. **Compare types directly**, since `alembic check` structurally cannot. Reflect production's
   `information_schema.columns` and diff it against the ORM metadata column by column — a short
   script, not a migration. A restored **schema-only** copy is sufficient (types are schema, not
   data), so this needs no production write access and no large dump.
2. **Exclude the vector columns explicitly** rather than by accident. `Verse.embedding`,
   `Passage.embedding` and `Topic.embedding` are environment-dependent by design; the audit should
   report them as "expected difference" rather than omit them silently.
3. **Classify each finding**: faithful-but-questionable (model and database agree, but the choice is
   wrong — e.g. a naive timestamp), versus genuine drift (model and database disagree).
4. **Remediate separately.** Anything requiring an `ALTER TABLE ... TYPE` is a rewrite of the column
   and belongs in its own reviewed revision with its own lock analysis — `verses` is ~400k rows.

Consider whether the audit is worth keeping as a CI job. A periodic type comparison that tolerates
the known vector difference would close the gap permanently, rather than leaving it to be
rediscovered. That is a judgement call for whoever runs this: a bespoke checker is a thing to
maintain.

## Acceptance Criteria

- [ ] Type comparison run against a copy of production; full output recorded in the PR
- [ ] Vector columns reported as expected-difference, not silently skipped
- [ ] Each difference classified: faithful-but-questionable, or genuine drift
- [ ] `translations.created_at` resolved explicitly — `timestamptz` like its siblings, or documented
      as intentionally naive with the reason
- [ ] Any `ALTER TABLE ... TYPE` deferred to its own revision with a lock/rewrite assessment
- [ ] Decision recorded on whether the comparison becomes a recurring CI check
- [ ] `api/alembic/README.md` invariant #2 updated to state the consequence plainly: `compare_type=False`
      means **no** type is ever compared, not just vectors

## Out of Scope

- Turning `compare_type=True`. The vector dimensions make it unusable as a gate; anything better
  needs a custom `compare_type` callable that special-cases `Vector`, which is its own decision.
- Structural drift — BITB-093, done.
- The five legacy non-ORM tables — BITB-091; they have no models to compare types against.

## Related

- BITB-093 — the structural reconciliation this completes
- BITB-089 — the adoption sequence that surfaced the gap
- `api/alembic/env.py` (`compare_type=False`), `api/alembic/README.md` invariant #2
- `scripts/init.sql`, `api/scripture/models.py`, `api/feedback/models.py`

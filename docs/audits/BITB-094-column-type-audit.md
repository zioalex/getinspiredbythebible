# BITB-094: Column-Type Audit — ORM Models vs. Database

**Story:** `docs/BACKLOG_STORIES/BITB-094-audit-column-types-against-production.md`
**Status:** tooling built, static pass complete, dynamic pass run against a
fresh migrated database. **The authoritative run — against a schema-only
restore of real production — is still outstanding** (see "What's still
missing" below); this audit does not close that gap on its own.
**Date:** 2026-09-10

## Why this exists

`api/alembic/env.py` sets `compare_type=False`, deliberately: `Vector(dim)`
is 1024 locally / in CI (ollama) and 1536 in production (`azure_openai`), and
turning type comparison on would make `alembic check` report drift in every
environment purely because two environments run different embedding
providers. The cost is that `compare_type=False` suppresses **all** column
type comparison, not just the three Vector columns — no `alembic check` run
has ever verified that a `varchar(50)` is still a `varchar(50)`, or that a
`timestamp` hasn't quietly become a `timestamptz` (or failed to). BITB-093
reconciled *structure*; this story is the first real look at *types*.

## What this audit is (and is not)

The story's acceptance criteria call for "type comparison run against a
schema-only copy of production, full output recorded in the PR." **This
sandbox has no network access to production or any real Postgres instance**
— that's a environment constraint, not a shortcut taken here. Rather than
fake or simulate a production connection, this audit does two honestly
labeled substitute passes:

1. **Static pass** — hand comparison of `scripts/init.sql` (established by
   BITB-093 as a faithful description of production's real column types for
   every table it declares) against the ORM models, column by column, for
   every table both sides describe.
2. **Dynamic pass** — a real, reusable tool
   (`scripts/audit_column_types.py`) built and run for real against a
   throwaway local Postgres 16 database created fresh by `alembic upgrade
   head`. This proves the tool works and that the migration history is
   internally consistent with the models — which is close to trivial, since
   both trace back to the same model definitions. **It does not, on its own,
   prove anything about production**, which may still carry manual changes
   `scripts/init.sql` and the Alembic history don't know about.

A maintainer with real production access still needs to run
`scripts/audit_column_types.py` against a schema-only restore of production
(`docs/HOW-TO-BACKUP-RESTORE-DATABASE.md` Scenario C, `make
db-backup-schema` / `make db-restore-local`) before this story's acceptance
criterion #1 can be marked done outright. See "What's still missing."

---

## 1. Static pass — `scripts/init.sql` vs. the ORM models

Scope: every table `scripts/init.sql` declares that also has an ORM model —
`translations`, `books`, `chapters`, `verses`, `passages`, `topics`,
`feedback`, `contact_submissions`. `blocked_message_samples` and `verse_tsv`
are **excluded by design**, not overlooked: both were created purely by
Alembic/`create_all()`, never by `scripts/init.sql` (BITB-093), so they
trivially match the models by construction — there is no independent
description of them to compare against. The five legacy non-ORM tables
(`sessions`, `verse_topics`, `rate_limit_hits`, `rate_limit_sessions`,
`schema_migrations`) have no ORM model at all and are out of scope per
BITB-091.

Classification legend:

- **match** — `init.sql` and the model declare the same type.
- **faithful-but-questionable** — `init.sql` and the model agree with each
  other, but the choice itself looks wrong.
- **expected difference** — the three Vector embedding columns, whose
  dimension is legitimately environment-dependent (see above); not counted
  toward match/drift totals.
- **genuine drift** — `init.sql` and the model disagree.

### `translations`

| column | `init.sql` | model (`api/scripture/models.py`) | classification |
| --- | --- | --- | --- |
| `code` | `VARCHAR(20)` PK | `String(20)` PK | match |
| `name` | `VARCHAR(100) NOT NULL` | `String(100)` | match |
| `language` | `VARCHAR(50) NOT NULL` | `String(50)` | match |
| `language_code` | `VARCHAR(10) NOT NULL` | `String(10)` | match |
| `description` | `TEXT` | `Text`, nullable | match |
| `source_url` | `TEXT` | `Text`, nullable | match |
| `license` | `VARCHAR(100) DEFAULT 'Public Domain'` | `String(100)` | match |
| `is_default` | `BOOLEAN DEFAULT FALSE` | `Boolean` | match |
| `created_at` | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` (no tz) | `DateTime` (no tz) | **faithful-but-questionable** — see decision below |

8 match, 1 faithful-but-questionable, 0 drift.

### `books`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `name` | `VARCHAR(50) NOT NULL UNIQUE` | `String(50)`, unique | match |
| `abbreviation` | `VARCHAR(10) NOT NULL` | `String(10)` | match |
| `testament` | `VARCHAR(20) NOT NULL` | `String(20)` | match |
| `position` | `INTEGER NOT NULL` | `Integer` | match |

5 match, 0 questionable, 0 drift.

### `chapters`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `book_id` | `INTEGER NOT NULL` | `Integer` | match |
| `number` | `INTEGER NOT NULL` | `Integer` | match |

3 match, 0 questionable, 0 drift.

### `verses`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `book_id` | `INTEGER NOT NULL` | `Integer` | match |
| `chapter_id` | `INTEGER NOT NULL` | `Integer` | match |
| `chapter_number` | `INTEGER NOT NULL` | `Integer` | match |
| `verse_number` | `INTEGER NOT NULL` | `Integer` | match |
| `text` | `TEXT NOT NULL` | `Text` | match |
| `translation` | `VARCHAR(20) NOT NULL DEFAULT 'kjv'` | `String(20)` | match |
| `embedding` | `vector(1024)` | `Vector(settings.embedding_dimensions)` | **expected difference** |

7 match, 0 questionable, 1 expected difference, 0 drift.

### `passages`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `title` | `VARCHAR(200) NOT NULL` | `String(200)` | match |
| `start_book_id` | `INTEGER NOT NULL` | `Integer` | match |
| `start_chapter` | `INTEGER NOT NULL` | `Integer` | match |
| `start_verse` | `INTEGER NOT NULL` | `Integer` | match |
| `end_chapter` | `INTEGER NOT NULL` | `Integer` | match |
| `end_verse` | `INTEGER NOT NULL` | `Integer` | match |
| `text` | `TEXT NOT NULL` | `Text` | match |
| `topics` | `VARCHAR(500)` | `String(500)`, nullable | match |
| `embedding` | `vector(1024)` | `Vector(settings.embedding_dimensions)` | **expected difference** |

9 match, 0 questionable, 1 expected difference, 0 drift.

### `topics`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `name` | `VARCHAR(100) NOT NULL UNIQUE` | `String(100)`, unique | match |
| `description` | `TEXT` | `Text`, nullable | match |
| `parent_id` | `INTEGER` (self-FK) | `Integer`, nullable (self-FK) | match |
| `embedding` | `vector(1024)` | `Vector(settings.embedding_dimensions)` | **expected difference** |

4 match, 0 questionable, 1 expected difference, 0 drift.

### `feedback`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `created_at` | `TIMESTAMP WITH TIME ZONE DEFAULT NOW()` | `DateTime(timezone=True)` | match |
| `message_id` | `UUID NOT NULL` | `PGUUID(as_uuid=True)` | match |
| `session_id` | `VARCHAR(255)` | `String(255)`, nullable | match |
| `rating` | `VARCHAR(10) NOT NULL CHECK (...)` | `String(10)` | match |
| `comment` | `TEXT` | `Text`, nullable | match |
| `user_message` | `TEXT` | `Text`, nullable | match |
| `assistant_response` | `TEXT` | `Text`, nullable | match |
| `verses_cited` | `JSONB` | `JSONB`, nullable | match |
| `model_used` | `VARCHAR(100)` | `String(100)`, nullable | match |
| `response_time_ms` | `INTEGER` | `Integer`, nullable | match |

11 match, 0 questionable, 0 drift.

**Note:** the model also declares `reason: String(40)`, added to production
by `scripts/migrations/006_add_feedback_reason.py` (`ALTER TABLE feedback ADD
COLUMN IF NOT EXISTS reason VARCHAR(40)`) — a hand-rolled migration that ran
*after* `scripts/init.sql` was written and was never backported into it.
`init.sql` therefore has no `reason` column to compare against; this is a
completeness gap in `init.sql` (already implied by BITB-091's scope, which
left the legacy `scripts/migrations/` system frozen as historical record),
not a type disagreement, so it isn't counted in either bucket above. The
type that *is* declared (`VARCHAR(40)` in migration 006) matches the model
(`String(40)`) exactly.

### `contact_submissions`

| column | `init.sql` | model | classification |
| --- | --- | --- | --- |
| `id` | `SERIAL` PK | `Integer` PK | match |
| `created_at` | `TIMESTAMP WITH TIME ZONE DEFAULT NOW()` | `DateTime(timezone=True)` | match |
| `email` | `VARCHAR(255)` | `String(255)`, nullable | match |
| `subject` | `VARCHAR(50) NOT NULL CHECK (...)` | `String(50)` | match |
| `message` | `TEXT NOT NULL` | `Text` | match |
| `session_id` | `VARCHAR(255)` | `String(255)`, nullable | match |
| `user_agent` | `TEXT` | `Text`, nullable | match |
| `status` | `VARCHAR(20) DEFAULT 'new' CHECK (...)` | `String(20)` | match |

7 match, 0 questionable, 0 drift.

### Static pass summary

| table | match | faithful-but-questionable | expected difference | genuine drift |
| --- | --- | --- | --- | --- |
| translations | 8 | 1 | 0 | 0 |
| books | 5 | 0 | 0 | 0 |
| chapters | 3 | 0 | 0 | 0 |
| verses | 7 | 0 | 1 | 0 |
| passages | 9 | 0 | 1 | 0 |
| topics | 4 | 0 | 1 | 0 |
| feedback | 11 | 0 | 0 | 0 |
| contact_submissions | 7 | 0 | 0 | 0 |
| **Total** | **54** | **1** | **3** | **0** |

**Finding: zero genuine drift.** The only faithful-but-questionable case is
the one BITB-093 already flagged — `translations.created_at` as a naive
`TIMESTAMP`. Every other column across all 8 ORM-owned, `init.sql`-declared
tables agrees between the SQL and the models. This also cross-checks `r0001`
(the Alembic baseline): grepping every revision under `api/alembic/versions/`
for `alter_column`/`ALTER COLUMN` finds none — the baseline's column
definitions are the only ones that have ever existed in the Alembic history,
so `r0001` and `init.sql` were compared implicitly by transitivity as well.

Cross-checked independently by the dynamic pass, below: a database built
purely from `alembic upgrade head` (i.e. from the models, transitively)
shows **zero** type diffs against the models themselves when compared with
`compare_type=True` — consistent with, though not a substitute for, this
static result.

---

## 2. Dynamic pass — `scripts/audit_column_types.py`

### The tool

`scripts/audit_column_types.py` (new) runs Alembic's own autogenerate
comparison machinery — the same code path `alembic check` uses internally
(`RevisionContext.run_autogenerate()` inside an `EnvironmentContext` that
loads and executes `api/alembic/env.py` by file path) — with
`EnvironmentContext.configure` monkeypatched, only for the duration of the
script, to force `compare_type=True`. `env.py` on disk is never modified.
Because `env.py` is executed for real rather than copied from, the tool's
`target_metadata` / `include_name` / `include_object` /
`compare_server_default` are env.py's actual objects — they cannot drift
from the real migration environment.

Diffs matching `("modify_type", …)` on `verses.embedding`,
`passages.embedding` or `topics.embedding` are bucketed and printed as
*expected difference (environment-dependent embedding dimension)*; every
other diff prints as *flagged — needs human triage*. The script always exits
`0` on a successful comparison (it's a report tool, not a gate) and exits
non-zero only on a connection/usage error. It is deliberately **not** wired
into any CI workflow — see the CI-gate decision below.

Unit tests: `api/tests/test_audit_column_types.py`, 19 cases over the pure
classifier/bucketing/flattening/formatting logic using fake diff tuples — no
live database needed. All pass (see "Validation" below).

### The run

Setup, following `api/alembic/README.md`'s documented commands and the
`throwaway_database_url` fixture pattern in `api/tests/test_alembic_migrations.py`:

```
$ sudo pg_ctlcluster 16 main start
$ createdb (as postgres) bitb094_audit
$ cd api
$ DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/bitb094_audit" \
  EMBEDDING_PROVIDER=ollama EMBEDDING_MODEL=mxbai-embed-large EMBEDDING_DIMENSIONS=1024 \
  python3 -m alembic upgrade head
```

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> r0001, baseline schema
INFO  [alembic.runtime.migration] Running upgrade r0001 -> r0002, pipeline probe: prove a revision reaches production via CI (BITB-089)
INFO  [alembic.runtime.migration] Running upgrade r0002 -> r0003, remove the pipeline probe comment (BITB-089)
INFO  [alembic.runtime.migration] Running upgrade r0003 -> r0004, add verse_tsv side table for verse full-text search (BITB-096)
INFO  [alembic.runtime.migration] Running upgrade r0004 -> r0005, add search_eval_ro read-only role for the nightly search-eval harness (BITB-101)
INFO  [alembic.runtime.migration] Running upgrade r0005 -> r0006, grant search_eval_ro access to topic-boosting tables (BITB-104)
```

Then the audit itself:

```
$ DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/bitb094_audit" \
  EMBEDDING_PROVIDER=ollama EMBEDDING_MODEL=mxbai-embed-large EMBEDDING_DIMENSIONS=1024 \
  python3 ../scripts/audit_column_types.py
```

**Literal captured output:**

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.schemas
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.tables
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.types
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.constraints
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.defaults
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.comments
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.checkconstraint_byname
INFO  [alembic.ddl.postgresql] Detected sequence named 'verses_id_seq' as owned by integer column 'verses(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'topics_id_seq' as owned by integer column 'topics(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'passages_id_seq' as owned by integer column 'passages(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'feedback_id_seq' as owned by integer column 'feedback(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'chapters_id_seq' as owned by integer column 'chapters(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'books_id_seq' as owned by integer column 'books(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'contact_submissions_id_seq' as owned by integer column 'contact_submissions(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'blocked_message_samples_id_seq' as owned by integer column 'blocked_message_samples(id)', assuming SERIAL and omitting
BITB-094 column-type audit against postgresql://postgres:***@127.0.0.1:5432/bitb094_audit
0 total structural+type difference(s) found (compare_type forced on for this run; env.py's own table/index allowlist still applies).

No embedding-dimension difference found. Expected when run against a database created by `alembic upgrade head` itself (see the module docstring) -- both sides trace back to the same EMBEDDING_DIMENSIONS. A real production restore running a different embedding provider would show one here.

No flagged differences outside the expected embedding-dimension bucket.
```

Exit code: `0`.

**Interpretation.** Zero diffs is the expected result for this run, not a
surprise: the throwaway database was created entirely from
`alembic upgrade head`, i.e. from the models themselves, with the local
`EMBEDDING_DIMENSIONS=1024` matching the dimension `r0001` hardcoded for the
Vector columns. This run mainly validates the *tool* — it proves
`compare_type=True` really is active and the diff/bucketing logic behaves —
rather than proving anything new about production.

**Proof the type-detection path is real** (not included in the committed
output above, done as a one-off check during tool development): temporarily
setting `settings.embedding_dimensions = 1536` in-process against the same
1024-dimension throwaway database produced exactly the expected diff —

```
[('modify_type', None, 'passages', 'embedding', {...}, VECTOR(dim=1024), VECTOR(dim=1536))]
[('modify_type', None, 'topics', 'embedding', {...}, VECTOR(dim=1024), VECTOR(dim=1536))]
[('modify_type', None, 'verses', 'embedding', {...}, VECTOR(dim=1024), VECTOR(dim=1536))]
```

— and separately, manually widening `translations.created_at` to
`timestamptz` in the throwaway database and re-running produced:

```
FLAGGED -- needs human triage -- 1:
  modify_type      translations.created_at: TIMESTAMP(timezone=True) -> DateTime()
```

confirming both that real type drift is caught and correctly flagged, and
that the three embedding columns are correctly bucketed as expected rather
than flagged, without the classifier being fooled by column name alone (a
hypothetical `embedding` column on an unrelated table would still flag — see
`api/tests/test_audit_column_types.py::TestIsExpectedEmbeddingDiff::test_embedding_named_column_on_wrong_table_is_not_expected`).

### Validation

```
$ cd api && python3 -m pytest tests/test_audit_column_types.py -v
...
19 passed in 0.04s
```

`black --check` and `ruff check` run clean on both new Python files (see
commit for the exact invocations).

---

## `translations.created_at` — decision

**Recommendation: convert to `TIMESTAMP WITH TIME ZONE` (`DateTime(timezone=True)`),
for consistency with `feedback.created_at` / `contact_submissions.created_at`
on a UTC-everywhere service.** The static pass confirms this is
faithful-but-questionable, not drift — `scripts/init.sql` and the model agree
with each other, and the column's actual values are always UTC in practice
(`CURRENT_TIMESTAMP` / `datetime.utcnow()`), so nothing is *wrong* today. But
a naive timestamp is a standing ambiguity: nothing in the column's type says
which zone `created_at` is in, and the three other `created_at`/`expires_at`
columns in this same schema all say so explicitly. Leaving one inconsistent
column around is exactly the kind of thing that becomes a bug the day
someone compares it against a timezone-aware value or serializes it across a
DST boundary.

**Not performed in this story.** Per the acceptance criterion, any
`ALTER TABLE ... TYPE` is deferred to its own reviewed revision with a
lock/rewrite assessment. Filed as **BITB-127**
(`docs/BACKLOG_STORIES/BITB-127-translations-created-at-timezone.md`), P3/S —
`translations` is a 13-row reference table, so the change itself is expected
to be low-risk, but `docs/MIGRATION_GUIDELINES.md`'s locking discipline
applies mechanically regardless of table size, and BITB-127 asks explicitly
for the row-count/access-pattern check to happen before, not instead of,
following it.

---

## Decision: not a CI gate (yet)

**`scripts/audit_column_types.py` is deliberately not wired into any CI
workflow.** Rationale:

- The dynamic pass has only been validated against a database created by
  `alembic upgrade head` itself — a near-tautological check (see
  "Interpretation" above). It has **not yet been run against real production
  data**, which is the one case that would actually prove the tool finds
  real drift in the wild rather than only in a contrived test (as the
  manual embedding-dimension and `translations.created_at` checks above
  demonstrate it can).
- `compare_type=False` exists in `env.py` specifically because an
  under-validated type-comparison signal flapping CI is a known failure mode
  for this exact class of tool (the Vector-dimension case). Wiring this
  script into CI as a blocking gate before it's proven stable against
  production risks reproducing precisely that problem one layer up.
- The audit/report design (always exits 0, prints rather than fails) reflects
  this: it's built to be run and read by a human today, not to gate a merge.

**Revisit this decision** once a maintainer has run
`scripts/audit_column_types.py` against a real schema-only production
restore and it's shown to be stable (no false positives from reflection
quirks, comment/collation noise, etc.) across at least one such run.

---

## What's still missing

This audit satisfies BITB-094's acceptance criteria as far as this sandboxed
environment allows, but **one thing remains genuinely open**, and the
backlog entry for BITB-094 stays 🚧 In Progress (not ✅ Done) because of it:

- **No comparison has run against real production data.** The static pass
  gives strong indirect evidence (production's schema, as described by
  `scripts/init.sql`, has already been independently reconciled against the
  models in BITB-093), and the dynamic pass proves the tool itself works.
  Neither is the same as pointing `scripts/audit_column_types.py` at a
  schema-only restore of production and reading its actual output. A
  maintainer with real Azure/production access needs to do that — see the
  module docstring in `scripts/audit_column_types.py` and
  `docs/HOW-TO-BACKUP-RESTORE-DATABASE.md` Scenario C
  (`make db-backup-schema` / `make db-restore-local`) — before this story can
  be marked ✅ Done.

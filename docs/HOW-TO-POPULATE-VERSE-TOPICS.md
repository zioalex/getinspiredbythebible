# How to Populate `verse_topics` (BITB-044)

Topic-based search-ranking boost was built under BITB-018: query-side topic
detection (`api/chat/topics.py`), the boosted ranking queries
(`api/scripture/repository.py`), and the `verse_topics` junction table +
seeded `topics` rows (`scripts/migrations/004_add_topic_boosting_schema.sql`)
all existed — but nothing ever inserted a row into `verse_topics`. The
`LEFT JOIN` against it always returned zero matches, so
`topic_boosting_enabled` was a silent no-op even when set to `true`. This doc
covers `scripts/populate_verse_topics.py`, which fills that gap.

See also:
[`api/chat/topic_tagging.py`](../api/chat/topic_tagging.py),
[`api/chat/topics.py`](../api/chat/topics.py),
[`docs/BACKLOG_STORIES/BITB-044-populate-verse-topics.md`](BACKLOG_STORIES/BITB-044-populate-verse-topics.md).

## What it does

For each translation whose language is one of the 7 the keyword map covers
(`en`, `it`, `de`, `es`, `fr`, `pt`, `ar`), the script scans every verse's
text against that language's topic keywords
(`TOPIC_KEYWORDS_BY_LANGUAGE` in `api/chat/topics.py`) and inserts a
`(verse_id, topic_id)` row into `verse_topics` for each match. Matching is
word-boundary based with a small bounded suffix allowance (so "trust"
matches "trusted" without every inflected form needing to be spelled out in
the map) — see the module docstring in `api/chat/topic_tagging.py` for the
exact algorithm and why it's stricter than the query-side `detect_topics()`.

Translations in unsupported languages (`ru`, `zh`, `hi`, `ko`, ...) are
skipped and reported — there's no keyword vocabulary to tag them with.

**This script does not enable topic boosting.** `topic_boosting_enabled`
stays `false` and `topic_boost_factor` is untouched. It only makes the
feature *possible* to validate — see "Not covered by this script" below.

## Idempotency

`(verse_id, topic_id)` is the table's primary key, so a plain re-run only
adds pairs that aren't already there — running it twice inserts 0 new rows
the second time. Use `--replace` to delete and re-seed a translation's rows
first (e.g. after editing `TOPIC_KEYWORD_MAP` or `CORPUS_KEYWORD_DENYLIST`).

## Automated population in CI (BITB-105)

The deploy pipeline runs this for you. `.github/workflows/azure-deploy.yml`'s
`seed-database-post` job has a **Populate Verse Topics** step that invokes
`scripts/populate_verse_topics.py` with no `--translation` filter, so every
supported-language translation is (re-)tagged on each seeding run. That is
safe and self-healing precisely because of the idempotency above: a plain
re-run backfills anything a previous run or a single-translation dispatch
missed, and inserts nothing where rows already exist.

It fires on the same trigger as seeding itself — a change matching the
`bible_scripts` path filter (which includes `scripts/translations.py`, so
adding a translation tags it in the same run) or a manual `workflow_dispatch`
with `skip_database_seed=false`.

Two placement details that matter:

- The step runs **before** `Generate Embeddings`. That step has no
  `continue-on-error`, so anything downstream of it is skipped when Azure
  OpenAI misbehaves — tagging placed after it would be silently skipped by an
  unrelated outage, which is the original BITB-105 bug all over again.
- The job installs `pydantic`/`pydantic-settings` for this step. Both topic
  scripts import `api/chat/topics.py`, which pulls in `config.Settings`;
  without those packages the step dies at import time.

The population step does not touch the migration window — it is downstream of
`run-migrations` and `deploy` (BITB-097 ordering).

## Coverage check (drift and emptiness alarm)

`scripts/check_verse_topic_coverage.py` runs immediately after population (and
with `if: always()`, so it still reports when population failed or never ran).
It reads `verse_topics` **back out of the database** rather than trusting the
population run's own tally — a check built on that tally would pass even if
every insert silently did nothing, which is the exact failure class here.

Per supported-language translation it reports one of six statuses:

| Status | Alarms | Meaning |
|---|---|---|
| `ok` | no | Coverage inside the band |
| `empty` | **yes** | Verses loaded, zero topic rows — the BITB-105 condition |
| `below_floor` | **yes** | Coverage under the floor (default 5%) |
| `above_ceiling` | **yes** | Coverage over the ceiling (default 60%) |
| `small_sample` | no | Under 1,000 verses — the percentage isn't meaningful yet |
| `no_verses` | no | Translation not seeded; the existing verse-count gate owns this |

**Thresholds.** BITB-044 measured 18.3% (KJV/en) and 12.3% (Luther 1912/de).
The 5% floor sits well below both on purpose: five of the seven supported
languages have never been validated against a real corpus (BITB-106), so the
floor exists to catch zero and near-total collapse, not to police quality.
The 60% ceiling is a *different* metric from the per-topic 25% denylist
guideline above — overall coverage stacks 13 topics, so ~18% overall is
consistent with no single topic above ~3.2%.

**Exit code.** 0 even when it alarms, unless `--strict`. This is the recorded
blast-radius decision: a tagging failure degrades ranking quality behind a
feature flag, never correctness or availability, so it alarms and does not
fail the deploy. Violations surface as GitHub `::warning::` annotations plus a
per-translation table in the job step summary.

### Negative rehearsal

An emptiness check nobody has seen fire is not yet known to work. To prove the
whole path — query, classify, annotate, exit code — actually fires:

```bash
# Force every translation to violate the floor.
python scripts/check_verse_topic_coverage.py --floor 100 --strict   # expect: warnings + exit 1
python scripts/check_verse_topic_coverage.py --floor 100            # expect: same warnings, exit 0
```

`api/tests/test_verse_topic_coverage_check.py` is the automated equivalent: it
asserts the zero-rows case alarms, that alarms render as `::warning::` lines,
and that the default exit code stays 0 — all over synthetic counts, no
database needed.

## Manual usage (backfills and one-offs)

The pipeline runs this for you on every seed (above); the manual invocation
stays for backfills, `--replace` re-tags, and dry-run tuning.

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host/db?ssl=require"  # pragma: allowlist secret

# Always dry-run first and read the coverage report before writing anything.
python scripts/populate_verse_topics.py --dry-run --verbose

# Populate every supported-language translation.
python scripts/populate_verse_topics.py

# Just one or two translations.
python scripts/populate_verse_topics.py --translation kjv --translation web

# Re-seed a translation after a keyword-map edit.
python scripts/populate_verse_topics.py --translation kjv --replace
```

Flags: `--dry-run`, `--translation CODE` (repeatable), `--replace`,
`--limit N` (debugging — only the first N verses per translation),
`--batch-size N` (default 5000), `-v`/`--verbose` (also prints the top
contributing keywords per topic).

## Reading the coverage report

```
kjv (en): 31,100 verses, 5,695 tagged (18.3%), 6,537 pairs -> 6,537 inserted, 0 already present
    anger             485  ( 1.6%)
    anxiety            27  ( 0.1%)
    ...
```

- **tagged**: verses that matched at least one topic.
- **pairs**: total `(verse, topic)` matches (a verse can match more than
  one topic).
- Per-topic lines show what share of the translation's verses matched that
  topic. If any topic exceeds **25%**, that's a sign a keyword is too
  generic for corpus-scale matching (fine for a single user message, noisy
  across ~31k verses) — see "Tuning the denylist" below.

## Tuning the denylist

`CORPUS_KEYWORD_DENYLIST` in `api/chat/topic_tagging.py` excludes specific
keywords from **corpus** tagging only; `detect_topics()` on the query side
always keeps the full vocabulary, since a false positive there just adds an
extra boost term to one message.

As of this script's introduction, a dry run against the real KJV (`en`,
31,100 verses) and Luther 1912 (`de`, 31,102 verses) corpora found no topic
above ~3.2% coverage and no single keyword above ~2% — well under the 25%
guideline — so the denylist starts empty. The other supported languages
(`it`, `es`, `fr`, `pt`, `ar`) have not been validated the same way in this
repo (no local corpus data was available); run `--dry-run --verbose` for
those translations and check the top-keyword breakdown before trusting an
empty denylist for them too.

To add an entry: run `--dry-run --verbose`, find the offending
`topic: keyword count (%)`, add it to `CORPUS_KEYWORD_DENYLIST` with a
comment recording the observed count, then re-run with `--replace`.

## Not covered by this script (deliberate follow-ups)

- **LLM-assisted tagging** to catch verses the keyword scan misses (thematic
  matches with no literal keyword overlap). The keyword-seeded rows this
  script writes and any future LLM-sourced rows are composable — both write
  into the same table via `ON CONFLICT DO NOTHING`.
- **Validating against the BITB-043 golden eval set** and tuning
  `topic_boost_factor`.
- **Enabling `topic_boosting_enabled` in production** — do this only after
  the golden-set validation above.
- **Keyword-map edits do not re-trigger tagging.** `api/chat/topics.py` and
  `api/chat/topic_tagging.py` are deliberately *not* in the `bible_scripts`
  path filter: a plain re-run is additive and cannot retract rows for a
  keyword you just denylisted, so auto-triggering on a map edit would produce
  a half-applied re-tag that looks like it worked. A map edit needs a manual
  `--replace` run for now.
- **Per-language coverage floors.** The check uses a single 5% floor because
  five of the seven supported languages are unmeasured; tighten it under
  BITB-106.
- **A scheduled coverage check independent of deploys.** Today the alarm only
  fires when a seed runs, so a truncation or a bad restore stays invisible
  until the next `bible_scripts` change.
- A `source` provenance column on `verse_topics` so `--replace` doesn't
  discard rows from a future non-keyword tagging pass — tracked separately;
  not needed while keyword-seeding is the only source.

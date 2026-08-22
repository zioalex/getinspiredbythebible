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

## Usage

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
- **CI/deploy wiring** (e.g. running this automatically alongside the
  existing `seed-database` matrix job) — this is a manual/on-demand script
  for now.
- A `source` provenance column on `verse_topics` so `--replace` doesn't
  discard rows from a future non-keyword tagging pass — tracked separately;
  not needed while keyword-seeding is the only source.

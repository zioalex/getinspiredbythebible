# BITB-069: Add Menge-Bibel and Make It the German Default

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — translation quality/familiarity for the German audience
**Size:** M (2-3 days — new markup conversion pipeline, not a simple getBible pull)
**Created:** 2026-07-19
**Source:** Product idea — swap in a more highly-regarded German translation than Luther 1912

## User Story

**As a** German-speaking user,
**I want** the default Bible to be the Menge-Bibel (Hermann Menge's translation),
**so that** I get a translation known for precision and helpful explanatory glosses, rather than
the currently-default Luther 1912.

## Background

[BITB-046](BITB-046-german-translations-luther-elberfelder.md) made **Luther 1912** the German
default (`LANGUAGE_TRANSLATIONS["de"]` in `api/utils/language.py`) after beta feedback that
Schlachter 1951 felt unfamiliar to most German readers. This story proposes going further: add the
**Menge-Bibel** as a third German translation and promote it to default, keeping Luther 1912 and
Schlachter 1951 available as alternatives.

## Source Research

**Repo:** [`renehamburger/Menge-Bibel`](https://github.com/renehamburger/Menge-Bibel) — "Eine
Markdown-Version der gemeinfreien Menge-Bibel" (17 stars, actively maintained since 2018).

| Item | Finding |
|---|---|
| License | **CC0 1.0 Universal** — public-domain dedication, no attribution legally required (even more permissive than the "Public Domain" label already used for `luther1912`/`schlachter`) |
| Canon | 66 books, full Protestant canon — 39 OT files under `Bibel/Altes Testament/`, 27 NT files under `Bibel/Neues Testament/`. No deuterocanon. |
| Format | **Not** a getBible JSON feed — getBible's translation manifest has no Menge entry (only `schlachter`, `luther1545`, `elberfelder`, `elberfelder1905` for German). Menge ships as one Markdown file per book. |
| Markdown structure | Editorial section headings (`##`/`###`/`####` — Menge's translation includes descriptive subheadings unique to this edition), chapter markers as `__N__`, verse numbers as inline `<sup>N</sup>` tags (not one verse per line), footnote markers as `<sup title="...">&#x2732;</sup>` (translator's explanatory notes), `<blockquote>` nesting for poetic indentation (e.g. Psalms) |

This means Menge **cannot** be loaded via the existing getBible download path — it needs a
committed, pre-converted JSON file, same mechanism as `luther1912.json` and `hindi.json`
(`source: "manual"`, `url: None`, see `data/bible/LICENSES.md`). Unlike those two source formats
(flat verse arrays / USFX XML), Menge's Markdown mixes verse text with editorial markup inline, so
converting it requires:

- Stripping heading lines, footnote `<sup title=...>` tags, and `<blockquote>` wrapper markup
- Splitting on `__N__` for chapter boundaries and `<sup>N</sup>` for verse boundaries
- Reflowing wrapped/poetic lines within a verse into a single text string
- **Keeping** Menge's parenthetical interpretive words (e.g. "(von allem), was geworden ist" in
  John 1:3) as running text — those parentheses are a hallmark of this translation's style, not
  apparatus to strip

This is meaningfully more parsing work than a getBible JSON pull, but it's the same category of
one-time conversion already done for `hindi.json` (USFX XML → flat JSON, documented in
`data/bible/LICENSES.md`), so it's well-precedented, not novel risk.

### Book name differences

Menge uses different German book names than the existing `ENGLISH_TO_GERMAN` map (shared by
`schlachter` and `luther1912`) for 9 of 66 books — confirmed by diffing the Menge README's book
list against `api/utils/translation_registry.py`:

| English | Luther/Schlachter (`ENGLISH_TO_GERMAN`) | Menge |
|---|---|---|
| Genesis | 1. Mose | **Genesis** |
| Exodus | 2. Mose | **Exodus** |
| Leviticus | 3. Mose | **Levitikus** |
| Numbers | 4. Mose | **Numeri** |
| Deuteronomy | 5. Mose | **Deuteronomium** |
| Ruth | Ruth | **Rut** |
| Esther | Esther | **Ester** |
| Song of Solomon | Hohelied | **Hoheslied** |
| Zephaniah | Zephanja | **Zefanja** |

The remaining 57 books (incl. all NT books — Matthäus, Markus, ..., Offenbarung) match exactly.
Consequence: Menge needs its **own** `ENGLISH_TO_MENGE` dict in `translation_registry.py` — it
cannot reuse `GERMAN_BOOK_NAMES` as-is. Build it by copying `ENGLISH_TO_GERMAN` and overriding
these 9 entries.

### Alternative considered

`elberfelder1905` is already hosted on getBible (trivial pull, zero markup-parsing risk) and was
scoped out of BITB-046 only because Luther 1912 was judged sufficient. It remains a lower-effort
fallback if the Menge conversion proves more troublesome than expected, but it doesn't address the
actual goal here (a more contemporary, glossed translation) — Elberfelder 1905 is a literal,
archaic-register translation like Luther, not a change in kind.

## Approach

1. **Conversion script** — `scripts/convert_menge.py` (commit it, unlike the one-off Hindi
   conversion — Menge-Bibel is a live upstream repo that receives typo fixes, so re-running the
   conversion should be cheap):
   - Reads the 66 Markdown files (vendor a snapshot under a scratch/input dir, or fetch via GitHub
     API/raw URLs at conversion time — either way, the *output* JSON is what gets committed)
   - Strips headings, footnote tags, blockquote markup as described above
   - Splits into chapters/verses, reflows poetic line breaks
   - Maps each Markdown filename to its canonical English book name
   - Emits `data/bible/translations/menge.json` in the shape
     `[{"name": "<English book name>", "chapters": [["verse text", ...], ...]}]`
   - Includes a sanity check: 66 books, plausible verse counts per chapter, and a few spot-checked
     verses (e.g. John 3:16, Genesis 1:1, a Psalm with poetic blockquotes) diffed against the
     source Markdown by hand
2. **`scripts/translations.py`** — add `TRANSLATIONS["menge"]`: `name: "Menge-Bibel"`,
   `language: "German"`, `language_code: "de"`, `source: "manual"`, `url: None`,
   `book_names: MENGE_BOOK_NAMES` (derived via reversal like `GERMAN_BOOK_NAMES`), `license: "CC0
   1.0 Universal (Public Domain)"`, `is_default: False` (this flag is global-only — see
   Implementation Notes).
3. **`api/utils/translation_registry.py`** — add `ENGLISH_TO_MENGE` dict, register
   `TRANSLATION_REGISTRY["menge"] = ENGLISH_TO_MENGE`. Add an aliases dict if useful (e.g. users
   who type "1. Mose" while reading Menge should probably still resolve to Genesis).
4. **`api/utils/language.py`**:
   - Add `"menge"` to `TRANSLATION_INFO` (name "Menge-Bibel", short_name "Menge", language_code
     "de")
   - Change `LANGUAGE_TRANSLATIONS["de"]` to `["menge", "luther1912", "schlachter"]` — **this is
     the actual default switch**, per the existing convention that "the first element is the
     default" (see BITB-046 Implementation Notes)
   - Update the inline comment (`# German: Menge-Bibel (default), Luther 1912, Schlachter 1951`)
5. **`api/utils/book_names.py`** — add `menge` to the supported-translations docstring/list.
6. **`data/bible/LICENSES.md`** — new `menge.json` section mirroring the `luther1912.json`/
   `hindi.json` entries: source repo URL, CC0 license, conversion method summary, verse count,
   attribution to Hermann Menge / the `renehamburger` GitHub maintainer.
7. **Data loading (operator step, post-merge):**

   ```bash
   python scripts/load_bible.py --translation menge
   ```

   ~31k verses + embeddings, 30-60 min depending on embedding provider (same as BITB-046
   precedent).

## Acceptance Criteria

- [ ] German translation picker shows **Menge-Bibel** first (new default), then Luther 1912, then
      Schlachter 1951.
- [ ] Menge Bible text + embeddings are loaded and searchable.
- [ ] Verse-detail and chapter views render correctly for Menge, including the 9 renamed books
      (Genesis, Exodus, Levitikus, Numeri, Deuteronomium, Rut, Ester, Hoheslied, Zefanja).
- [ ] All existing tests pass; German-default assertions updated from `luther1912` → `menge`
      across `api/tests/test_language.py`, `api/tests/test_language_detection.py`,
      `api/tests/test_routes_main_coverage.py`, `api/tests/test_translation_readiness.py`.
- [ ] New tests: `ENGLISH_TO_MENGE` completeness/round-trip (mirroring the existing
      `GERMAN_BOOK_NAMES` tests in `api/tests/test_translations.py`), conversion-script output
      spot checks.

## Files / Config

| Item | Location | Change |
|---|---|---|
| Conversion script | `scripts/convert_menge.py` (new) | Markdown → committed JSON converter |
| Committed data | `data/bible/translations/menge.json` (new) | ~31k verses, converter output |
| Translation config | `scripts/translations.py` | add `menge` entry (reuse pattern from `luther1912`) |
| Book-name registry | `api/utils/translation_registry.py` | add `ENGLISH_TO_MENGE`, register in `TRANSLATION_REGISTRY` |
| Language → translations | `api/utils/language.py` `LANGUAGE_TRANSLATIONS["de"]` | `["menge", "luther1912", "schlachter"]` |
| Translation metadata | `api/utils/language.py` `TRANSLATION_INFO` | add `menge` entry |
| Supported list | `api/utils/book_names.py` | register `menge` |
| Provenance | `data/bible/LICENSES.md` | add `menge.json` section |
| DB seed | `scripts/init.sql` | add INSERT row for `menge` |
| Loader | `scripts/load_bible.py` | already supports `--translation <code>` for manual-source configs (no change) |

## Implementation Notes

- The single source of truth for book names is `translation_registry.py` (AGENTS.md pitfall #4) —
  `menge` must map through `ENGLISH_TO_MENGE`, never hardcode names elsewhere.
- `is_default` in `scripts/translations.py`/the `translations` DB table stays `kjv`-only — it's a
  single global flag, not per-language (confirmed: only `kjv` has it `True` today, and no code
  queries it by `language_code`). "Default per language" is governed entirely by the first element
  of `LANGUAGE_TRANSLATIONS["de"]` in `api/utils/language.py` — same convention BITB-046 already
  established.
- Keep Menge's interpretive parentheticals in the verse text (they're the translation's defining
  feature); only strip HTML/Markdown apparatus (headings, footnote `<sup>` tags, blockquote tags).
- Verify the verse count/canon boundaries against a second reference (e.g. compare chapter/verse
  counts to the existing `luther1912.json`) before committing — silent verse-splitting bugs in a
  hand-written Markdown parser are the main risk here.

## Testing

- `api/tests/test_translations.py` — add config test for `menge` (mirroring the existing
  `schlachter`/`luther1912` assertions); update any translation-count assertions.
- `api/tests/test_language.py` / `test_language_detection.py` — update German-default assertions
  (`get_translation_for_language("de")`, `detect_translation(...)`, `resolve_translation(...)`)
  from `luther1912` → `menge`.
- `api/tests/test_multilingual_integration.py` — add a `menge` branch.
- New: conversion-script unit tests or a fixture-based regression test that re-parses a small
  sample of the Markdown (e.g. John 1) and asserts exact verse text/count, so future upstream
  Markdown changes don't silently corrupt the committed JSON.

## Related

- [BITB-046: Add German Bible Translations (Luther 1912 + Elberfelder 1871)](BITB-046-german-translations-luther-elberfelder.md)
- Multi-Language / Translation System section in `AGENTS.md`.

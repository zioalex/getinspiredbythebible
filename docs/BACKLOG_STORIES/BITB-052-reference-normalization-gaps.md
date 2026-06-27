# BITB-052: Audit & Close Bible Reference-Normalization Gaps

**Status:** ✅ Done (partial — aliases + case-insensitive normalization; versification offsets and full per-language abbreviation matrix deferred)
**Priority:** P2 (Medium) — correctness/robustness; benefits the whole app, not just the eval
**Size:** M (1-2 days)
**Created:** 2026-06-16
**Parent / related:** BITB-051 (retrieval-eval harness)

## User Story

As the maintainer, I want Bible book/verse references to canonicalize reliably across
**all 11 languages and their common citation variants**, so that the retrieval-eval
metrics (BITB-051) — and the app's own verse linking, which shares the same utility —
don't silently mis-handle references and produce wrong matches or false negatives.

## Problem

Reference canonicalization for the eval harness goes through
`api/search_eval/normalize.py:canonical_book`, which delegates to
`utils.book_names.normalize_book_name` (built from `utils/translation_registry.py`'s
forward maps + `EXTRA_REVERSE_MAPPINGS`) and then patches a few **English-only**
spelling variants. A review of the registry surfaced **uneven, incomplete coverage**:

- **Localized citation / singular forms are inconsistent.** Arabic and Russian include
  singular and abbreviated forms (`مزمور` singular, `Пс` abbrev → Psalms), but Italian
  `Salmo` (singular; the normal way to cite one psalm), German `Psalm` (singular),
  and Spanish/French/Portuguese singular + abbreviations are **missing** — only the
  plural canonical form (e.g. `Salmi`) is mapped. So `"Salmo 23"` fails to canonicalize.
- **Abbreviations** (`Ps`, `Gen`, `Phil`, `1 Cor`, …) are not handled for most languages.
- **Numbered-book variants** (`I Corinthians`, `1st Corinthians`, `1Corinthians`) are not
  normalized.
- **Case / diacritic sensitivity** — localized lookups in `normalize_book_name` are
  exact-case dict lookups (only the English-variant table lower-cases).
- **Versification differences** across translations (verse numbering: Psalm
  superscriptions, Joel/Malachi chapter splits, 3 John, etc.) can offset a verse's
  `chapter:verse` relative to the English-canonical key — independent of book-name
  language. This can mis-score a correct retrieval as a miss.

These gaps are low-impact for BITB-051 today (its `relevant_refs` and the retrieved
references are both English-canonical), but they affect any localized input and the
app's shared verse-linking path, and they undermine confidence in per-language scores.

> **Update (2026-06-19) — concrete reproductions from verse-grounding debugging.**
> `extract_all_references("1 Cor 13:4")`, `"Cant 2:1"`, and `"Songs 2:1"` all return `[]`
> (with *and* without parentheses), while `"Ps 23:1"` works and full names
> (`1 Corinthians`, `Song of Solomon`) work — confirming the abbreviation / numbered-book
> gaps above. Also a **parser-divergence** finding for the "robust matching" scope: the
> frontend verse parser (`frontend/src/lib/versePatterns.ts`) does not support German comma
> separators (`Johannes 3,16`) that the backend (`api/utils/verse_parser.py`) does — the
> three parsers must be reconciled here.

## Scope

In scope:

1. **Audit** coverage per language against `utils/translation_registry.py` +
   `EXTRA_REVERSE_MAPPINGS`: which singular/plural, abbreviation, and citation variants
   exist vs. are missing, per book, per language. Produce a coverage matrix.
2. **Fill the gaps** — add missing localized singular/citation + abbreviation aliases
   (prioritize Psalms and the commonly-cited books), preferably data-driven in
   `translation_registry.py` so reverse maps update automatically.
3. **Robust matching** — make book-name lookup case- and (where safe) diacritic-
   insensitive without introducing collisions; add numbered-book variant handling
   (`I/1/1st`, with/without space).
4. **Versification** — investigate the magnitude of verse-numbering offsets across the
   11 translations; decide and document handling (options: document-only, chapter-level
   match tolerance for affected books, or a small per-translation verse-offset map).
5. **Tests** — table-driven cases across all 11 languages (canonical, singular,
   abbreviation, numbered-book, case/diacritic), plus versification cases for the known
   offending books.

Out of scope:

- Changing the BITB-051 golden-set ref format — it **stays English-canonical**.
- Reworking the translation registry's forward (English→localized) data beyond adding
  reverse-alias coverage.

## Approach

- Start from `utils/book_names.normalize_book_name` / `LOCALIZED_TO_ENGLISH` and
  `EXTRA_REVERSE_MAPPINGS` as the single source of truth; extend there so both the app
  and `search_eval` benefit. Keep `api/search_eval/normalize.py` as a thin consumer.
- Reuse existing reference-parsing logic where present (e.g. `extract_references` in the
  chat path) rather than duplicating regexes.
- Validate the audit against real loaded data (the 11 prod translations) so the coverage
  matrix reflects what's actually queryable.

## Acceptance Criteria

- [ ] Per-language coverage matrix committed (canonical / singular / abbreviation /
      numbered-book variants) identifying every gap.
- [x] Missing high-value localized aliases added (Psalms + commonly-cited books) so e.g.
      `"Salmo 23"`, `"Psalm 23"` (de), `"Ps 23"` all canonicalize to `Psalms 23`.
      Also added: `1 Cor`, `2 Cor`, `Cant`, `Songs`, `Song of Songs`, `Revelations`, etc.
- [x] Case-insensitive matching (`normalize_book_name` now has a case-insensitive fallback),
      with no regressions in `utils/book_names` consumers (verse linking, etc.).
- [ ] Versification offsets quantified and a documented handling decision (with tests for
      the known offending books).
- [ ] Table-driven tests across all 11 languages pass; `search_eval` normalization tests
      still green.

## Files / Config

| Item | Location |
|---|---|
| Localized maps / aliases (source of truth) | `api/utils/translation_registry.py` (`EXTRA_REVERSE_MAPPINGS`) |
| Normalizer | `api/utils/book_names.py` (`normalize_book_name`, `LOCALIZED_TO_ENGLISH`) |
| Eval consumer | `api/search_eval/normalize.py` (`canonical_book`) |
| Reference parsing to reuse | chat reference extraction (`extract_references`) |
| Tests | `api/tests/` (book-name + `test_search_eval_metrics.py`) |

## Related

- **BITB-051** — retrieval-eval harness; surfaced these gaps during P1 review. Its
  golden-set refs stay English-canonical regardless of this work.
- **BITB-040** — verse-detail localized book name (related book-name handling).

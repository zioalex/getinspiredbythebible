# BITB-046: Add German Bible Translations (Luther 1912 + Elberfelder 1871)

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — content breadth for the German audience
**Size:** M (1-2 days, mostly data loading)
**Created:** 2026-06-12
**Source:** Beta tester feedback (Oliver Osthoever, 2026-06-12)

## User Story

**As a** German-speaking user,
**I want** to choose a familiar Bible translation (Luther),
**so that** I'm not limited to Schlachter 1951, which most German readers find unusual.

## Problem

> "Schlachter finde ich als einzige deutsche Bibelversion recht unüblich. Wer liest Schlachter?"

Only Schlachter 1951 is available for German. The tester also asked for the Einheitsübersetzung,
but that — like Luther 1984/2017, NGÜ, and Schlachter 2000 — is **copyrighted** and cannot be
integrated without a licence.

## Copyright Research

| Translation | Status | Source |
|---|---|---|
| Luther 1984 / 2017 (DBG) | ❌ Copyright | — |
| Einheitsübersetzung | ❌ Copyright | — |
| Neue Genfer Übersetzung | ❌ Copyright | — |
| Schlachter 2000 | ❌ Copyright | — |
| **Luther 1912** | ✅ Public domain | `https://api.getbible.net/v2/luther1912.json` |
| **Elberfelder 1905** | ✅ Public domain | `https://api.getbible.net/v2/elberfelder1905.json` (getBible has no 1871 edition; the 1905 Darby Unrevidierte Elberfelder is the available public-domain edition) |
| Schlachter 1951 | ✅ Public domain | already integrated |

## Approach

Add **Luther 1912** (new German default) and **Elberfelder 1871** as additional public-domain
German translations, reusing the existing `GERMAN_BOOK_NAMES` / `ENGLISH_TO_GERMAN` mappings
(book names are identical across all three). Verify the exact getBible codes against the getBible
manifest before loading.

## Acceptance Criteria

- [ ] German translation picker shows **Luther 1912** first (default), then Schlachter 1951, then
      Elberfelder 1871.
- [ ] Bible text + embeddings for both new translations are loaded and searchable.
- [ ] All existing tests pass; German-default assertions updated to `luther1912`.
- [ ] Verse-detail and chapter views render correctly for both new translations.

## Files / Config

| Item | Location | Change |
|---|---|---|
| Translation config | `scripts/translations.py` | add `luther1912`, `elberfelder1871` entries (reuse `GERMAN_BOOK_NAMES`) |
| DB seed | `scripts/init.sql` | add INSERT rows for both codes |
| Language → translations | `api/utils/language.py` `LANGUAGE_TRANSLATIONS["de"]` | `["luther1912", "schlachter", "elberfelder1871"]` |
| Translation metadata | `api/utils/language.py` `TRANSLATION_INFO` | add both entries |
| Book-name registry | `api/utils/translation_registry.py` `TRANSLATION_BOOK_NAMES` | map both codes → `ENGLISH_TO_GERMAN` |
| Supported list | `api/utils/book_names.py` | register both codes |
| Loader | `scripts/load_bible.py` | already supports `--translation <code>` (no change) |

## Implementation Notes

- The single source of truth for book names is `translation_registry.py` (AGENTS.md pitfall #4) —
  both new codes must map to `ENGLISH_TO_GERMAN`, never hardcode names.
- `is_default` stays `kjv` globally; "default per language" is governed by the first element of
  `LANGUAGE_TRANSLATIONS["de"]`.

## Data Loading (Operator Step — Post-Merge)

```bash
python scripts/load_bible.py --translation luther1912
python scripts/load_bible.py --translation elberfelder1871
```

~31k verses + embeddings per translation; 30–60 min each depending on embedding provider.

## Testing

- `api/tests/test_language_detection.py` — update German-default assertions
  (`get_translation_for_language("de")`, `detect_translation(...)`, `resolve_translation(...)`)
  from `schlachter` → `luther1912`; update `test_german_returns_one` (now 3 translations).
- `api/tests/test_translations.py` — add config tests for both new codes; update count assertions.
- `api/tests/test_multilingual_integration.py` — add branches for both codes.

## Related

- Multi-Language / Translation System section in `AGENTS.md`.

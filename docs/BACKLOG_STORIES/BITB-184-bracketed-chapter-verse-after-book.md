# BITB-184: Detect a Bracketed Chapter:Verse After the Book Name (`Romans (8:28)`, `罗马书（8:28）`)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-10
**Prompted by:** BITB-182 follow-up — found while writing the `verse-citing` follow-up chip cases.

## Bug Report

The backend parser (`api/utils/verse_parser.py`) finds a reference when the whole citation is
wrapped (`（罗马书8:28）`, `(Romans 8:28)`) but not when only the chapter and verse are bracketed after
the book name. Checked on `main` on 2026-10-10 with `extract_references`:

| Input | Result |
| ----- | ------ |
| `罗马书（8:28）` | none |
| `罗马书(8:28)` | none |
| `Romans (8:28)` | none |
| `Römer (8,28)` | none |
| `（罗马书8:28）` | `Romans 8:28` |

A missed reference means no lookup, no grounding and no link. BITB-179 covers the fullwidth colon
and a fully wrapped `（诗篇23：1）`; this form is separate.

## Functional Requirements

- FR1 Accept an optional ASCII or fullwidth bracket pair around the chapter:verse part when it
  directly follows a book name, in the shared grammar (`tests/fixtures/verse_grammar.json`) and
  the backend pattern; regenerate the web and Android grammar with the generator.
- FR2 Check the frontend (`frontend/src/lib/versePatterns.ts`) and Android parsers first: record
  whether they already accept this form, and keep all three in sync.

## Acceptance Criteria

- [ ] The four failing inputs above parse in backend, frontend and Android, with parity tests
- [ ] Parametrized across all 11 languages, including German comma separators and ranges
- [ ] No false positives on prose such as `chapter (8:28)` with no book name

## Out of Scope

- The fullwidth colon itself (BITB-179).

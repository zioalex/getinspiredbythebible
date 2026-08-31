# BITB-113: Verse-Parser Grammar Unification — Generate the Separator/Range Grammar for TS + Kotlin

**Status:** 🎯 Todo
**Priority:** P2
**Size:** L
**Created:** 2026-08-31
**Split from:** [BITB-108](BITB-108-verse-parser-phase-3-regex-grammar.md) — its ReDoS-safety ACs
(benchmark + fix for the connector branch) shipped separately; this story is the remaining scope.

## User Story

**As** a maintainer fixing a citation-parsing bug, **I want** the separator/range grammar to live in
one place like the book-name map now does, **so that** one fix ships to web, Android and the API
instead of three hand-synchronised edits that drift.

## Why This Exists

BITB-059's goal was a single source of truth for verse parsing. PR #983 delivered the book-name
half (Phases 1–2): `scripts/generate_localized_book_map.py` generates the Kotlin and TypeScript
book-name maps and is CI-guarded via `--check`. The separator/range grammar — colon-vs-comma
chapter:verse separators, hyphen/en-dash ranges, script-class alternations (Han/Hangul/Devanagari
handling) — is still hand-duplicated across:

- `frontend/src/lib/versePatterns.ts`
- `android/.../ChatMessageItem.kt`
- `api/utils/verse_parser.py`

Every citation-parsing fix (a new separator convention, a script-class edge case) currently costs
three hand-synchronised edits that can silently drift out of parity.

BITB-108 originally bundled this with its ReDoS-safety concern (audit item E13). The safety half is
now closed (bounded connector-branch quantifier, benchmark-verified — see BITB-108's Resolution
section) independently of this unification work, which is why it was split out: the two are
unrelated in both risk and effort, and bundling them made BITB-108 too large to ship as one
reviewable PR.

## Proposed Approach

1. Extend `scripts/generate_localized_book_map.py` (already CI-guarded via `--check`) to also emit
   the separator/range grammar and script-class alternations, for TypeScript and Kotlin.
2. Decide Python's relationship to the generated grammar. Follow Phase 2's precedent for
   `api/utils/translation_registry.py`: that file documents why generation was judged the wrong
   model for it, using a contract test instead. The same reasoning likely applies here — evaluate
   and record the decision either way.
3. Update `docs/AUDIT_PLAYBOOK.md`'s regex parity-ledger row to point at the generator, matching how
   the book-name-map row already does.
4. Keep the shared cross-platform corpus (PR #906) green throughout — it is the regression net that
   makes this rewrite tractable, on all three platforms.
5. Only once the grammar has a single generated source, consider retiring the duplicate
   hand-written parsers (BITB-086 notes this explicitly as follow-on, contingent work).

## Acceptance Criteria

- [ ] Separator/range grammar and script-class alternations come from one source, generated for
      TypeScript and Kotlin, with hand-editing failing CI
- [ ] Python's relationship to that source is decided and enforced — generated, or contract-tested
      like `translation_registry.py`
- [ ] The shared cross-platform corpus (PR #906) stays green across all three implementations
- [ ] `docs/AUDIT_PLAYBOOK.md`'s regex row points at the generator
- [ ] Duplicate-parser retirement (BITB-086) reconsidered once the grammar has one source — either
      done, or explicitly deferred with a reason

## Verification

The corpus (PR #906) is the regression net. Generation output must be diffed against the
hand-written grammar it replaces for all three platforms before the hand-written versions are
removed, and CI must fail on any hand-edit to a generated file (`--check` mode, matching the
book-name generator's existing convention).

## Related

- **BITB-108** — its ReDoS-safety half shipped first; this is the remaining Phase 3 scope
- **BITB-059 / PR #983** — Phases 1–2 (book-name map), the precedent this follows
- **BITB-086** — its parser-retirement note depends on this landing first
- **PR #906** — the shared corpus this must not break
- `frontend/src/lib/versePatterns.ts`, `android/.../ChatMessageItem.kt`,
  `api/utils/verse_parser.py`, `scripts/generate_localized_book_map.py`

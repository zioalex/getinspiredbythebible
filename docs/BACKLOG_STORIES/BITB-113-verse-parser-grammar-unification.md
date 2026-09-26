# BITB-113: Verse-Parser Grammar Unification — Generate the Separator/Range Grammar for TS + Kotlin

**Status:** 🚧 In Progress (2026-09-26)
**Priority:** P2
**Size:** L
**Created:** 2026-08-31
**Split from:** [BITB-108](BITB-108-verse-parser-phase-3-regex-grammar.md) — its ReDoS-safety ACs
(benchmark + fix for the connector branch) shipped separately; this story is the remaining scope.

## Scope Cut (2026-09-26)

Full grammar unification (retiring three hand-composed regex engines behind one IR) is out of
reach for a single reviewable PR without material regression risk to the app's core feature. This
pass ships the literal fragments that are genuinely identical across platforms today —
**connector words, the chapter/verse separator class, the range-dash class, and the non-ASCII
digit ranges** — as one generated JSON source, consumed by TypeScript and Kotlin. The
script-class *alternation* logic (which book names to list per script) stays hand-written in each
platform, because it is derived from `LOCALIZED_BOOK_TO_ENGLISH` (already a shared generated map,
BITB-059) via platform-specific filtering, not an independent literal to unify.

**Python's relationship (AC#2), decided:** contract-tested, not generated — for two independent
reasons, both recorded here so the decision doesn't need re-litigating:

1. `api/utils/verse_parser.py` matches book names via a flat literal alternation of every known
   name (`ALL_BOOK_NAMES`) built from `translation_registry.py`; it has no compositional
   "connector word" grammar to unify — `"Song of Solomon"` is one literal string in the registry,
   never assembled from a generic book-name + connector pattern the way TS/Kotlin build theirs.
   There is nothing to generate for connector words on the Python side.
2. Python's `re` module's `\d` is Unicode-aware by default (unlike JS `RegExp` and Java/Kotlin
   `Regex`, which need the explicit Devanagari/Eastern-Arabic ranges spelled out) — so Python's
   `cv_pattern` never needed those ranges and gains nothing from generating them.

What Python *does* share literally: the separator characters (`:`, `,`) and range characters
(`-`, en dash `–`). A parity test (`api/tests/test_verse_grammar_parity.py`) asserts Python's
hardcoded separator/range characters match the canonical JSON, mirroring how
`test_localized_book_map_registry_parity.py` holds `translation_registry.py` contradiction-free
with the generated book map instead of generating it.

**AC#5 (duplicate-parser retirement) — explicitly deferred, not done:** the three parsers still
need language-specific composition logic (JS `RegExp`, JVM `Regex`, Python `re` all differ in
Unicode-class support and lookbehind semantics), so retiring them behind one engine is a
substantially larger effort than this story's fragment-generation scope. BITB-086's retirement
note stays open, contingent on more of the grammar becoming generated first.

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

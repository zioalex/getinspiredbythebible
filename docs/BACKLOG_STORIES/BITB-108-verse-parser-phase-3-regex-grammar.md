# BITB-108: Verse-Parser Phase 3 — One Regex Grammar, and Prove It Can't Be Attacked

**Status:** 🎯 Todo
**Priority:** P2 — the book-name half of BITB-059 is solved; the regex-grammar half still costs a
three-platform repair for every citation fix, and carries an unbenchmarked ReDoS surface
**Size:** L
**Created:** 2026-08-22
**Prompted by:** PR #983 (BITB-059), which ships Phases 1–2 and labels the rest "Phase 3"

## User Story

**As** a maintainer fixing a citation-parsing bug, **I want** the separator/range grammar to live in
one place like the book-name map now does, **so that** one fix ships to web, Android and the API
instead of three hand-synchronised edits that drift.

## Why This Exists

BITB-059's goal was a single source of truth for verse parsing. PR #983 delivers half of it and says
so plainly — three of its acceptance criteria are marked **Partial** or **Phase 3, not started**:

> - [ ] A single source-of-truth spec … defines: localized book-name → English map, separator/range
>   grammar, and script-class alternations. **Partial:** the book-name map half is complete …; the
>   regex grammar half is Phase 3.
> - [ ] Build-time generation … produces the Kotlin, TypeScript, and Python artifacts …
>   **Partial:** Kotlin and TypeScript book-name maps are generated + CI-guarded … The regex grammar
>   (all three platforms) is Phase 3.
> - [ ] The nested-quantifier connector branch (`versePatterns.ts:276`) is benchmarked against
>   adversarial input … **Phase 3, not started.**

So after #983 merges, the parity ledger still carries a hand-synchronised regex row, and the
grammar remains duplicated across `frontend/src/lib/versePatterns.ts`,
`android/.../ChatMessageItem.kt` and `api/utils/verse_parser.py`.

### The ReDoS item is the sharp end

Audit item **E13** flags a nested-quantifier connector branch at `versePatterns.ts:276`. Nested
quantifiers are the classic catastrophic-backtracking shape, and this one runs **client-side on
model output** — text the user does not control and an attacker may partly influence. It has never
been benchmarked against adversarial input. The story's own recommendation is a two-stage
*cheap-candidate-scan → strict-validator* design rather than one mega-regex, which is both faster
and structurally immune to the failure mode.

This half is worth doing even if the unification is deferred: it is a latent hang in the browser, not
a tidiness concern.

## Proposed Fix

1. **Benchmark first.** Drive `versePatterns.ts:276` with adversarial inputs (long runs of
   connectors, digits and separators) and record the curve. If it degrades non-linearly, that alone
   justifies the rewrite ahead of any unification work.
2. **Rewrite as two stages** — a cheap linear candidate scan, then a strict validator on each
   candidate. Keep the shared corpus from PR #906 green throughout; it is the safety net that makes
   this rewrite tractable.
3. **Extend the generator** (`scripts/generate_localized_book_map.py`, already CI-guarded via
   `--check`) to emit the separator/range grammar and script-class alternations alongside the
   book-name map, for TypeScript and Kotlin. Follow Phase 2's precedent for Python: the story
   documents why generation is the wrong model for `api/utils/translation_registry.py`, and a
   contract test is used instead — the same reasoning likely applies to the grammar.
4. **Update the `docs/AUDIT_PLAYBOOK.md` parity-ledger regex row** to point at the generator. The
   book-name-map row already does; the regex row is the last hand-maintained one.
5. **Only then consider retiring the duplicate parsers** — BITB-086 notes that deleting the three
   parsers is Phase 3 work, and it is safe only once the grammar has a single generated source.

## Acceptance Criteria

- [ ] `versePatterns.ts:276` benchmarked against adversarial input, results recorded
- [ ] The connector branch is a two-stage scan+validate design, or the benchmark demonstrably shows
      the current form is safe (a recorded negative result closes this too)
- [ ] Separator/range grammar and script-class alternations come from one source, generated for
      TypeScript and Kotlin, with hand-editing failing CI
- [ ] Python's relationship to that source is decided and enforced — generated, or contract-tested
      like `translation_registry.py`
- [ ] The shared cross-platform corpus (PR #906) stays green across all three implementations
- [ ] `docs/AUDIT_PLAYBOOK.md`'s regex row points at the generator

## Verification

The corpus is the regression net and it already exists, which is what makes this safe to attempt.

The benchmark needs a real adversarial pass, not a smoke test: inputs deliberately shaped to force
backtracking, measured, with the numbers written down. "It felt fast" is what left E13 open.

## Related

- **BITB-059 / PR #983** — Phases 1–2; this is its explicitly-named Phase 3
- **BITB-086** — its parser-retirement note depends on this landing first
- **PR #906** — the shared corpus this must not break
- `frontend/src/lib/versePatterns.ts`, `android/.../ChatMessageItem.kt`,
  `api/utils/verse_parser.py`, `scripts/generate_localized_book_map.py`

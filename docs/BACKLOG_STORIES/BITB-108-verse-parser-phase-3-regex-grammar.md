# BITB-108: Verse-Parser Phase 3 — One Regex Grammar, and Prove It Can't Be Attacked

**Status:** 🚧 In Progress — ReDoS safety (AC1–2 below) closed; grammar-unification ACs split to
[BITB-113](BITB-113-verse-parser-grammar-unification.md)
**Priority:** P2 — the book-name half of BITB-059 is solved; the regex-grammar half still costs a
three-platform repair for every citation fix, and carries an unbenchmarked ReDoS surface
**Size:** L
**Created:** 2026-08-22
**Prompted by:** PR #983 (BITB-059), which ships Phases 1–2 and labels the rest "Phase 3"

## Resolution of the ReDoS half (2026-08-31)

The connector branch (`[\p{L}\p{M}]{2,}(?:\s+(?:of|dei|des|der|van|de|af|dos|da|del|के|ال)\s+[\p{L}\p{M}]+)+`)
was benchmarked with an adversarial input of repeated `" of aa"` segments run through the *full*
compiled pattern (`createVersePatternGlobal()`), not the branch in isolation — restart-driven scanning
at every string offset turns out to matter as much as the nested quantifier itself:

| input length | time (unbounded `+`) |
|---|---|
| 4,803 chars | 5ms |
| 19,203 chars | 87ms |
| 76,803 chars | 1,280ms |
| 307,203 chars | 21,988ms |

That is a genuine main-thread freeze on a plausible input size (a long pasted genealogy or an
LLM response repeating a connector word), not a contrived exponential case. Fix: bound the
connector-branch repetition to `{1,3}` — no entry in `localizedBookMap.generated.ts` needs more
than one connector repeat (checked: zero book names contain two connector words in sequence), so
`{1,3}` leaves headroom while making the branch's worst case O(1) instead of unbounded. Re-benchmarked
after the fix: a 1.2M-char adversarial input matches in under 50ms.

This is the "recorded negative result" alternative AC2 allows for, applied precisely: the *current
form* (bounded) is demonstrated safe by benchmark, rather than replacing it with the two-stage
scan+validate design the story originally proposed. The two-stage design remains a reasonable
future direction if the grammar is rewritten for BITB-113's unification work, but is not required to
close the safety gap.

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

- [x] `versePatterns.ts` connector branch benchmarked against adversarial input, results recorded
      (see Resolution above)
- [x] The connector branch is a two-stage scan+validate design, or the benchmark demonstrably shows
      the current form is safe (a recorded negative result closes this too) — closed via a bounded
      quantifier, benchmark-verified
- [ ] Separator/range grammar and script-class alternations come from one source, generated for
      TypeScript and Kotlin, with hand-editing failing CI — **split to BITB-113**
- [ ] Python's relationship to that source is decided and enforced — generated, or contract-tested
      like `translation_registry.py` — **split to BITB-113**
- [ ] The shared cross-platform corpus (PR #906) stays green across all three implementations — **split to BITB-113**
- [ ] `docs/AUDIT_PLAYBOOK.md`'s regex row points at the generator — **split to BITB-113**

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

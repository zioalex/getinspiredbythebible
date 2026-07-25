# BITB-059: Unify the Verse-Reference Parser — One Spec, Three Generated Artifacts

**Status:** 🚧 In Progress — Phase 1 (book-name map, Android leg) shipped; see Scope Note
**Priority:** P1 (High) — top-ranked finding of the 2026-07 adversarial audit (A1, CRITICAL); recurring cross-platform drift already shipping user-visible bugs
**Size:** L (spec + generator + migration of three call sites; the existing giant test suites become the safety net)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — A1 (also E13, D8)

## Scope Note (Phase 1, this PR)

AC#4 (shared cross-platform regression corpus) already shipped in PR #906 before this PR —
checked below.

This PR ships the **book-name map** half of AC#1/#2/#3/#6, **Android leg only**:

- `tests/fixtures/localized_book_map.json` is the new canonical source of truth for the
  localized-book-name → English-book-name map (AC#1, map only — the regex grammar is
  Phase 3).
- `scripts/generate_localized_book_map.py` generates
  `android/.../utils/LocalizedBookToEnglish.kt` from it, with a `--check` mode wired into
  `test_update.yml` so hand-editing the `.kt` file (or forgetting to regenerate after a JSON
  change) fails CI (AC#2, map only).
- `LocalizedBookToEnglishTest` now asserts **content equivalence** against the canonical JSON,
  replacing the old `size == 720` entry-count-only guard (AC#3 — done in full).
- `docs/AUDIT_PLAYBOOK.md`'s book-name-map parity-ledger row now points at the generator
  (AC#6, map only).

**Correction to this story's original problem statement:** at the time of this PR, the web
and Android book-name maps were verified **byte-for-byte identical** (720 entries, same keys,
same values, same order) — they had not yet drifted apart in content, only in their guard
quality (content-equivalence vs. entry-count-only). The audit's underlying risk — no guard
catches a content-only edit — was real and is what this PR closes for the Android leg; the
"already diverged" framing in the original problem statement was not confirmed and should not
be repeated.

**Live drift instance closed during this PR's own CI cycle:** while this PR was open, PR #903
merged to main and added 12 new Hindi aliases (`रोमियो`, `इफिसियो`, etc.) to the web map —
without touching the Android map, reproducing the exact drift this story predicts. Merging
main into this branch and re-running the generator picked up all 12 automatically and closed
the gap in the same PR, with no manual synchronization. Concrete validation that the guard
works as intended.

**Explicitly deferred (Phase 2):** generate the **web** `LOCALIZED_BOOK_TO_ENGLISH` from the
same JSON (currently locked to it only via a new parity test,
`frontend/src/lib/localizedBookMap.parity.test.ts`, not generation) and reconcile the JSON
against `api/utils/translation_registry.py` so the registry becomes the single true master.

**Explicitly deferred (Phase 3):** the regex grammar itself (separator/range grammar,
script-class alternations) — AC#5 and the audit's E13 nested-quantifier benchmark. This is
the higher-risk part of the story and needs its own scoped PR.

## User Story

As a maintainer, I want the verse-reference grammar (regex patterns + localized book-name maps)
defined **once** and consumed by web, Android, and the backend, so that fixing a citation edge case
in one place fixes it everywhere — instead of the current routine of three hand-synchronized
implementations drifting apart until a user reports dead verse links.

## Problem / Motivation

The verse-parsing engine exists three times, in two regex dialects:

- Kotlin: `android/.../ChatMessageItem.kt:104–362` (Java regex, `\p{IsHan}`)
- TypeScript: `frontend/src/lib/versePatterns.ts` + `verseExtraction.ts` (JS regex, `\p{Script=Han}`)
- Python: `api/utils/verse_parser.py`

The 737-line `LocalizedBookToEnglish.kt` is a self-described "parity copy — do not edit by hand" of
the 1,073-line web map, guarded only by an **entry-count** test — counts can match while contents
diverge. The drift is not hypothetical: PRs #799, #801, and #804 were all cross-platform drift
repairs ("web + android"). Every future locale/citation fix pays this tax again.

## Acceptance Criteria

- [ ] A single source-of-truth spec (data file or generator module) defines: localized book-name →
      English map, separator/range grammar, and script-class alternations.
      **Partial:** the book-name map half exists (`tests/fixtures/localized_book_map.json`);
      the regex grammar half is Phase 3.
- [ ] Build-time generation (or code-gen script committed with CI verification) produces the Kotlin,
      TypeScript, and Python artifacts; hand-editing a generated file fails CI.
      **Partial:** Kotlin book-name map is generated + CI-guarded; TypeScript/Python artifacts
      and the regex grammar are Phase 2/3.
- [x] The Android parity test checks **content equivalence** against the generated map, not entry
      count. — done (book-name map; `LocalizedBookToEnglishTest`).
- [x] A shared cross-platform test corpus (citation string → expected book/chapter/verse, including
      the #799/#801/#804 regression cases and non-Latin numerals) runs against all three
      implementations in their respective CI jobs. — shipped in PR #906 (before this PR).
- [ ] The nested-quantifier connector branch (`versePatterns.ts:276`) is benchmarked against
      adversarial input as part of the change (audit E13); prefer a two-stage
      cheap-candidate-scan → strict-validator design over one mega-regex. — Phase 3, not started.
- [ ] `docs/AUDIT_PLAYBOOK.md` parity-ledger row for the verse regex/book map is updated to point at
      the generator.
      **Partial:** the book-name-map row now points at the generator; the regex-grammar row is
      unchanged pending Phase 3.

## Out of scope

Moving extraction fully server-side (evaluated as the alternative in the audit) — larger change,
revisit if the generator approach proves insufficient.

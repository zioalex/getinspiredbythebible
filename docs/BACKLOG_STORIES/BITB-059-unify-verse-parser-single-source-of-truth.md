# BITB-059: Unify the Verse-Reference Parser — One Spec, Three Generated Artifacts

**Status:** 📋 Backlog
**Priority:** P1 (High) — top-ranked finding of the 2026-07 adversarial audit (A1, CRITICAL); recurring cross-platform drift already shipping user-visible bugs
**Size:** L (spec + generator + migration of three call sites; the existing giant test suites become the safety net)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — A1 (also E13, D8)

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
- [ ] Build-time generation (or code-gen script committed with CI verification) produces the Kotlin,
      TypeScript, and Python artifacts; hand-editing a generated file fails CI.
- [ ] The Android parity test checks **content equivalence** against the generated map, not entry
      count.
- [ ] A shared cross-platform test corpus (citation string → expected book/chapter/verse, including
      the #799/#801/#804 regression cases and non-Latin numerals) runs against all three
      implementations in their respective CI jobs.
- [ ] The nested-quantifier connector branch (`versePatterns.ts:276`) is benchmarked against
      adversarial input as part of the change (audit E13); prefer a two-stage
      cheap-candidate-scan → strict-validator design over one mega-regex.
- [ ] `docs/AUDIT_PLAYBOOK.md` parity-ledger row for the verse regex/book map is updated to point at
      the generator.

## Out of scope

Moving extraction fully server-side (evaluated as the alternative in the audit) — larger change,
revisit if the generator approach proves insufficient.

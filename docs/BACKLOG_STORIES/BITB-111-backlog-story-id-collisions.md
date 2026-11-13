# BITB-111: Fifteen Story IDs Refer to More Than One Story

**Status:** ✅ Done — all 16 collisions resolved (19 renumbers + 2 duplicate deletions), BITB-059
given a `docs/BACKLOG.md` entry, cross-references updated, and the CI guard
(`scripts/check_backlog_story_ids.py`) added and passing. A follow-up fix round corrected the
BITB-018 disposition (the companion analysis+resolution pair it was wrongly still sharing an ID
with is now BITB-147) and added the BITB-132 / BITB-142 entries `docs/BACKLOG.md` was missing. See
the Renumbering Log below.
**Priority:** P2 — a tracking defect that has already caused one near-miss and costs time on every
dedup pass
**Size:** M (mechanical, but every rename touches cross-references)
**Created:** 2026-08-22
**Prompted by:** the STEP 6 hygiene pass, and the BITB-092 collision caught in PR #969 hours before
it would have merged

## User Story

**As** anyone deciding what to work on, **I want** a `BITB-NNN` to identify exactly one story, **so
that** "is this already done?" is answerable by looking the ID up rather than by reading every file
that shares it.

## Why This Exists

`AGENTS.md` states the rule:

> **Story IDs are sequential.** Before creating a new story, check the highest existing `BITB-NNN`
> number in `docs/BACKLOG_STORIES/` and increment by one.

It is not holding. Fifteen IDs were found in the initial sweep to each name two to four unrelated
stories across `docs/BACKLOG_STORIES/` and `docs/DONE/`; a sixteenth (BITB-025) surfaced during
this story's own implementation (see *Two related defects* below) and is included in the table:

| ID | files | ID | files |
|---|---|---|---|
| BITB-017 | 3 | BITB-052 | 2 |
| BITB-018 | 4 | BITB-053 | 2 |
| BITB-024 | 2 | BITB-054 | 2 |
| BITB-025 | 2 | BITB-057 | 2 |
| BITB-027 | 2 | BITB-068 | 3 |
| BITB-028 | 2 | BITB-069 | 3 |
| BITB-037 | 3 | BITB-050 | 2 |
| BITB-043 | 3 | BITB-051 | 2 |

### This is not cosmetic

- **PR #969 nearly shipped a sixteenth.** It split BITB-084 Part C out as "BITB-092" while
  `BITB-092-fix-dev-db-initialization.md` was already merged and marked ✅ Done. Caught in review and
  renumbered to BITB-102 — but the only thing standing between the repo and another collision was
  someone noticing.
- **A dedup pass cannot trust an ID.** "Is BITB-051 done?" has no answer: the search-eval harness
  BITB-051 is partly shipped, the Android contact-form BITB-051 merged in June. Every check degrades
  into reading files.
- **Status lies by aliasing.** `docs/BACKLOG.md` marks BITB-009 ✅ Done on the strength of the models
  half, while four `# type: ignore` suppressions the same story requires removing are still on
  `main` and are what PR #984 fixes. An ID that names one thing cannot be half-done under another.

### Two related defects in the same family

- **BITB-059 has no `docs/BACKLOG.md` entry at all.** It exists only as a story file, and PR #983
  does not add one — so after that PR merges, an active story is invisible in the canonical list.
- **Orphaned story files.** `BITB-025-verse-linking-android.md` sits in `docs/BACKLOG_STORIES/` with
  no `BACKLOG.md` section; the BITB-025 entry that *does* exist is the Traditional Chinese story
  (PR #982). At least one such orphan exists per the earlier dedup pass; a sweep should find the
  rest.

## Proposed Fix

1. **Inventory** every duplicated ID and every story file with no `BACKLOG.md` entry. Mechanical and
   scriptable.
2. **Keep the earliest/shipped claimant** on each contested ID and **renumber the others** from the
   current high-water mark. Renaming a *shipped* story's ID is worse than renaming an unstarted
   one — merged PR titles and commit messages reference it and cannot be rewritten.
3. **Update every cross-reference** — `docs/BACKLOG.md`, other story files' Related sections,
   `docs/AUDIT_PLAYBOOK.md`, and any in-code comment naming the ID. Those in-code references are the
   ones most likely to be missed.
4. **Add a CI guard** asserting each `BITB-NNN` maps to exactly one story file and that every story
   file has a `BACKLOG.md` entry. This is the durable part: without it, the next collision is a
   matter of time, and the rule in `AGENTS.md` has already proven insufficient on its own.
5. **Record renumberings** in a short table so anyone following an old ID from a merged PR can find
   where the story went.

## Acceptance Criteria

- [x] Every `BITB-NNN` maps to exactly one story file across `docs/BACKLOG_STORIES/` and
      `docs/DONE/` — enforced by `scripts/check_backlog_story_ids.py`. `BITB-018` itself maps
      to exactly one file, the live `docs/BACKLOG_STORIES/BITB-018-query-understanding-context-quality.md`
      story; the unrelated CI/Ollama-timeout write-up that used to also claim ID 018 was
      renumbered to **BITB-147** (see Renumbering Log). The one legitimate remaining exception
      to "exactly one file" (`docs/DONE/BITB-147-ANALYSIS-CI-OLLAMA-TIMEOUT.md` +
      `docs/DONE/BITB-147-RESOLUTION-CI-OLLAMA-TIMEOUT.md`, a companion analysis+resolution pair
      for that one write-up) is an explicit, documented allowlist entry, not a blanket
      suppression — and the guard's allowlist-subtraction logic was fixed to still fail when a
      *third*, unrelated file shares an allowlisted pair's ID (an adversarial review found the
      original logic let that through; see `scripts/test_check_backlog_story_ids.py`)
- [x] Every story file has a corresponding `docs/BACKLOG.md` entry — including BITB-059 (added
      here), and BITB-132 / BITB-142 (this story's own renumbered files, added in the same
      follow-up fix round that corrected BITB-018 above — the entry-detection check itself was
      too weak to catch that they were missing: it accepted a bare `BITB-NNN` substring anywhere
      in `docs/BACKLOG.md`, which incidental prose mentioning either ID by name (e.g. this
      story's own Renumbering Log) satisfied without either file having a real entry; the check
      now requires an actual markdown heading or `**Full Story:**` link). Tightening that check
      also surfaced 4 more pre-existing gaps hidden the same way (BITB-016, BITB-017, BITB-031,
      BITB-032) — added to the exemption list rather than backfilled, same rationale as the 19
      below. 19 pre-existing gaps unrelated to the 16 collisions this story fixes were found by
      the new guard on its first pass; rather than silently backfilling an unbounded number of
      unrelated entries in this PR, they are named in a documented, commented exemption list in
      `scripts/check_backlog_story_ids.py` (`_MISSING_BACKLOG_ENTRY_EXEMPT`) so CI passes without
      permitting *new* violations. See this story's implementation report for the full list.
- [x] Cross-references updated everywhere, in-code comments included
- [x] A CI check fails on a duplicate ID or a story file with no backlog entry
- [x] A renumbering table records old → new for anything moved
- [x] The BITB-009 status is corrected to reflect that its suppression-removal criterion was
      outstanding until PR #984 — already correct in `docs/BACKLOG.md` (confirmed, no change
      needed)

## Verification

The CI guard is the deliverable that matters — the cleanup without it just resets a counter that
climbs again. Prove it by adding a deliberate duplicate on a scratch branch and confirming CI
rejects it.

## Related

- **PR #969 / BITB-102** — the near-miss that prompted this
- **PR #984 / BITB-009** — the status-aliasing example
- **PR #983 / BITB-059** — the missing-entry example
- `AGENTS.md` (*Backlog Hygiene*), `docs/BACKLOG.md`, `docs/BACKLOG_STORIES/`, `docs/DONE/`

## Renumbering Log

The keeper (earliest/shipped claimant) on each contested ID kept its number unchanged; every
other claimant was renumbered from the 130+ high-water mark (124 was the highest ID anywhere in
the repo at the time; 125–129 were already claimed by other in-flight PRs). Old IDs below are no
longer story IDs — this table exists only so a merged PR or commit message that cites one of them
can be traced to where the story went.

| Old ID (file) | New ID / disposition | Reason |
|---|---|---|
| BITB-017 (`skip-terraform-apply-when-no-changes.md`) | → **BITB-130** | Collided with keeper `BITB-017-multilanguage-harm-detection.md` |
| BITB-024 (`fix-contact-turnstile-token.md`) | → **BITB-131** | Collided with keeper `BITB-024-10-interaction-session-limit.md` |
| BITB-025 (`verse-linking-android.md`) | → **BITB-132** | Collided with keeper `BITB-025-traditional-chinese-t2s-normalization.md`; this was the orphaned file named in this story's original "Two related defects" section |
| BITB-027 (`translate-legal-pages.md`) | → **BITB-133** | Collided with keeper `BITB-027-android-chat-first-navigation.md` |
| BITB-028 (`pipeline-path-filters.md`) | → **BITB-134** | Collided with keeper `BITB-028-church-finder-bottom-sheet-cleanup.md` |
| BITB-037 (`android-amber-quote-test-coverage.md`) | → **BITB-135** | Collided with keeper `BITB-037-verse-citation-panel-reliability.md` (and the other BITB-037 claimant below) |
| BITB-037 (`seo-followups-server-render-homepage.md`) | → **BITB-136** | Same collision as above |
| BITB-043 (`product-analytics-dashboard.md`) | → **BITB-137** | Collided with keeper `BITB-043-validate-and-enable-phase1-search.md` (and the other BITB-043 claimant below) |
| BITB-043 (`require-contact-email-and-actionable-negative-feedback.md`) | → **BITB-138** | Same collision as above |
| BITB-050 (`search-thematic-relevance-and-response-depth.md`) | → deleted, duplicate of surviving `docs/BACKLOG_STORIES/BITB-050-thematic-search-and-response-depth.md` | Confirmed by full diff to be a stale duplicate (same work, same files touched); the surviving file is the corrected ✅ Done copy |
| BITB-051 (`search-retrieval-eval-harness.md`) | → **BITB-139** | Collided with keeper `BITB-051-android-contact-form-misleading-validation-error.md` |
| BITB-052 (`reference-normalization-gaps.md`) | → **BITB-140** | Collided with keeper `BITB-052-web-contact-form-email-specific-error.md` |
| BITB-053 (`modern-open-bible-translations-research.md`) | → **BITB-141** | Collided with keeper `BITB-053-ground-unquoted-paraphrased-citations.md` |
| BITB-054 (`android-first-run-feature-spotlight.md`) | → **BITB-142** | Collided with keeper `docs/DONE/BITB-054-translation-data-observability.md` |
| BITB-057 (`upstream-dependency-resilience.md`) | → **BITB-143** | Collided with keeper `BITB-057-android-inapp-update-api.md` |
| BITB-068 (`per-language-model-fallback-chain.md`) | → **BITB-144** | Collided with keeper `BITB-068-content-safety-smoke-tests.md` (and the other BITB-068 claimant below) |
| BITB-068 (`refresh-and-expand-bible-translations.md`) | → **BITB-145** | Same collision as above |
| BITB-069 (`menge-bibel-german-default.md`) | → **BITB-146** | Collided with keeper `docs/DONE/BITB-069-splash-screen-hydration-mismatch.md` |
| BITB-018 (`fix-ci-ollama-timeout.md`) | → deleted, merged into `docs/DONE/BITB-018-ANALYSIS-CI-OLLAMA-TIMEOUT.md` + `docs/DONE/BITB-018-RESOLUTION-CI-OLLAMA-TIMEOUT.md` | Self-admitted redundant historical copy of the same CI/Ollama-timeout investigation; folded into the analysis+resolution pair rather than kept as a third file |
| BITB-018 (`docs/DONE/BITB-018-ANALYSIS-CI-OLLAMA-TIMEOUT.md` + `docs/DONE/BITB-018-RESOLUTION-CI-OLLAMA-TIMEOUT.md`) | → **BITB-147** | **Fix-round correction:** an adversarial review found this pair was still incorrectly sharing ID 018 with the real, live `docs/BACKLOG_STORIES/BITB-018-query-understanding-context-quality.md` story (created 2026-02-24) even after the row above — the CI/Ollama-timeout write-up (dated 2026-03-04, over a week later, concluding "no fix needed") is a genuinely different, unrelated story that merely reused the number, not a companion doc *for the live BITB-018 story*. Renumbered to **BITB-147** so `BITB-018` maps to exactly one file again; the pair keeps sharing **BITB-147** between themselves as companion analysis+resolution halves of that one write-up (allowlisted in `scripts/check_backlog_story_ids.py`) |

Every cross-reference to an old ID above (`docs/BACKLOG.md` sections, other story files' Related
sections, and in-code comments) was updated to the new ID where the mention was actually about the
renumbered story — a plain-text ID could belong to either claimant, so each hit was read in context
rather than blanket-replaced. `docs/AUDIT_PLAYBOOK.md` mentions exactly one of the contested IDs —
`BITB-025`, once, correctly referring to the surviving keeper (Traditional→Simplified Chinese
conversion), not either renumbered claimant — so no cross-reference fix was needed there; the
original version of this section had incorrectly claimed it had no mentions of any contested ID at
all. Counting precisely from the table and this log: **16 distinct `BITB-NNN` values** were
contested (the 15 found in the initial sweep, plus `BITB-025` found during this story's own
implementation) — 19 renumbered files and 2 deleted duplicates across those 16 IDs, all now
resolved. `CHANGELOG.md` and dated session logs under `docs/WIP/`/`docs/DONE/` were left untouched: they
are historical records of what a PR was titled *at the time*, the same reason a shipped story's own
ID is never rewritten.

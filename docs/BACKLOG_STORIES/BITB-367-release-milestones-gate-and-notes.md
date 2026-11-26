---
id: BITB-367
status: todo
priority: P1
kind: chore
size: L
created: 2026-11-26
depends_on: [BITB-368, BITB-366]
---

# BITB-367: Product Releases — Milestones With an Outcome, a Gated Release PR, Stakeholder Notes

## User story

As the **owner**, I want each release to deliver a stated outcome, to know what is still missing
before I merge the Release PR, and to get a summary of what changed for users, what became more
reliable or secure, and what moved to the next release.

## Requirements

1. GitHub milestones titled `R<n>: <outcome>`; the description holds the outcome and how we know
   it is met. `docs/ROADMAP.md` is rewritten: Now = the current milestone, Next = the following
   one (absorbs the roadmap part of BITB-306).
2. `.github/workflows/release-gate.yml` on PRs labelled `autorelease: pending`: fails while the
   current milestone (lowest open `R<n>`) has open PRs or stories not `done`. The label
   `release/hotfix` bypasses it for urgent fix/nfr-only patches. On `release_created`, close the
   milestone and record the tag in its description.
3. `scripts/release_notes.py`: from the milestone's stories, the outcome plus "New features",
   "Quality & reliability" (nfr) and "Fixes", one line per story, and "Moved to next"; appended to
   the GitHub Release body; `make release-notes` previews it. CHANGELOG.md stays as release-please
   writes it.
4. Triage pass: create R1 "Safe and secure chat" (stories in BITB-368) and the next milestones,
   label the open PRs, and decide #1316 (`release 1.62.1`): hotfix now or hold for R1.

## Acceptance criteria

- [ ] With an open R1 item the Release PR check is red; green once closed; `release/hotfix`
      bypasses it
- [ ] `make release-notes` for R1 prints the three sections and "Moved to next"
- [ ] Unit tests for the gate and the notes builder

---
id: BITB-367
status: in-review
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

## Decisions (owner, 2026-11-27)

- R1 is "Safe and secure chat" (stories in BITB-368). R2 is "Smoother chat on web and Android":
  BITB-331/334 (#1312), BITB-252 (#1339), BITB-300 (#1301).
- The Release Gate **blocks**; the `release/hotfix` label lets an urgent fix release through. It is
  not a required check, so the owner can merge past it.
- Release PR #1316 (1.63.0: agent tooling only) is held until R1 is done.
- GitHub milestones `R1: Safe and secure chat` (#1) and `R2: Smoother chat on web and Android` (#2)
  were created on 2026-11-27, each with an `Outcome:` line the notes reuse.
- A hotfix release adds no product notes and leaves the milestone open.

## Acceptance criteria

- [x] `scripts/release_notes.py` (`notes`, `gate`, `current`, `github-milestone`) with unit tests
      (`scripts/test_release_notes.py`), including the real R1 against the real backlog
- [x] `release-gate.yml` (gate + preview comment + hotfix label) and the `product-notes` job in
      `release-please.yml`; `make release-notes`
- [x] `docs/ROADMAP.md` rewritten (Now = R1, Next = R2) and `docs/RELEASE_PROCESS.md` gains
      "Product releases (milestones)"
- [ ] Live, after merge: the Release Gate on #1316 is red while R1 is open, its preview comment
      lists the open R1 items, and `release/hotfix` turns it green
- [ ] Triage: every open PR carries a `kind/*` label; R1 and R2 PRs are in their milestones
- [ ] Owner step: when R1's stories are done, merge #1316; the product notes appear on the GitHub
      Release and milestone R1 closes

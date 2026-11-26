---
id: BITB-365
status: in-review
priority: P1
kind: chore
size: M
created: 2026-11-26
prs: [1345]
follow_ups: [BITB-366, BITB-367]
---

# BITB-365: Every Story Says What It Is for the Product — `kind` and Release `milestone`

## User story

As the **owner**, I want each change to say whether it is a new feature, a non-functional
improvement (security, privacy, reliability, performance, cost), a fix, internal work or an
experiment, and which product release it belongs to, so that the PR list and the releases read
as product outcomes instead of a stream of commits.

## Problem (evidence, 2026-11-26)

- The commit type is the only classification, and it describes code, not product. NFRs ship as
  `fix:` (BITB-297 trusted client IP, BITB-298 rate limits, BITB-317 error echo); ops and legal
  work ships as `feat:` (`feat(infra)` SLO tiles, `feat(legal)` retention, `feat(parity)` CI).
- Agent tooling reaches the user-facing notes: v1.60.0 "Bug Fixes" lists five
  `opencode`/`kubeopencode` fixes, and the in-app What's New shows that entry verbatim.
- Releases ship whenever the Release PR is merged (v1.60 9 Nov, v1.61 10 Nov, v1.62 16 Nov) with no
  stated outcome; `docs/ROADMAP.md` was last updated 2026-02-23. 25 PRs are open.

## Requirements

1. Front matter gains `kind` (`feature | nfr | fix | chore | spike`) and optional `milestone`
   (`R1`, `R2`, ...), placed after `priority` so an insert never touches the `status` line
   that open PRs flip.
2. `backlog.py check` rejects unknown values, and requires `kind` on open stories created from
   2026-11-27 (stories already claimed by open PRs are not turned red by a merge of `main`).
3. `backlog.py list --kind ... --milestone ...` filters; the markdown/rendered index shows both.
4. `docs/backlog/LEGEND.md` defines each kind, with examples and allowed commit types.
5. Every open story on `main` is backfilled with a `kind`; the stories agreed for R1 carry
   `milestone: R1`.

## R1: Safe and secure chat (owner, 2026-11-26)

Outcome: a person in distress gets a safe answer in all 11 languages even when a moderation
provider fails, and the public API does not leak or let others spend what it should not.
Stories: BITB-321, BITB-288, BITB-294, BITB-203, BITB-204, BITB-310, BITB-317, with the golden
sets BITB-293 and BITB-322 as the evidence. WIP limit agreed: 8 open product PRs (to revisit).

## Acceptance criteria

- [x] `make backlog-check` passes with every open story carrying a `kind`
- [x] `make backlog ARGS="list --milestone R1"` lists the nine R1 stories
- [x] Unit tests cover the new keys, the cut-over date, the filters, and that the backfill insert
      merges cleanly with a status flip on another branch
- [ ] Owner step: review the backfilled kinds (`make backlog ARGS="list --kind nfr"`, etc.) and
      correct any that are wrong with a one-line edit

## Out of scope

PR labels and CI enforcement (BITB-366); GitHub milestones, the release gate and release notes
(BITB-367); localized end-user What's New (BITB-175).

## Follow-ups

- BITB-366 — PR `kind/*` labels, title/kind consistency check, PR template, WIP limit
- BITB-367 — Release milestones, Release-PR gate, stakeholder release notes

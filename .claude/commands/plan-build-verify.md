---
description: Run a task through the Specify → Plan (Opus) → Build (Sonnet) → Verify (Opus) relay
argument-hint: <task description>
---

Run the task below through this project's standard **Plan → Build → Verify**
relay, which starts with a Specify step (see `AGENTS.md` → *Standard Workflow*). Do not shortcut it for anything
beyond a trivial one-line change.

## Task

$ARGUMENTS

## Stage 0 — Specify (you, Opus)

Gather **all** the requirements before planning:

1. Do a quick code read so your questions are informed (e.g. you've found the
   likely root cause or the affected screens).
2. Interview the user with `AskUserQuestion`: platform(s), desired behaviour,
   edge cases, languages/locales, devices, priority, and what's out of scope.
   Give concrete options, with the recommended one first.
3. Write the spec into the backlog story `docs/BACKLOG_STORIES/BITB-NNN-<slug>.md`:
   user story or bug report, functional requirements, non-functional
   requirements (platforms, all 11 languages, accessibility, performance),
   acceptance criteria, out of scope, and open questions.
4. Show the user the spec and get confirmation before Stage 1. Every acceptance
   criterion must be testable; the Stage 3 verifier checks against them.

## Stage 1 — Plan (you, Opus)

1. Explore before deciding: read the files involved and search for existing
   functions, utilities, and patterns to reuse instead of writing new code.
2. Resolve any genuine ambiguity with the user via `AskUserQuestion` *before*
   writing the plan — do not guess on decisions that change the outcome.
3. Write an explicit plan: the problem/why, the precise change per file, and a
   verification section (which tests/commands prove it works).
4. Add the plan to the story file from Stage 0 and keep its front matter
   (`status`, `prs`) current per *Backlog Hygiene* in `AGENTS.md` (sequential
   `BITB-NNN`; find stories with `make backlog`, never by reading `docs/BACKLOG.md`,
   which is a stub that PRs must not edit).

## Stage 2 — Build (delegate to Sonnet)

Launch a single `Agent` with `subagent_type: general-purpose` and
`model: sonnet`, handing it the full approved plan as its brief. It must:

- Make all code, test, migration, and i18n changes on the current feature branch.
- Follow `AGENTS.md` (code style, every-change-ships-with-tests, i18n in all 11
  locales, conventional commits).
- Report exactly what it changed (files + a short summary), and NOT open a PR
  unless the user explicitly asked for one.

## Stage 3 — Verify (delegate to Opus)

Launch a *separate* `Agent` with `model: opus` (read-capable, e.g.
`subagent_type: general-purpose` or the `verify` skill). It must, independently:

- Run the backend tests, frontend tests/lint/type-check, and Android tests if
  those areas were touched (commands in `AGENTS.md` → *Testing*).
- Review the diff against the plan's acceptance criteria.
- Report **PASS/FAIL with evidence** (test output, specific gaps). It must not
  rubber-stamp — call out anything missing or untested.

If a suite cannot run in this environment (no network for Gradle, no DB,
etc.), the verifier must say which, do a deeper static review instead, and the
main session must treat the PR's CI run as the gate it watches to green.

## Close-out

- **Loop until PASS.** If the verifier reports FAIL or any gap, do not close
  out: hand the verifier's findings back to Build (Sonnet, continuing the same
  agent when possible) as a fix brief, then run a *fresh* Opus verifier on the
  new diff. Repeat Build → Verify until the verifier returns PASS. Trivial
  fixes (a typo, an import) may be made directly by the main session, but still
  get re-verified. If the loop stops converging (the same finding twice in a
  row, or a design question the plan didn't settle), stop and ask the user
  instead of looping again.
- After the PR is open, a red CI run counts as a FAIL and re-enters the loop.
- Set the story's front matter (`status`, `prs`, `follow_ups`); do not touch `docs/BACKLOG.md`.
- **Before opening the PR**, file a follow-up `BITB-NNN` story for every point
  it leaves unfixed, in the same PR, and list the IDs under *Follow-ups* in the
  PR description (see *Backlog Hygiene* in `AGENTS.md`). Never write "to file at
  merge". At merge, re-check only for new points raised in review.
- **Owner actions:** as soon as you find a step only the owner can do (a secret,
  `terraform apply`, a `workflow_dispatch` run, a decision), tell the user in
  chat in that turn, under "⚠️ Owner action needed". Also put it at the top of
  the PR description under `## ⚠️ Owner action required`.
- Summarize for the user: what changed, test results, the follow-up story IDs,
  and the owner actions again.
- Commit/push only when the user has asked; never push to a closed/merged PR
  branch.

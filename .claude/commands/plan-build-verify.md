---
description: Run a task through the Plan (Opus) → Build (Sonnet) → Verify (Opus) relay
argument-hint: <task description>
---

Run the task below through this project's standard **Plan → Build → Verify**
relay (see `AGENTS.md` → *Standard Workflow*). Do not shortcut it for anything
beyond a trivial one-line change.

## Task

$ARGUMENTS

## Stage 1 — Plan (you, Opus)

1. Explore before deciding: read the files involved and search for existing
   functions, utilities, and patterns to reuse instead of writing new code.
2. Resolve any genuine ambiguity with the user via `AskUserQuestion` *before*
   writing the plan — do not guess on decisions that change the outcome.
3. Write an explicit plan: the problem/why, the precise change per file, and a
   verification section (which tests/commands prove it works).
4. Create or update the backlog story and `docs/BACKLOG.md` entry per
   *Backlog Hygiene* in `AGENTS.md` (sequential `BITB-NNN`).

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

## Close-out

- Fix any gaps the verifier found (re-delegating to Sonnet if substantial).
- Mark the story status and update `docs/BACKLOG.md`.
- Summarize for the user: what changed, test results, and any follow-ups.
- Commit/push only when the user has asked; never push to a closed/merged PR
  branch.

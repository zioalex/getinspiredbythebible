---
id: BITB-271
status: todo
priority: P2
size: S
rank: 140
created: 2026-11-08
---

# BITB-271: Upstream opencode — Subagent `question` Tool Call Parks Forever; No Default Denial, Timeout, or Parent Routing

**Migration note (2026-11-13, status):** (contains an owner-run external step)
**Follow-up to:** BITB-269 (deferred as out-of-scope item 2)

## User Story

**As a** user of opencode's subagent/task system,
**I want** `mode: subagent` sessions to be structurally unable to hang
their parent on an unanswerable interactive tool call,
**so that** the framework itself — not every downstream project's plugin
config and per-agent permission lists — guarantees dispatch liveness.

## Background

The 2026-11-07 incident (BITB-269): a fullstack-engineer subagent invoked
the `question` tool; a subagent has no interactive user, so the call was
never answered and never timed out. The child session parked in `asking`
state, the parent's task tool call blocked with it for **9h34m** (even a
parallel verifier sibling's *completed* result was trapped behind the
blocked call), and the runtime log recorded exactly one
`message=asking` line before going silent. The deadlock broke only when a
human resumed the parent session, at which point the runtime aborted the
parked child and delivered `Task cancelled`.

Local mitigations shipped in BITB-269 (PR #1254) are defense-in-depth:
`question: deny` on all 11 subagent agents, a plugin watchdog that
records `asking` and aborts stuck children best-effort, and an
orchestrator resume ritual. The framework should not need any of that.

## Requirements

1. **Draft the upstream issue** (ready-to-paste text below), covering:
   - reproducible narrative + log excerpts (version 1.18.31,
     `opencode serve`, ai-sdk runtime, openrouter provider);
   - expected vs actual behavior;
   - proposed behaviors, in preference order:
     a. **default-deny** `question` for `mode: subagent` agents (or make
        denial the documented default rather than opt-in per agent);
     b. or **auto-answer** synthetically ("no interactive user — proceed
        with best judgment and report the blocker in your result");
     c. or **route** the question to the parent session / the parent's UI;
     d. and at minimum: a **timeout** on unanswered subagent questions,
        plus a **timeout on the parent-side task call** (a child session
        that never terminates blocks the parent forever — the same wedge
        from the other side).
2. **File it upstream** — OWNER-RUN step (external account action against
   the opencode repo; verify the canonical tracker first — the binary
   self-identifies as opencode 1.18.31, plugin SDK
   `@opencode-ai/plugin@1.18.31`; confirm the GitHub org/repo before
   filing). Record the issue URL in this story and in the backlog entry.
3. **Track the upstream outcome** and record the local-layer decision:
   - keep or remove per-agent `question: deny` (recommend keep — it is
     cheap and explicit even if the framework fixes the hang);
   - retire the watchdog's `asking`-abort if it becomes redundant, or keep
     it covering the parent-side timeout gap until upstream ships one;
   - update this story's status (`✅ Done` once filed + linked, or
     `❌ Cancelled` if the upstream issue already exists — in that case
     link the existing issue instead of filing a duplicate).

## Acceptance Criteria

- [ ] Issue draft finalized in this story (paste-ready)
- [ ] Canonical upstream repo/tracker verified (correct org/repo)
- [ ] (owner) issue filed upstream; URL recorded here + in the backlog entry
- [ ] (owner) upstream response tracked; local-layer keep/retire decision
      recorded in this story

## Issue draft (starting point — verify against the current opencode

version and issue template before filing)

> **Title:** Subagent (`mode: subagent`) sessions can invoke the `question`
> tool and park forever — no default denial, timeout, or parent routing;
> parent's task call blocks indefinitely
>
> **Version:** opencode 1.18.31 (`opencode serve`, OPENCODE_CONFIG via env),
> ai-sdk runtime, provider openrouter, plugin SDK @opencode-ai/plugin@1.18.31.
>
> **What happens:**
> A subagent session (agent with `mode: subagent`, spawned via the task
> tool) can call the `question` tool. A subagent has no interactive user,
> so the question is never answered and never times out:
>
> - The child session parks in `asking` state indefinitely (runtime log
>   shows a single `message=asking … questions=1` line, then silence).
> - The parent's task tool call blocks until the child terminates — which
>   never happens. No timeout on either side.
> - Parallel task results completed *before* the wedge are also trapped:
>   the parent cannot process them until every in-flight call resolves.
> - The only recovery is a human resuming the parent session, at which
>   point the runtime aborts the parked child (`error=Aborted` on the
>   child's in-flight message) and the task call returns "Task cancelled".
>
> Observed wall-clock cost in our setup: **9h34m** of a wedged
> orchestration run from one question call
> (child created 23:02:41, `asking` at 23:09:29, abort at 08:36:14 next day).
>
> **Expected:**
> One or more of:
>
> 1. `question` denied by default for `mode: subagent` agents (or the
>    denial documented as the required setup);
> 2. auto-answer with a synthetic response so the loop continues;
> 3. routing the question to the parent session / parent UI;
> 4. a timeout on unanswered subagent questions;
> 5. a timeout on the parent-side task tool call.
>
> **Workaround we ship locally:** per-agent `permission: question: deny`
> for all subagents + a plugin watchdog that aborts children stuck in
> `asking` state. Happy to contribute upstream if there's appetite —
> we'd want the default-deny (#1) plus the task-call timeout (#5).

## Out of Scope

- Fixing the behavior in opencode core from this repo (contribute
  upstream only with maintainer interest; do not fork)

## References

- BITB-269 (incident, local mitigations), BITB-270 (the sibling
  stream-stall gap — separate failure class, file as its own upstream
  issue if it can't ride along)
- Incident log: `message=asking id=que_1b8462d6… questions=1` at
  23:09:29 UTC; child `ses_e47c00c61…`, abort `error=Aborted` at
  08:36:14 UTC

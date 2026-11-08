# BITB-269: Subagent `question`-Tool Deadlock — 9.5h Orchestrator Hang, Unsupervised Detached Children

**Status:** 🔄 In progress — mitigations implemented in the same PR; runtime hardening below
**Priority:** P1
**Size:** M
**Created:** 2026-11-08
**Incident:** 2026-11-07, 23:02→08:36 UTC (9h34m orchestrator hang)

## Bug Report (the incident, reconstructed from the runtime log)

A `[T-1248LINT]` fullstack-engineer dispatch (fix a yamllint line-length
violation on PR 1248) hung the entire orchestration run overnight:

1. **23:02:41** — child session `ses_e47c00c61…` created; parent's parallel
   task call (plus a verifier sibling) in flight.
2. **23:09:21** — child reaches loop step 17 and streams a response.
3. **23:09:29** — the child emits a `question` tool call (runtime log:
   `message=asking id=que_1b8462d6… questions=1`). The brief had named the
   **wrong branch** (PR 1241's `claude/elegant-gates-lwy7a7` instead of PR
   1248's `claude/elegant-gates-mjnm4f`), so the lint violation the brief
   described did not exist on the branch the child fetched — it asked.
4. **A subagent has no interactive user.** The question can never be
   answered; opencode ≤1.18 neither denies `question` for subagent-mode
   sessions nor times the call out. The child parked in `asking` state
   indefinitely.
5. The parent's task tool call blocks until the child finishes — no
   timeout on either side. The parent was wedged 23:02→08:36; even the
   **verifier sibling's completed result** was trapped behind the blocked
   call. From the user's seat the orchestrator simply hung with no output.
6. **08:36:14** — the user's next prompt resumed the parent; the runtime
   aborted the parked child (`error=Aborted` on its in-flight message) and
   delivered `Task cancelled` to the parent. The documented recovery
   checklist (log grep → `task_id` resume) then recovered the child
   cleanly: it spotted the branch-name error itself and completed the fix
   in ~30 minutes.

Aggravating factors found during the post-mortem:

- The **task-reliability plugin** (`.opencode/plugin/task-reliability.ts`,
  BITB-169) — which writes the durable child registry
  (`/workspace/.opencode/task-registry.jsonl`), enriches cancelled task
  output with the child id, and embeds the recovery protocol — **is not
  loaded in the pod**: the generated `opencode.json`'s `plugin` array
  contains only `opencode-runtime-fallback@0.2.4`, and plugin
  auto-discovery scans the *effective* project root (`/workspace/.opencode/`
  — empty) while the plugin lives in the repo checkout at
  `/workspace/repo/.opencode/plugin/`. Recovery therefore required raw
  greps of the ephemeral `/tmp` runtime log (also non-PVC: `HOME=/tmp`).
- Nothing watches for children with no terminal state. A parked or stalled
  child is invisible until a human pokes the parent session.

## Requirements

### Done in this PR (mitigations — config + protocol only)

1. **`question: deny`** added to all 11 `mode: subagent` agents in
   `.opencode/agents/` (+ a "no questions — report blockers in your task
   result" contract paragraph in each body). A confused child now fails
   fast at the tool call and reports blockers instead of parking.
2. **Orchestrator protocol** (`.opencode/agents/orchestrator.md` +
   `AGENTS.md`): briefs identify PRs by number + `refs/pull/<n>/head`
   (never hand-copied branch names); run-closure rule (no yielding while a
   dispatched token lacks a terminal outcome); resume-after-idle ritual;
   bounded commands in briefs (`timeout …`, max-iteration poll loops).

### Runtime hardening (implement in this PR)

3. **Load the task-reliability plugin in the pod.** Add it to the
   `PLUGIN` list in `scripts/generate-opencode-config.py` so the generated
   `opencode.json` carries it through the configmap sync into
   `/tools/opencode.json`. Path design must work both in-pod
   (`/workspace/repo/.opencode/plugin/task-reliability.ts` — absolute
   `file:///` entry is acceptable) and on developer laptops (plugin is
   inert there by design; verify opencode tolerates a non-existent plugin
   path without breaking startup). Extend
   `scripts/test_generate_opencode_config.py` accordingly.
4. **Stuck-child visibility (watchdog), as far as the plugin API allows.**
   In `task-reliability.ts`: on the `event` hook, record `asking` events
   for subagent sessions in the registry (`kind: "status"`, `status:
   "asking"`), and when a child has shown no activity for a configurable
   threshold (env `TASK_RELIABILITY_STUCK_SECONDS`, default ~1200) append a
   `status: "stuck"` line. If the plugin `client` API exposes a way to
   abort/cancel a session, use it for `stuck` children; otherwise the
   registry line is the deliverable (the orchestrator's resume ritual
   greps for it). Extend `task-reliability.test.ts` (`node
   --experimental-strip-types --test`) for the new logic. Preserve the
   plugin's "inert by design / never break a session or startup" contract.
5. **Registry-first recovery becomes real:** after sync + pod restart,
   `/workspace/.opencode/task-registry.jsonl` must exist and record
   `created`/`status` lines for every subagent dispatch (verifiable the
   next time the orchestrator runs in the pod).

## Acceptance Criteria

- [x] All 11 subagent agent definitions deny `question`; generator carries
      per-agent `permission` through to `opencode.json` (test added:
      `test_subagent_question_denied` + `test_permission_frontmatter_round_trips`)
- [x] Generated `opencode.json` includes the task-reliability plugin entry;
      `make gen-opencode-config` + `make verify-opencode-config` pass;
      generator tests pass (`test_task_reliability_plugin_entry_present`)
- [x] `node --experimental-strip-types --test .opencode/plugin/task-reliability.test.ts`
      passes with the new asking/stuck tests (26/26)
- [x] `make pre-commit` passes
- [x] The docs (`AGENTS.md` Subagent Delegation Reliability section) match
      the implemented behavior (watchdog bullet added)
- [ ] After merge + `make sync-opencode-configmap` + pod restart: a test
      dispatch shows the registry file being written (owner-run step; keep
      unticked until verified in-pod)
- [x] Follow-up story filed for any watchdog capability the plugin API
      could not deliver — N/A: the plugin `client` DOES expose
      `client.session.abort({ path: { sessionID } })` (probed empirically on
      opencode 1.18.31 in-pod), so the watchdog aborts stuck children
      directly; no capability was left undelivered. The abort call is
      best-effort/try-catch — if a future runtime drops the API, the
      `status: "stuck"` registry line alone remains the deliverable.

## Out of Scope

- General LLM stream-stall detection beyond the fallback plugin's existing
  error-retry (`timeout_seconds: 45` covers provider errors, not silent
  stalls) — file a separate story if the stream-stall class recurs
- Any change to opencode core (the deadlock is an upstream limitation;
  upstream issue can be filed separately)

## References

- Incident log forensics: `~/.local/share/opencode/log/opencode.log`
  (`ses_e47c00c61…`, `message=asking que_1b8462d6…` at 23:09:29,
  `error=Aborted` at 08:36:14)
- BITB-169 (task-reliability plugin), BITB-236 (fallback model posture),
  BITB-128 (PVC persistence), BITB-235 (story-ID allocation)

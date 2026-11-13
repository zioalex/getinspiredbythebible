---
id: BITB-269
status: in-progress
priority: P1
size: M
rank: 110
created: 2026-11-08
---

# BITB-269: Subagent `question`-Tool Deadlock — 9.5h Orchestrator Hang, Unsupervised Detached Children

**Status note:** mitigations implemented in the same PR; runtime hardening below
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
      passes with the new asking/stuck tests (26/26; extended to 29/29 by the
      T-1254PLG addendum — loader-contract regression tests + the empirical
      nested `session.created` shape)
- [x] `make pre-commit` passes
- [x] (T-1254PLG addendum) The plugin module's runtime export surface is a
      single default function — pinned by test, enforced by
      `opencode-ci.yml` on every `.opencode/**` change, and pre-flighted
      in-pod by `scripts/sync-opencode-workspace.sh` before any config sync
      (the [T-269A] present-but-rejected-export gap is now mechanically
      closed)
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

## Follow-ups (filed 2026-11-08)

- **BITB-270** — LLM stream-stall watchdog: the fallback plugin is
  error-driven, so a stream that stalls without closing trips nothing;
  stream-idle detection + abort/registry line, threshold far tighter than
  the 1200 s stuck catch-all
- **BITB-271** — upstream opencode issue: subagent `question` call parks
  forever (no default denial, timeout, or parent routing; parent task call
  also unbounded) — paste-ready draft included in the story; filing is an
  owner-run external step

## Pre-live verification gap (2026-11-08, T-1254PLG addendum)

The pre-merge config sync on 2026-11-08 (pod restarted 18:51 UTC) loaded the
config improvements but **failed to load the plugin** — runtime log 18:52:00Z:

```text
ERROR message="failed to load plugin"
      path=file:///workspace/repo/.opencode/plugin/task-reliability.ts
      error="Plugin export is not a function"
```

Post-mortem findings (all verified empirically against the live
opencode 1.18.31 binary, scratch-instance probes; live server untouched):

1. **Why the [T-269A] "verification" missed it.** The builder verified
   laptops were unaffected by testing a *missing* plugin path (silently
   skipped — true), and the unit tests proved the module parses under Node
   type-stripping — but a *present-but-rejected* export was never
   live-tested against the actual opencode loader. Both the old and the new
   plugin versions carried the same latent bug.
2. **The actual loader contract (opencode 1.18.31).** The loader iterates
   `Object.values(module)` over the plugin module's export surface: **every**
   distinct export must be a function (or an object with a callable
   `.server`), and **every** function export is then CALLED as
   `plugin(ctx, options)` with its return value registered as hooks. The
   plugin module exported the string constant `DEFAULT_REGISTRY_PATH` →
   rejected whole. Even without the constant, co-resident helpers break the
   load: the loader would call `findActiveChild(ctx, …)` →
   `{} is not iterable`. The working reference
   (`opencode-runtime-fallback@0.2.4`) ships exactly one export:
   `export { OpenCodeFallbackPlugin as default }`.
3. **The fix.** The plugin module now exports exactly one thing — the
   default plugin function — and all named helper exports the tests import
   moved to the sibling `task-reliability-helpers.ts` (imported, never
   re-exported). `task-reliability.test.ts` gained two regression tests that
   pin the contract (single `default` export; called-as-the-loader-calls-it
   returns the hooks object), and a third pinning a second live-only bug the
   scratch test surfaced: on 1.18.31 the `session.created` parent linkage
   arrives nested under `properties.info.parentID` (not flat), so `created`
   lines — and with them the whole stuck-child watchdog — never fired
   against the old flat-shape reader. 29/29 tests green under
   `node --experimental-strip-types --test` (Node 22.23.4, the pod's node).
4. **Proof it loads now.** Isolated scratch instance (separate
   HOME/XDG/config/DB; live server untouched): zero
   `failed to load plugin` in the scratch log, a real subagent task
   dispatched through the task tool completed, and the registry recorded
   `created` (with parentID/agent/title) + `idle` lines.
5. **Delivery hazard — the stale shared checkout.** The config points at
   `file:///workspace/repo/...` but nothing updated that checkout after the
   initial clone; at sync time it was 6 days stale, so even a
   loader-compatible config would have loaded the old plugin file.
   **Chosen: Option B — the sync flow fast-forwards the pod's checkout.**
   `make sync-opencode-configmap` now first runs
   `scripts/sync-opencode-workspace.sh`: `kubectl exec` into the agent pod →
   `git fetch origin && git merge --ff-only origin/main` in `/workspace/repo`
   → run the plugin unit tests *in the pod* (the pre-flight the incident
   lacked) → only then update the ConfigMap. Fast-forward only: diverged,
   detached, or non-main checkouts fail loudly; history is never rewritten;
   attached worktrees (`${WORKSPACE_DIR}/worktrees/*`) are unaffected
   (verified: worktree HEADs and uncommitted files survived a simulated ff).
   Rejected alternatives: **Option A** (ship the plugin file in a multi-key
   ConfigMap) needs operator file-mount support the `kubeopencode.io/v1alpha1`
   CRD does not expose (same limitation as the auth.json mount — "not wirable
   today"); **Option C** (copy the plugin to the PVC auto-discovery dir
   `/workspace/.opencode/plugin/`) puts the file outside any self-healing
   flow: the documented PVC-reset runbook (`kubectl delete pvc`) re-clones
   the checkout but would silently leave the plugin *missing* until the next
   sync, while a re-cloned checkout (Option B) always carries the merged
   plugin. Runbook: **merge → `make sync-opencode-configmap` → delete pod →
   verify** (greps in deployment/kubeopencode/README.md). *(the runbook now lives in k8s/kubeopencode/README.md — BITB-285)*
6. **CI now enforces the tests.** The plugin suite was never wired into CI
   (why the gap shipped). `.github/workflows/opencode-ci.yml` now runs it on
   every `.opencode/**` change (Node 22.x, type-stripping), and
   `make test-opencode-plugin` exposes it locally.

## Out of Scope

- General LLM stream-stall detection beyond the fallback plugin's existing
  error-retry (`timeout_seconds: 45` covers provider errors, not silent
  stalls) — now filed as **BITB-270**
- Any change to opencode core (the deadlock is an upstream limitation) —
  upstream issue now filed as **BITB-271**

## References

- Incident log forensics: `~/.local/share/opencode/log/opencode.log`
  (`ses_e47c00c61…`, `message=asking que_1b8462d6…` at 23:09:29,
  `error=Aborted` at 08:36:14)
- BITB-169 (task-reliability plugin), BITB-236 (fallback model posture),
  BITB-128 (PVC persistence), BITB-235 (story-ID allocation)

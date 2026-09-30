# BITB-169: Reliable Orchestrator↔Subagent Comms — Task-Reliability Plugin + Registry

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M
**Created:** 2026-09-30
**Found by:** Live delegation-fault diagnosis, 2026-09-30 (see *Why This Exists*); runbook
first aid already codified in the orchestrator definition (PR #1121)

## User Story

**As** the orchestrator, **I want** a cancelled task dispatch to always tell me where the
detached subagent session lives and how to recover its result, **so that** a transient model
503 never silently discards completed subagent work or spawns duplicate detached sessions.

## Why This Exists

Observed live on 2026-09-30 while verifying that subagent delegation works:

1. Two verifier dispatches returned `Task cancelled` to the parent task call — but the runtime
   log shows both subagent sessions **were created, hit a 503**
   (`Upstream error from Nvidia: Service temporarily overloaded` on
   `opencode/nemotron-3-ultra-free`), **recovered on the fallback model via the
   `opencode-runtime-fallback` plugin, and completed all 45 verification steps** — detached.
2. So the fallback works at the **session** level (it replays `chat.message` on a fallback
   model), but the parent's in-flight **task tool call** is torn down by the same stream error
   → the parent gets a dead-end `Task cancelled` while the child runs on.
3. The orchestrator's blind retry then duplicated the entire verification in a second detached
   session — pure waste.
4. Recovery *is* possible (proven: resuming the finished session via the task tool with
   `task_id=<ses_...>` returned its full report), but today it requires grepping the runtime
   log for the session id — and the log (and all session state) lives under
   `/tmp/.local/share/opencode/`, which is **not persisted** across pod restarts (BITB-128:
   only the workspace volume is). After a pod restart, detached sessions and the log are gone.

The broken link is therefore not the fallback (working) and not the dispatch pipeline
(working — a trivial seo-auditor dispatch returned its result normally seconds after the
verifier cancels) — it is the **result channel of the in-flight task call**.

## Design — Three Layers

### L0 — Operational discipline (no code; mostly the PR #1121 runbook)

- **Unique task tokens:** every task dispatch `description` carries a unique token
  (e.g. `[T-<short-random>] verify PR 1120`) — today's two verifier dispatches had identical
  titles, making log/registry greps ambiguous.
- **Probe-first for long, critical dispatches:** a trivial smoke task to the same agent before
  a big one; if it returns, the provider is healthy, shrinking the 503-at-dispatch window.
- **Prefer smaller-grained subtasks:** shorter exposure window and less duplicate-work waste
  when a cancel does happen.
- **Never blindly re-dispatch on `Task cancelled`** (PR #1121 orchestrator runbook).

### L1 — `task-reliability` plugin (the real fix; ~80 lines of TypeScript)

A local plugin at `.opencode/plugin/task-reliability.ts` (auto-discovered — no config entry
needed). Hook surface verified against the installed `opencode-runtime-fallback@0.2.4`
package, whose own hooks prove the API: `event`, `tool.execute.after`
(`{tool, sessionID, callID, args}` → `{title, output, metadata}` mutable in place),
`tool.definition`. Bus event names extracted from its compiled source: `session.created`,
`session.idle`, `session.stop`, `session.error`, `session.deleted`.

- **`event` hook — durable dispatch registry:** on `session.created` for a session with a
  parent (subagent), append `{childID, parentID, agent, title/token, created, status:"running"}`
  to `/workspace/.opencode/task-registry.json` — on the **workspace PVC**, so it survives pod
  restarts (unlike `/tmp` log and session state). On `session.idle` / `session.stop` /
  `session.error` / `session.deleted`, update the matching entry (`idle` = loop finished =
  result collectable via resume).
- **`tool.execute.after` hook — cancel enrichment:** when `tool === "task"` and the output
  indicates cancellation (substring/metadata match, written defensively), mutate the output
  in place to append:
  *"Task cancelled mid-dispatch — the subagent session may still be alive on a fallback model.
  Do NOT re-dispatch. Registry: /workspace/.opencode/task-registry.json; recover by resuming
  the child session with task_id=<id>."*
  The orchestrator can then never receive a dead-end cancel — the recovery path arrives in
  the very message that reports the failure.
- **`tool.definition` hook — protocol in the tool description:** append the recovery protocol
  to the task tool's description (prompt real-estate the orchestrator is guaranteed to see at
  dispatch time), complementing the orchestrator.md runbook.
- **Defensive throughout:** every hook wrapped in try/catch; unknown event/output shapes are
  no-ops; the plugin must never break a tool call or throw.

### L2 — Result mailbox (pod-restart-proof; optional, ship after L1)

- **Write-capable agents** (fullstack-engineer, android-expert, android-gemini,
  data-engineer, verse-parity-keeper): as a final step, also drop their report at
  `/workspace/.opencode/task-results/<token>.md`.
- **Read-only agents** (verifier, risk-auditor, seo-auditor, failure-forecaster): they rely on
  L1 registry + resume (proven 2026-09-30), or optionally get a path-scoped write permission
  for that one directory.
- **Why it matters:** L1's registry survives pod restarts, but the child *session state* lives
  under `/tmp/.local/share/opencode` and dies with the pod — so resume-based recovery only
  works within a pod's lifetime. The mailbox on the PVC is the only result store that
  outlives a restart (e.g. the orchestrator's own session dies mid-verification; the next
  session finds the finished report on disk).

## Acceptance Criteria

- [ ] Every task dispatch carries a unique token in its description (L0, orchestrator runbook
      update if needed)
- [ ] `.opencode/plugin/task-reliability.ts` exists and is auto-discovered (verify in the
      startup log) without breaking opencode startup or any tool call
- [ ] Subagent session creation appends a registry entry; idle/stop/error updates its status;
      registry file lives at `/workspace/.opencode/task-registry.json` (PVC path)
- [ ] A cancelled task tool output is enriched with the recovery message + child session id
      (or registry pointer) — demonstrated by a live test that triggers a cancel (or a
      simulated one)
- [ ] `tool.definition` for `task` includes the recovery protocol
- [ ] Plugin is inert-by-design on unexpected shapes: no throw, no swallowed tool results
- [ ] (L2, if in scope) mailbox convention added to the write-capable agent definitions with
      the drop-file step, and either resume-path documentation or path-scoped write
      permission for read-only agents
- [ ] Docs: the orchestrator runbook (PR #1121 section) updated to read the registry first
      instead of grepping the log
- [ ] Tests where testable: a small unit test for the registry read/write helpers
      (pure functions), and a startup smoke check (`make verify-opencode-config` extended or
      a new target that asserts the plugin loads)

## Open Questions (implementation must verify)

1. **How does a local plugin file reach the KubeOpenCode pod?** The deployment ships
   `opencode.json` via ConfigMap (`spec.configRef`); does the pod also get the repo clone
   (and therefore `.opencode/plugin/`)? Check `deployment/kubeopencode/agent.yaml` — if only
   the ConfigMap ships, the plugin needs a different delivery (ConfigMap-mounted file under
   the plugin scan path, or published as an npm package pinned in `opencode.json`).
2. **Exact `session.created` / `session.idle` event property shapes** on opencode 1.18.31
   (fields for `parentID`, agent name, title) — handle defensively, log what arrives on
   first contact.
3. **Exact cancelled-output shape of the task tool** (string `"Task cancelled"` vs structured
   metadata) — detect broadly and never break on mismatch.
4. Registry concurrency: events can interleave; keep appends atomic
   (read-modify-write with a write queue, or append-only JSONL — JSONL is simpler and
   crash-safe; prefer it).

## Out of Scope

- Swapping subagent primary models to paid/reliable endpoints (owner cost decision)
- Modifying opencode core or the `opencode-runtime-fallback` plugin itself (a possible
  future upstream contribution: their fallback already owns the retry; the orphaned-parent
  case is our gap to patch locally first)
- Any change to the product (api/, frontend/, android/)

## Dependencies & Caveats

- PR #1121 (orchestrator runbook) is the L0 first aid and the place the L1 pointer will be
  added after this story lands.
- The 503 window is a property of the free-tier primary model; L1/L2 make its consequences
  recoverable, not rarer — only a model change reduces frequency.

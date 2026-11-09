# BITB-270: LLM Stream-Stall Watchdog — Silent Provider Stream Freezes Are Not Covered by Error-Driven Fallback

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M
**Created:** 2026-11-08
**Follow-up to:** BITB-269 (deferred as out-of-scope item 1)

## User Story

**As the** orchestrator of a multi-agent opencode session,
**I want** any in-flight LLM stream that stops producing tokens without
erroring or closing to be detected and recovered within minutes,
**so that** a single silently-stalled stream can never wedge a subagent
session — and through it, the parent's dispatch — indefinitely.

## Background — two hang classes, only one fixed

The 2026-11-07 incident forensics (BITB-269) surfaced two distinct
liveness holes in the runtime:

1. **Class A — subagent question-tool deadlock** (the actual incident):
   fixed by BITB-269 (`question: deny`, watchdog abort, resume ritual).
2. **Class B — silent stream stall** (uncovered, hypothetical until it
   bites): a provider stream that opens, emits partial output, then goes
   quiet **without closing** produces *no error*. The runtime-fallback
   plugin (`opencode-runtime-fallback@0.2.4`) is strictly error-driven —
   `retry_on_errors` [400,401,402,403,429,500,502,503,504] +
   `retryable_error_patterns` + `timeout_seconds: 45` — so a stalled
   stream trips **nothing**; message processing waits forever. The
   BITB-269 stuck-child watchdog eventually aborts after
   `TASK_RELIABILITY_STUCK_SECONDS` (default 1200 s), but that is (a) a
   long wedge, (b) lossy — abort ≠ recovery: the turn is lost, not
   retried — and (c) unable to distinguish "stream idle" from "child
   legitimately inside a long bash command".

In the incident log, the child's last events were
`message=stream … modelID=z-ai/glm-5.3` at 23:09:21 followed by
`message=asking` at 23:09:29 — the stream *completed* there (Class A
struck afterwards). But had that stream itself hung at 23:09:21 with no
`asking` line, every downstream symptom would have been identical, and
*none* of the BITB-269 mitigations would have prevented the parent wedge
— only the slow 1200 s watchdog abort would have limited it.

## Requirements

1. **Observability findings first (document in this story):**
   - Which bus events fire during streaming (e.g. `message.updated`
     payload shapes — do they carry token deltas/timestamps usable as
     heartbeat?), and what `client.session.abort` does to an in-flight
     message: does the loop re-issue the turn (ideally through the
     runtime-fallback machinery onto a fallback model), or is the turn
     lost and the session parked/idle?
   - Whether opencode config offers a native stream/request idle timeout
     (check the config schema at <https://opencode.ai/config.json> for
     the version in use, 1.18.31, and any newer release notes). If a
     native knob appears, prefer config over plugin code and record the
     version that introduced it.
2. **Stream-idle detection** (extend `.opencode/plugin/task-reliability.ts`
   or add a companion plugin — implementer's choice, documented):
   - Track last-activity per active subagent message from streaming
     events; when idle > `STREAM_IDLE_SECONDS` (env, default ~180 s —
     deliberately far tighter than the 1200 s stuck threshold), abort
     the session best-effort and append a registry line
     (`status: "stalled-stream"`) so the orchestrator's recovery
     protocol can re-dispatch with the registry as source of truth.
   - If the observability findings show abort *re-drives* the loop
     (retry/fallback), wire that path — that is the preferred outcome:
     stall becomes a self-healing blip instead of a lost turn.
   - The threshold must only apply to *streaming* phases — a child inside
     a legitimate long bash run (pytest suites, pip installs) must not
     be flagged as stalled-stream. If streaming state is not
     distinguishable from bash-waiting in the event surface, document
     that and fall back to a conservative threshold with the distinction
     between this and the generic stuck watchdog made explicit.
3. **Preserve the inert-by-design contract** (every hook try/catch, no
   top-level side effects, never break a tool call or startup).
4. **Tests** via `node --experimental-strip-types --test`: idle stream
   detected, actively-streaming message not flagged, terminal messages
   untracked, threshold respected (no double-fire), inert on malformed
   events; no regression in the existing suites.

## Acceptance Criteria

- [ ] Observability findings documented in this story (event shapes,
      abort semantics, native-knob verdict)
- [ ] Stream-idle detection + best-effort abort + registry line
      implemented, env-thresholdable (`STREAM_IDLE_SECONDS`)
- [ ] Interplay with `TASK_RELIABILITY_STUCK_SECONDS` documented
      (stream-idle is the fast path for streams; stuck remains the
      catch-all for hung tools/bash)
- [ ] Plugin test suite green including the new tests; generator suite
      green
- [ ] `make pre-commit` passes; PR CI green
- [ ] (owner, after merge + sync + pod restart) registry shows normal
      `created`/`status` lines on real dispatches; stall behavior
      verified only if the class occurs naturally — do not induce
      stalls in production

## Out of Scope

- Any change to opencode core stream handling — that belongs upstream
  (see BITB-271 for the upstream-issue story; add the stream-stall
  angle there if the upstream issue for the question deadlock is filed
  first — separate concerns, possibly one issue each)
- Provider-side retries beyond what the runtime-fallback plugin already
  does once an error *is* produced

## References

- BITB-269 (parent incident + plugin/watchdog foundation this builds on)
- `.opencode/plugin/task-reliability.ts` + `task-reliability.test.ts`
- `scripts/generate-opencode-config.py` (`PLUGIN` list, fallback plugin
  config: retry_on_errors, timeout_seconds)

# BITB-270: LLM Stream-Stall Watchdog — Silent Provider Stream Freezes Are Not Covered by Error-Driven Fallback

**Status:** 🔄 In progress — implementation + proofs done, PR pending review
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

## Observability Findings (requirement 1 — empirical, scratch probes 2026-11-09)

All findings re-verified against the pinned pod binary (opencode 1.18.31,
`/tools/opencode`) with isolated HOME/XDG scratch instances and an
OpenAI-compatible **hanging mock provider** (streams role + two text deltas,
then never closes — the exact Class B stall). Probe artifacts under
`/tmp/opencode/bitb270-*` (probe setup documented in the PR).

### 1. Event surface — streaming vs tool-in-flight are cleanly distinguishable

- **Streaming heartbeat**: `message.part.delta` bus events —
  `{type, properties: {sessionID, messageID, partID, field: "text",
  delta: "<token>"}}` — one per token chunk. 81 deltas observed on a plain
  120-word generation. This is the heartbeat the watchdog uses.
- **Tool in flight**: `message.part.updated` with
  `properties.part.type === "tool"` and
  `properties.part.state.status === "running"` (empirically: `"pending"` →
  `"running"` (×2, with input/metadata fills) → `"completed"`, carrying
  `state.time.start`/exit metadata). During a 20 s `sleep 20` bash run the
  child emitted **zero** `message.part.delta` events — deltas and tool runs
  never overlap. So the guard is: a tool part in `running`/`pending` state
  ⇒ bash-waiting, never a stream stall. `tool.execute.before` also exists on
  the plugin hook surface, but the part events are sufficient and carry the
  sessionID directly.
- **Session idle**: `session.idle` (`properties.sessionID`) marks the loop
  finished — the watchdog clears stream tracking there, so a collectable
  idle child is never falsely flagged.

### 2. Abort semantics — `client.session.abort` CANNOT abort an in-flight stream in 1.18.31

Probed directly: a plugin captured its `client` (present on the plugin
input: `{client, project, worktree, directory, experimental_workspace,
serverUrl, $}`; `client.session` exists) and called
`client.session.abort({path: {sessionID}})` against its own session
mid-generation. Result:

```
UnknownError: "Unexpected server error. Check server logs for details."
ref err_364d394a
```

The endpoint errors on the exact state we need it for (in-flight
generation). The e2e stall run confirms the downstream effect: registry
line written, abort no-ops, the child stays wedged (no error/idle events,
no fallback request) and the parent's task call remains blocked. **Verdict:
lossy — the deliverable is detect + `status: "stalled-stream"` registry
line + best-effort abort (kept: it costs nothing and may work in other
states or future versions) + the parent-side re-dispatch/recovery via the
registry (the existing BITB-169 protocol: the orchestrator reads the line,
aborts/re-dispatches as it would for a stuck child).** No self-healing
re-drive is possible from plugin land in 1.18.31.

### 3. Native knob — `chunkTimeout` exists in the config schema, enforced for custom providers only

The config schema (https://opencode.ai/config.json) exposes a per-provider
`options.chunkTimeout`: *"Timeout in milliseconds between streamed SSE
chunks for this provider (default: 300000). If no chunk arrives within
this window, the request is aborted."* Empirically on 1.18.31:

- **Custom OpenAI-compatible provider: honored.** With
  `chunkTimeout: 15000`, a hanging stream aborted at ~15 s. But the abort
  is **silent-lossy**: no error event, the runtime-fallback plugin never
  fired (its log stayed empty), and the partial text ("Stall probe.")
  became the assistant's final answer. A tripwire, not a recovery.
- **Built-in OpenRouter provider: NOT honored.** With
  `provider.openrouter.options.baseURL` redirected at the mock (proving
  the options block merges into built-in providers — both title and
  primary requests hit the mock) and `chunkTimeout: 15000`, the stalled
  stream was still in flight at the 150 s probe bound; no abort, no retry,
  no second request. The pod's real traffic (OpenRouter, built-in) gets no
  native protection in 1.18.31.
- **Verdict**: the native knob is real but (a) not enforced on the
  provider the pod actually uses, and (b) lossy-silent where it is
  enforced. The plugin watchdog is the near-term fix; `chunkTimeout` is
  recorded as the preferred long-term replacement **if** a future opencode
  release enforces it for built-in providers AND surfaces the abort as an
  error the runtime-fallback plugin can catch (revisit when the pod's
  pinned image (`oc<x.y.z>` in `deployment`/`k8s` agent manifests) is
  upgraded — see BITB-271 for the upstream tracking).

### 4. Probe artifacts worth recording

- The scratch probes see **two plugin instances** when the pod's
  `/tools/opencode.json` (compiled into the kubeopencode binary) leaks its
  config-listed plugin (shared-checkout copy) into the scratch instance —
  the registry shows duplicated `created`/`idle` lines ~3 ms apart. The
  live pod runs ONE instance (its config lists a single plugin path); the
  duplicates are a probe artifact (harmless — the registry tolerates them,
  `findActiveChild` reads the latest).
- The 2026-11-07 incident's "no first token received" line was the
  **runtime-fallback plugin's own** 45 s no-first-token watchdog (it fired
  in the BITB-279 incident), *not* opencode core — that case is covered by
  the fallback plugin; the Class B mid-stream freeze is the uncovered one.

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

## Design chosen (requirement 2: "extend the existing plugin or add a companion — implementer's choice")

**Extended `.opencode/plugin/task-reliability.ts` + helpers** rather than
adding a companion plugin: the stream-idle watchdog shares the stuck
watchdog's sweep loop, registry, tracked-children map, abort helper and
inert-by-design scaffolding — a second plugin would duplicate all of it
AND add a second `file://` entry the 1.18.31 loader must accept. The
distinguishing state lives in three new `WatchdogState` fields
(`lastStreamActivity`, `toolInFlight`, `streamMarked`):

- `message.part.delta` / `message.part.updated` bus events for a tracked
  child refresh `lastStreamActivity`; a tool part entering
  `running`/`pending` sets the `toolInFlight` guard (bash-waiting ≠
  stall); `completed`/`error`/… clears it and re-arms the clock; the
  clock also arms at spawn (a first token that never arrives is a stall);
  `session.idle` clears stream tracking (a collectable idle child is
  never flagged).
- `detectStreamStalls` fires once per stall per child (re-armed by any
  stream signal); the sweep appends one
  `status: "stalled-stream"` registry line and attempts the best-effort
  abort — identical shape to the BITB-269 stuck path it extends.
- Sweep cadence follows the **tighter** of the two thresholds
  (`min(sweepIntervalMs(stuck), sweepIntervalMs(streamIdle))`, clamped to
  [1 s, 60 s]) so a low `STREAM_IDLE_SECONDS` is honored.
- **Interplay (requirement 3):** stream-idle is the FAST path (default
  180 s) for streaming phases only, with the tool-in-flight guard; the
  1200 s `TASK_RELIABILITY_STUCK_SECONDS` watchdog remains the catch-all
  for hung tools/bash and any activity the stream clock cannot see. A
  long bash run (>180 s) triggers NOTHING from the stream watchdog (the
  guard holds) and only the stuck watchdog after 1200 s; a frozen stream
  triggers the stream watchdog at ~180 s and the stuck watchdog would
  double-mark at 1200 s only if the child somehow stayed alive and
  un-aborted — the registry records both distinctly.

## End-to-end proof (scratch only; hanging mock provider)

`STREAM_IDLE_SECONDS=10`, mock provider with `chunkTimeout: false` (native
knob disabled so the plugin is the only detector), parent on the real
provider dispatching a `stallprobe` subagent (model `mock-hang` —
streams two deltas then never closes):

- **Stall run**: registry gained, ~18 s after spawn —

  ```json
  {"ts":"2026-11-09T13:49:47.220Z","kind":"created","childID":"ses_e3f6d86b7ffe…","parentID":"ses_e3f6daa22ffe…","agent":"stallprobe","title":"Stall probe test (@stallprobe subagent)"}
  {"ts":"2026-11-09T13:50:05.114Z","kind":"status","childID":"ses_e3f6d86b7ffe…","status":"stalled-stream"}
  ```

  The abort no-opped (finding 2 — expected); no further child events,
  no fallback request: the wedge is *observable and attributed* instead of
  silent, and the orchestrator's registry-driven recovery applies.
- **Control run** (model `mock-ok`, same setup): dispatch completed
  (`✓ … subagent`), parent replied, exit=0, registry shows
  `created` + `status: idle` and **no** `stalled-stream` line:

  ```json
  {"ts":"2026-11-09T14:11:58.838Z","kind":"created","childID":"ses_e3f59354bffe…","parentID":"ses_e3f596fe8ffe…","agent":"stallprobe","title":"Test stallprobe subagent (@stallprobe subagent)"}
  {"ts":"2026-11-09T14:12:08.001Z","kind":"status","childID":"ses_e3f59354bffe…","status":"idle"}
  ```

- Unit suite: **37/37** (`node --experimental-strip-types --test`),
  8 new tests covering: stall fires once past the threshold and re-arms on
  activity; actively-streaming never flagged; tool-in-flight guarded
  (fires only after the tool completes and the clock re-expires);
  `session.idle` clears tracking; terminal untrack; malformed-part inert;
  untracked top-level sessions ignored; `STREAM_IDLE_SECONDS` env parsing.
  The single-export loader-contract tests stay green.

## Acceptance Criteria

- [x] Observability findings documented in this story (event shapes,
      abort semantics, native-knob verdict — sections 1–3 above)
- [x] Stream-idle detection + best-effort abort + registry line
      implemented, env-thresholdable (`STREAM_IDLE_SECONDS`, default 180)
- [x] Interplay with `TASK_RELIABILITY_STUCK_SECONDS` documented
      (stream-idle is the fast path for streams; stuck remains the
      catch-all for hung tools/bash)
- [x] Plugin test suite green including the new tests (37/37); generator
      suite green
- [x] `make pre-commit` passes; PR CI green
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

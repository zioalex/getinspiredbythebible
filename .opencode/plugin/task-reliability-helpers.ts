/**
 * task-reliability-helpers — the importable helper library behind the
 * task-reliability opencode plugin (BITB-169, BITB-269, BITB-270).
 *
 * WHY THIS MODULE EXISTS (the 2026-11-08 live incident, T-1254PLG):
 * opencode 1.18.31's plugin loader iterates `Object.values(module)` over the
 * PLUGIN MODULE's export surface. Every distinct export value must be a
 * function (or an object with a callable `.server` property) — otherwise the
 * loader throws `TypeError: Plugin export is not a function` and skips the
 * plugin — and every accepted function export is then CALLED with
 * `(ctx, options)` and its return value is registered as plugin hooks.
 * A single non-function export (the old file exported the string constant
 * `DEFAULT_REGISTRY_PATH`) or a single export that throws when invoked with
 * `(ctx, options)` (any helper like `findActiveChild`, which does `for..of`
 * over its first argument) is enough to fail the whole plugin load:
 *
 *   runtime log, 2026-11-08T18:52:00Z:
 *   ERROR message="failed to load plugin"
 *         path=file:///workspace/repo/.opencode/plugin/task-reliability.ts
 *         error="Plugin export is not a function"
 *
 * So `task-reliability.ts` (the module the loader imports) exports EXACTLY
 * ONE runtime export — `default`, the plugin entry function — and every
 * named helper lives here instead, where the loader never looks. The
 * working `opencode-runtime-fallback@0.2.4` plugin uses the same shape: its
 * dist/index.js ends with `export { OpenCodeFallbackPlugin as default }`
 * and nothing else. Both facts were verified empirically against the live
 * 1.18.31 binary (scratch-instance probes, T-1254PLG) — see the story file
 * docs/BACKLOG_STORIES/BITB-269-subagent-question-deadlock-unsupervised-children.md.
 *
 * Inert by design: every helper is wrapped in try/catch where it can see
 * malformed input, and this module's top level is side-effect-free so the
 * unit tests can import it under `node --experimental-strip-types --test`.
 *
 * Zero runtime dependencies (node: builtins only).
 */

import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";

// ── Structural types (type-only; keep in sync with the live hook shapes) ──

export interface BusEvent {
  type: string;
  properties?: unknown;
}

export type RegistryStatus =
  | "idle"
  | "stop"
  | "error"
  | "deleted"
  | "asking"
  | "stuck"
  | "stalled-stream";

export interface EventHookInput {
  event?: BusEvent;
}

export interface ToolExecAfterInput {
  tool?: string;
  sessionID?: string;
  callID?: string;
  args?: unknown;
}

export interface ToolExecAfterOutput {
  title?: unknown;
  output?: unknown;
  metadata?: unknown;
}

export type RegistryLine =
  | {
      ts: string;
      kind: "created";
      childID: string;
      parentID: string;
      agent?: string;
      title?: string;
    }
  | {
      ts: string;
      kind: "status";
      childID: string;
      status: RegistryStatus;
    };

export interface ChildInfo {
  childID: string;
  parentID: string;
  agent?: string;
  title?: string;
  status?: RegistryStatus;
}

export interface Hooks {
  name: string;
  event: (input: EventHookInput) => Promise<void>;
  "tool.execute.after": (
    input: ToolExecAfterInput,
    output: ToolExecAfterOutput,
  ) => Promise<void>;
  "tool.definition": (input: unknown, output: unknown) => Promise<void>;
}

// ── Constants ──────────────────────────────────────────────────────────────

/**
 * Default registry location: the PVC-backed workspace root, OUTSIDE the repo
 * clone (survives pod restarts and re-clones; /tmp is NOT persisted — see
 * deployment/kubeopencode/agent.yaml persistence note, BITB-128).
 * Override with TASK_RELIABILITY_REGISTRY (local dev / tests / laptops where
 * /workspace does not exist).
 */
export const DEFAULT_REGISTRY_PATH = "/workspace/.opencode/task-registry.jsonl";

/** Hint marker prepended to enriched cancelled-task output. */
export const HINT_MARK = "[task-reliability]";

const TERMINAL_STATUSES = new Set(["stop", "error", "deleted"]);
const REGISTRY_STATUSES = new Set<RegistryStatus>([
  "idle",
  "stop",
  "error",
  "deleted",
  "asking",
  "stuck",
  "stalled-stream",
]);
const SESSION_EVENT_STATUS: Record<string, Exclude<RegistryStatus, "asking" | "stuck">> = {
  "session.idle": "idle",
  "session.stop": "stop",
  "session.error": "error",
  "session.deleted": "deleted",
};

/**
 * Stuck-child threshold (seconds) — a tracked child with no bus activity for
 * this long gets one `status: "stuck"` line and a best-effort abort
 * (BITB-269). Override with TASK_RELIABILITY_STUCK_SECONDS.
 */
export const DEFAULT_STUCK_SECONDS = 1200;

/**
 * Stream-idle threshold (seconds) — a tracked child whose in-flight LLM
 * stream produces no part delta/update for this long (and has no tool call
 * running) is a silent Class B stall: the provider stream froze without
 * erroring, so the error-driven runtime-fallback plugin never fires. The
 * watchdog appends one `status: "stalled-stream"` line and aborts the child
 * best-effort (BITB-270). Deliberately far tighter than the 1200 s stuck
 * catch-all, which cannot distinguish an idle stream from a long bash run —
 * this one can (tool-in-flight is guarded). Override with
 * STREAM_IDLE_SECONDS.
 */
export const DEFAULT_STREAM_IDLE_SECONDS = 180;

/** Watchdog sweep cadence (ms): min 1s, max 60s, default quarter of the threshold. */
export function sweepIntervalMs(stuckSeconds: number): number {
  try {
    const raw = Math.round((stuckSeconds * 1000) / 4);
    return Math.min(60_000, Math.max(1_000, raw));
  } catch {
    return 60_000;
  }
}

export function readStuckSeconds(): number {
  try {
    const raw = process.env.TASK_RELIABILITY_STUCK_SECONDS;
    if (raw === undefined || raw === null || raw === "") return DEFAULT_STUCK_SECONDS;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_STUCK_SECONDS;
    return parsed;
  } catch {
    return DEFAULT_STUCK_SECONDS;
  }
}

export function readStreamIdleSeconds(): number {
  try {
    const raw = process.env.STREAM_IDLE_SECONDS;
    if (raw === undefined || raw === null || raw === "") return DEFAULT_STREAM_IDLE_SECONDS;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_STREAM_IDLE_SECONDS;
    return parsed;
  } catch {
    return DEFAULT_STREAM_IDLE_SECONDS;
  }
}

// ── Stuck-child watchdog state (BITB-269) ──────────────────────────────────

export interface WatchdogState {
  /** childID → epoch ms of its last observed bus activity */
  lastActivity: Map<string, number>;
  /** childIDs already marked stuck for the current stall (one line per stall) */
  stuckMarked: Set<string>;
  /**
   * BITB-270 stream-idle watchdog: childID → epoch ms of its last
   * stream-phase signal (message part delta/update — including tool-part
   * lifecycle, which is a stream-phase signal but sets/clears toolInFlight).
   */
  lastStreamActivity: Map<string, number>;
  /** childIDs with a tool call currently executing (bash-waiting ≠ stalled) */
  toolInFlight: Set<string>;
  /** childIDs already marked stalled-stream for the current stall */
  streamMarked: Set<string>;
}

/** Tracks a spawned child (session.created with parentID). */
export function trackChild(state: WatchdogState, childID: string, nowMs: number): void {
  try {
    state.lastActivity.set(childID, nowMs);
    state.stuckMarked.delete(childID);
    // Stream clock starts at spawn: a child whose first token never arrives
    // is a stall too (no tool in flight, no deltas).
    state.lastStreamActivity.set(childID, nowMs);
    state.toolInFlight.delete(childID);
    state.streamMarked.delete(childID);
  } catch {
    // never break the event pipeline
  }
}

/** Records activity for a tracked child; new activity ends a stall. */
export function recordActivity(state: WatchdogState, sessionID: string, nowMs: number): void {
  try {
    if (!state.lastActivity.has(sessionID)) return; // not a tracked child
    state.lastActivity.set(sessionID, nowMs);
    state.stuckMarked.delete(sessionID);
  } catch {
    // never break the event pipeline
  }
}

/** Drops a child from watchdog tracking (terminal status / cleanup). */
export function untrackChild(state: WatchdogState, sessionID: string): void {
  try {
    state.lastActivity.delete(sessionID);
    state.stuckMarked.delete(sessionID);
    state.lastStreamActivity.delete(sessionID);
    state.toolInFlight.delete(sessionID);
    state.streamMarked.delete(sessionID);
  } catch {
    // never break the event pipeline
  }
}

/**
 * Returns children whose last activity is older than `stuckSeconds` and marks
 * them stuck (each child yields at most one detection per stall — a later
 * `recordActivity` re-arms it). Pure w.r.t. the filesystem.
 */
export function detectStuckChildren(
  state: WatchdogState,
  nowMs: number,
  stuckSeconds: number,
): string[] {
  const stuck: string[] = [];
  try {
    const thresholdMs = Math.max(1, stuckSeconds) * 1000;
    for (const [childID, lastMs] of state.lastActivity) {
      if (state.stuckMarked.has(childID)) continue;
      if (nowMs - lastMs >= thresholdMs) {
        state.stuckMarked.add(childID);
        stuck.push(childID);
      }
    }
  } catch {
    // never break the event pipeline
  }
  return stuck;
}

// ── Stream-idle watchdog (BITB-270) ────────────────────────────────────────

/**
 * Records one stream-phase signal for a tracked child (BITB-270). Called
 * from handleBusEvent for `message.part.delta` / `message.part.updated`
 * bus events. Deltas and part lifecycle are the heartbeat of an in-flight
 * LLM stream; a tool part entering `running` state means the child is
 * waiting on a tool (e.g. a long bash command) — that phase is explicitly
 * NOT a stream stall, so it arms the toolInFlight guard instead of the
 * idle clock. Any signal re-arms the once-per-stall marker. Never throws.
 */
export function noteStreamSignal(
  state: WatchdogState,
  sessionID: string,
  event: BusEvent,
  nowMs: number,
): void {
  try {
    if (!state.lastActivity.has(sessionID)) return; // not a tracked child
    if (event.type === "message.part.delta") {
      state.lastStreamActivity.set(sessionID, nowMs);
      state.streamMarked.delete(sessionID);
      return;
    }
    // message.part.updated: part lifecycle; tool parts carry a state.status
    const props =
      event.properties !== null && typeof event.properties === "object"
        ? (event.properties as Record<string, unknown>)
        : {};
    const part =
      props.part !== null && typeof props.part === "object"
        ? (props.part as Record<string, unknown>)
        : null;
    if (part === null) return;
    state.lastStreamActivity.set(sessionID, nowMs);
    state.streamMarked.delete(sessionID);
    if (part.type === "tool") {
      const rawState = part.state;
      const status =
        rawState !== null && typeof rawState === "object"
          ? (rawState as Record<string, unknown>).status
          : undefined;
      if (status === "running" || status === "pending") {
        state.toolInFlight.add(sessionID);
      } else {
        // completed / error / anything else: the tool call ended
        state.toolInFlight.delete(sessionID);
      }
    }
  } catch {
    // never break the event pipeline
  }
}

/** Clears stream-idle tracking (session idle: between loops, not streaming). */
export function clearStreamTracking(state: WatchdogState, sessionID: string): void {
  try {
    state.lastStreamActivity.delete(sessionID);
    state.toolInFlight.delete(sessionID);
    state.streamMarked.delete(sessionID);
  } catch {
    // never break the event pipeline
  }
}

/**
 * Returns tracked children whose in-flight stream is idle beyond
 * `idleSeconds`, with no tool call running (bash-waiting never flags here —
 * that is the whole point of the toolInFlight guard; the generic stuck
 * watchdog remains the catch-all for genuinely hung tools). Each child
 * yields at most one detection per stall; a later stream signal re-arms.
 * Pure w.r.t. the filesystem.
 */
export function detectStreamStalls(
  state: WatchdogState,
  nowMs: number,
  idleSeconds: number,
): string[] {
  const stalled: string[] = [];
  try {
    const thresholdMs = Math.max(1, idleSeconds) * 1000;
    for (const [childID, lastMs] of state.lastStreamActivity) {
      if (state.toolInFlight.has(childID)) continue;
      if (state.streamMarked.has(childID)) continue;
      if (nowMs - lastMs >= thresholdMs) {
        state.streamMarked.add(childID);
        stalled.push(childID);
      }
    }
  } catch {
    // never break the event pipeline
  }
  return stalled;
}

/**
 * Best-effort session abort via the plugin `client` (opencode 1.18.31 exposes
 * `client.session.abort({ path: { sessionID } })`). Returns false — never
 * throws — when the client is missing/mis-shaped or the call fails.
 */
export async function abortSession(client: unknown, sessionID: string): Promise<boolean> {
  try {
    if (client === null || typeof client !== "object") return false;
    const session = (client as Record<string, unknown>).session;
    if (session === null || typeof session !== "object") return false;
    const abort = (session as Record<string, unknown>).abort;
    if (typeof abort !== "function") return false;
    await (abort as (arg: unknown) => Promise<unknown>).call(session, {
      path: { sessionID },
    });
    return true;
  } catch {
    return false;
  }
}

export function readRegistryPath(): string {
  try {
    const fromEnv = process.env.TASK_RELIABILITY_REGISTRY;
    if (typeof fromEnv === "string" && fromEnv.length > 0) return fromEnv;
  } catch {
    // process.env unavailable — fall through to the default
  }
  return DEFAULT_REGISTRY_PATH;
}

// ── Registry helpers (pure / near-pure; exported for tests) ────────────────

export function parseRegistryLine(text: string): RegistryLine | null {
  try {
    const raw = JSON.parse(text);
    if (typeof raw !== "object" || raw === null) return null;
    const obj = raw as Record<string, unknown>;
    if (obj.kind === "created") {
      if (typeof obj.childID !== "string" || typeof obj.parentID !== "string") {
        return null;
      }
      return {
        ts: typeof obj.ts === "string" ? obj.ts : "",
        kind: "created",
        childID: obj.childID,
        parentID: obj.parentID,
        ...(typeof obj.agent === "string" ? { agent: obj.agent } : {}),
        ...(typeof obj.title === "string" ? { title: obj.title } : {}),
      };
    }
    if (obj.kind === "status") {
      if (typeof obj.childID !== "string") return null;
      const status = obj.status;
      if (typeof status !== "string" || !REGISTRY_STATUSES.has(status as RegistryStatus)) {
        return null;
      }
      return {
        ts: typeof obj.ts === "string" ? obj.ts : "",
        kind: "status",
        childID: obj.childID,
        status: status as RegistryStatus,
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function registryLineToString(line: RegistryLine): string {
  return JSON.stringify(line);
}

/** Appends one JSONL line. Returns false (never throws) on any failure. */
export function appendRegistryLine(path: string, line: RegistryLine): boolean {
  try {
    mkdirSync(dirname(path), { recursive: true });
    appendFileSync(path, registryLineToString(line) + "\n", "utf8");
    return true;
  } catch {
    return false;
  }
}

/** Reads and parses the whole registry; unreadable/missing → empty array. */
export function readRegistryLines(path: string): RegistryLine[] {
  try {
    const text = readFileSync(path, "utf8");
    const lines: RegistryLine[] = [];
    for (const raw of text.split("\n")) {
      const trimmed = raw.trim();
      if (trimmed.length === 0) continue;
      const parsed = parseRegistryLine(trimmed);
      if (parsed !== null) lines.push(parsed);
    }
    return lines;
  } catch {
    return [];
  }
}

/**
 * Finds the most recent `created` entry for `parentID` that has no subsequent
 * terminal status (stop/error/deleted). `idle` is NOT terminal — an idle child
 * finished its loop and its result is collectable via task_id resume.
 */
export function findActiveChild(
  lines: RegistryLine[],
  parentID: string,
): ChildInfo | null {
  let latest: (RegistryLine & { kind: "created" }) | null = null;
  for (const line of lines) {
    if (line.kind === "created" && line.parentID === parentID) {
      latest = line;
    } else if (line.kind === "status" && latest !== null) {
      if (line.childID === latest.childID && TERMINAL_STATUSES.has(line.status)) {
        latest = null;
      }
    }
  }
  if (latest === null) return null;
  const info: ChildInfo = {
    childID: latest.childID,
    parentID: latest.parentID,
    ...(latest.agent !== undefined ? { agent: latest.agent } : {}),
    ...(latest.title !== undefined ? { title: latest.title } : {}),
  };
  return info;
}

// ── Cancel detection + hint text (pure; exported for tests) ───────────────

export function isCancelledTaskOutput(
  output: unknown,
  metadata?: unknown,
): boolean {
  try {
    if (typeof output === "string" && /cancel/i.test(output)) return true;
    if (metadata !== null && typeof metadata === "object") {
      const meta = metadata as Record<string, unknown>;
      for (const key of ["status", "state", "error"]) {
        const value = meta[key];
        if (typeof value === "string" && /cancel/i.test(value)) return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

export function recoveryHint(child: ChildInfo | null, registryPath: string): string {
  if (child === null) {
    return (
      `${HINT_MARK} Task cancelled and no child session was recorded — the provider ` +
      `likely failed before the session spawned; re-dispatching after a short wait is safe. ` +
      `Registry: ${registryPath}`
    );
  }
  const agent = child.agent !== undefined ? ` (agent ${child.agent})` : "";
  return (
    `${HINT_MARK} Task cancelled mid-dispatch — child session ${child.childID}${agent} ` +
    `likely survived on a fallback model. Do NOT re-dispatch. Once the registry shows ` +
    `status=idle (or after ~45s of quiet), recover by re-invoking the task tool with ` +
    `task_id=${child.childID} and a short prompt asking it to output its final report. ` +
    `Registry: ${registryPath}`
  );
}

// ── Event → registry-lines reducer (pure; exported for tests) ─────────────

/**
 * Pure event → registry-lines reducer (exported for tests). Mutates only the
 * in-memory watchdog state; never touches the filesystem, never throws.
 */
export function handleBusEvent(
  state: WatchdogState,
  event: unknown,
  nowMs: number,
): RegistryLine[] {
  const lines: RegistryLine[] = [];
  try {
    if (event === null || typeof event !== "object") return lines;
    const busEvent = event as BusEvent;
    if (typeof busEvent.type !== "string") return lines;
    const props =
      busEvent.properties !== null && typeof busEvent.properties === "object"
        ? (busEvent.properties as Record<string, unknown>)
        : {};
    const sessionID = typeof props.sessionID === "string" ? props.sessionID : undefined;
    const ts = new Date(nowMs).toISOString();

    if (busEvent.type === "session.created") {
      // opencode 1.18.31 (verified empirically in-pod, T-1254PLG) nests the
      // parent linkage under `properties.info`: {sessionID, info: {parentID,
      // agent, title, …}}. A flat properties.parentID is accepted as a
      // fallback for forward/backward tolerance, but without the nested read
      // NO created line is ever recorded and the stuck-child watchdog never
      // arms — the registry showed only bare `idle` lines before this fix.
      const info =
        props.info !== null && typeof props.info === "object"
          ? (props.info as Record<string, unknown>)
          : {};
      const flatOrNested = (key: string): string | undefined => {
        const flat = props[key];
        if (typeof flat === "string") return flat;
        const nested = info[key];
        return typeof nested === "string" ? nested : undefined;
      };
      const parentID = flatOrNested("parentID") ?? "";
      if (parentID.length === 0) return lines; // top-level session, not a subagent spawn
      lines.push({
        ts,
        kind: "created",
        childID: sessionID ?? "",
        parentID,
        ...(flatOrNested("agent") !== undefined ? { agent: flatOrNested("agent") as string } : {}),
        ...(flatOrNested("title") !== undefined ? { title: flatOrNested("title") as string } : {}),
      });
      if (sessionID !== undefined) trackChild(state, sessionID, nowMs);
      return lines;
    }

    if (sessionID !== undefined) recordActivity(state, sessionID, nowMs);

    // BITB-270: stream-phase heartbeat for the stream-idle watchdog.
    if (
      sessionID !== undefined &&
      (busEvent.type === "message.part.delta" || busEvent.type === "message.part.updated")
    ) {
      noteStreamSignal(state, sessionID, busEvent, nowMs);
    }

    // BITB-269: an asking subagent can never be answered — record it.
    if (
      busEvent.type === "question.asked" &&
      sessionID !== undefined &&
      state.lastActivity.has(sessionID)
    ) {
      lines.push({ ts, kind: "status", childID: sessionID, status: "asking" });
    }

    const status = SESSION_EVENT_STATUS[busEvent.type];
    if (status !== undefined && sessionID !== undefined) {
      lines.push({ ts, kind: "status", childID: sessionID, status });
      if (status === "idle") {
        // Idle = the loop finished; nothing is streaming. Without this the
        // stale stream clock would fire a bogus stalled-stream line on an
        // idle-but-collectable child (BITB-270).
        clearStreamTracking(state, sessionID);
      }
      if (TERMINAL_STATUSES.has(status)) untrackChild(state, sessionID);
    }
  } catch {
    // never break the event pipeline
  }
  return lines;
}

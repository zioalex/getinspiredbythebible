/**
 * task-reliability — makes orchestrator↔subagent communication recoverable.
 *
 * BITB-169 (L1). When the runtime-fallback plugin saves a subagent session after
 * a mid-dispatch provider failure (503, etc.), the parent's in-flight task tool
 * call is torn down anyway and reports a bare "Task cancelled" — the surviving
 * child runs on detached and its result never reaches the caller. This plugin:
 *
 *   1. appends every subagent session lifecycle event to a durable JSONL
 *      registry on the persistent workspace volume (survives pod restarts and
 *      re-clones, unlike the non-persistent /tmp runtime log),
 *   2. enriches any cancelled task-tool output in place with the child session
 *      id + recovery instructions, so a cancel is never a dead end,
 *   3. embeds the recovery protocol into the task tool's description, and
 *   4. watches for stuck children (BITB-269): records `question.asked` bus
 *      events for subagent sessions as `status: "asking"` registry lines, and
 *      appends `status: "stuck"` (once per stall) when a tracked child shows no
 *      activity for TASK_RELIABILITY_STUCK_SECONDS (default 1200s). A stuck
 *      child is then aborted best-effort via the plugin `client`
 *      (`client.session.abort`) — the same un-wedge a human prompt performed
 *      in the 2026-11-07 incident, which needed 9h34m to arrive.
 *
 * Inert by design: every hook is wrapped in try/catch, unexpected shapes are
 * no-ops, and this plugin must never break a tool call, a session, or opencode
 * startup. Correctness of that guarantee outranks feature completeness.
 *
 * Zero runtime dependencies (node: builtins only); type-only cross-module
 * imports; side-effect-free module top level, so the helper unit tests can
 * import this file under `node --experimental-strip-types --test`.
 *
 * ⚠ MODULE LAYOUT CONSTRAINT (opencode 1.18.31 plugin-loader contract):
 * This file is the module opencode imports via its `file://` plugin entry.
 * Its export surface must contain EXACTLY ONE runtime export: the default
 * plugin function below. The 1.18.31 loader iterates `Object.values(module)`
 * and (a) rejects the whole module with `TypeError: Plugin export is not a
 * function` if ANY export is not a function (or an object with a callable
 * `.server`), and (b) CALLS every function export with `(ctx, options)`,
 * registering each return value as plugin hooks — so a co-resident helper
 * either fails the load outright (a string/number const: the live
 * 2026-11-08T18:52:00Z `error="Plugin export is not a function"`) or gets
 * invoked with the wrong arguments (`findActiveChild(ctx, …)` → `{} is not
 * iterable`). Every named helper therefore lives in the sibling
 * `task-reliability-helpers.ts`, imported here but NEVER re-exported.
 * `task-reliability.test.ts` asserts this invariant
 * ("plugin module's runtime export surface…"); keep that test green.
 */

import {
  HINT_MARK,
  abortSession,
  appendRegistryLine,
  detectStuckChildren,
  findActiveChild,
  handleBusEvent,
  isCancelledTaskOutput,
  readRegistryLines,
  readRegistryPath,
  readStuckSeconds,
  recoveryHint,
  sweepIntervalMs,
} from "./task-reliability-helpers.ts";

import type {
  EventHookInput,
  Hooks,
  RegistryLine,
  ToolExecAfterInput,
  ToolExecAfterOutput,
  WatchdogState,
} from "./task-reliability-helpers.ts";

// ── Stuck-child watchdog state (BITB-269) ──────────────────────────────────

/**
 * Watchdog state, created lazily by the hooks — the module top level stays
 * side-effect-free so the unit tests can import this file safely.
 */
const watchdog: WatchdogState = {
  lastActivity: new Map<string, number>(),
  stuckMarked: new Set<string>(),
};

/** The plugin `client` captured from the plugin input (has session.abort). */
let capturedClient: unknown = undefined;

/** One-shot inactivity sweep: stuck lines + best-effort abort. Never throws. */
function sweep(nowMs: number): void {
  try {
    const stuck = detectStuckChildren(watchdog, nowMs, readStuckSeconds());
    if (stuck.length === 0) return;
    const registryPath = readRegistryPath();
    const ts = new Date(nowMs).toISOString();
    for (const childID of stuck) {
      const line: RegistryLine = { ts, kind: "status", childID, status: "stuck" };
      appendRegistryLine(registryPath, line);
      // Best-effort un-wedge (BITB-269): the same cancel a human prompt
      // performed 9h34m into the incident, delivered by the watchdog.
      void abortSession(capturedClient, childID).catch(() => {});
    }
  } catch {
    // never break the event pipeline
  }
}

let sweepTimer: ReturnType<typeof setInterval> | null = null;

/** Lazy periodic sweep so a fully quiet pod still detects stuck children. */
function ensureSweepTimer(): void {
  try {
    if (sweepTimer !== null) return;
    if (watchdog.lastActivity.size === 0) return; // nothing to watch yet
    const interval = sweepIntervalMs(readStuckSeconds());
    sweepTimer = setInterval(() => {
      sweep(Date.now());
    }, interval);
    const unref = (sweepTimer as { unref?: () => void }).unref;
    if (typeof unref === "function") unref.call(sweepTimer);
  } catch {
    sweepTimer = null;
  }
}

async function handleEvent({ event }: EventHookInput): Promise<void> {
  try {
    const now = Date.now();
    for (const line of handleBusEvent(watchdog, event, now)) {
      appendRegistryLine(readRegistryPath(), line);
    }
    sweep(now); // cheap: marks at most once per child per stall
    ensureSweepTimer();
  } catch {
    // never break the event pipeline
  }
}

async function handleToolExecAfter(
  input: ToolExecAfterInput,
  output: ToolExecAfterOutput,
): Promise<void> {
  try {
    if (input === null || typeof input !== "object") return;
    if (input.tool !== "task") return;

    const outputText = typeof output?.output === "string" ? output.output : "";
    const metadata = output?.metadata;
    if (!isCancelledTaskOutput(outputText, metadata)) return;
    if (outputText.includes(HINT_MARK)) return; // already enriched — never double-append

    const registryPath = readRegistryPath();
    const child = findActiveChild(readRegistryLines(registryPath), String(input.sessionID ?? ""));
    const hint = recoveryHint(child, registryPath);

    if (typeof output?.output === "string") {
      output.output = outputText + "\n\n" + hint;
    } else if (output !== null && typeof output === "object") {
      (output as Record<string, unknown>).output = hint;
    }
    if (typeof output?.title === "string" && output.title.length === 0) {
      output.title = HINT_MARK;
    }
  } catch {
    // never break a tool call
  }
}

/**
 * The exact tool.definition input/output shape is not verified empirically on
 * opencode 1.18.31 — this hook is deliberately conservative: it looks for a
 * task-tool identity and a description-like string on either object, mutates
 * the description in place, and no-ops on anything unexpected.
 */
async function handleToolDefinition(input: unknown, output: unknown): Promise<void> {
  try {
    const candidates = [input, output].filter(
      (obj): obj is Record<string, unknown> =>
        obj !== null && typeof obj === "object",
    );
    for (const obj of candidates) {
      const name = obj.name ?? obj.tool ?? obj.toolName;
      if (name !== "task") continue;
      if (typeof obj.description !== "string") continue;
      if (obj.description.includes(HINT_MARK)) continue;
      obj.description = obj.description + toolDescriptionProtocol(readRegistryPath());
      return;
    }
  } catch {
    // never break tool definitions
  }
}

function toolDescriptionProtocol(registryPath: string): string {
  return (
    `\n\n[task-reliability protocol] Prefix every dispatch description with a unique token ` +
    `(e.g. "[T-169A]"). If a dispatch returns "Task cancelled", do NOT re-dispatch: read ` +
    `${registryPath} for the child session id and recover it via task_id resume; only ` +
    `re-dispatch if no child session was recorded.`
  );
}

const hooks: Hooks = {
  name: "task-reliability",
  event: handleEvent,
  "tool.execute.after": handleToolExecAfter,
  "tool.definition": handleToolDefinition,
};

/**
 * The plugin entry — the ONLY runtime export of this module.
 *
 * opencode 1.18.31's loader accepts exactly this shape for a `file://` TS
 * plugin: a module whose export surface is functions only, where each
 * function is called as `plugin(ctx, options)` and returns the hooks object
 * (`{ name, event, "tool.execute.after", "tool.definition" }` — the same
 * contract as `opencode-runtime-fallback@0.2.4`, the working reference
 * plugin). Any additional named export on this module breaks plugin loading
 * (see the module header). Keep helpers in task-reliability-helpers.ts.
 */
export default function taskReliabilityPlugin(
  input?: unknown,
  _options?: unknown,
): Promise<Hooks> {
  try {
    // Capture the plugin `client` (opencode 1.18.31 exposes session.abort)
    // for the stuck-child watchdog. Best-effort: a missing/odd client just
    // leaves the registry line as the deliverable.
    if (input !== null && typeof input === "object") {
      const client = (input as Record<string, unknown>).client;
      if (client !== null && (typeof client === "object" || typeof client === "function")) {
        capturedClient = client;
      }
    }
  } catch {
    // never break plugin load
  }
  return Promise.resolve(hooks);
}

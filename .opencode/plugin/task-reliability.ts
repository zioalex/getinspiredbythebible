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
 *      id + recovery instructions, so a cancel is never a dead end, and
 *   3. embeds the recovery protocol into the task tool's description.
 *
 * Inert by design: every hook is wrapped in try/catch, unexpected shapes are
 * no-ops, and this plugin must never break a tool call, a session, or opencode
 * startup. Correctness of that guarantee outranks feature completeness.
 *
 * Zero runtime dependencies (node: builtins only); type-only opencode imports;
 * side-effect-free module top level, so the helper unit tests can import this
 * file under `node --experimental-strip-types --test`.
 */

import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";

// ── Structural types (type-only; keep in sync with the live hook shapes) ──

interface BusEvent {
  type: string;
  properties?: unknown;
}

interface EventHookInput {
  event?: BusEvent;
}

interface ToolExecAfterInput {
  tool?: string;
  sessionID?: string;
  callID?: string;
  args?: unknown;
}

interface ToolExecAfterOutput {
  title?: unknown;
  output?: unknown;
  metadata?: unknown;
}

type RegistryLine =
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
      status: "idle" | "stop" | "error" | "deleted";
    };

export interface ChildInfo {
  childID: string;
  parentID: string;
  agent?: string;
  title?: string;
  status?: "idle" | "stop" | "error" | "deleted";
}

interface Hooks {
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

const HINT_MARK = "[task-reliability]";
const TERMINAL_STATUSES = new Set(["stop", "error", "deleted"]);
const SESSION_EVENT_STATUS: Record<string, "idle" | "stop" | "error" | "deleted"> = {
  "session.idle": "idle",
  "session.stop": "stop",
  "session.error": "error",
  "session.deleted": "deleted",
};

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
      if (
        status !== "idle" &&
        status !== "stop" &&
        status !== "error" &&
        status !== "deleted"
      ) {
        return null;
      }
      return {
        ts: typeof obj.ts === "string" ? obj.ts : "",
        kind: "status",
        childID: obj.childID,
        status,
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

function toolDescriptionProtocol(registryPath: string): string {
  return (
    `\n\n[task-reliability protocol] Prefix every dispatch description with a unique token ` +
    `(e.g. "[T-169A]"). If a dispatch returns "Task cancelled", do NOT re-dispatch: read ` +
    `${registryPath} for the child session id and recover it via task_id resume; only ` +
    `re-dispatch if no child session was recorded.`
  );
}

// ── Hooks ──────────────────────────────────────────────────────────────────

async function handleEvent({ event }: EventHookInput): Promise<void> {
  try {
    if (event === null || typeof event !== "object" || typeof event.type !== "string") {
      return;
    }
    const props =
      event.properties !== null && typeof event.properties === "object"
        ? (event.properties as Record<string, unknown>)
        : ({} as Record<string, unknown>);

    const sessionID = typeof props.sessionID === "string" ? props.sessionID : undefined;
    if (sessionID === undefined) return;

    const registryPath = readRegistryPath();
    const ts = new Date().toISOString();

    if (event.type === "session.created") {
      const parentID = typeof props.parentID === "string" ? props.parentID : undefined;
      if (parentID === undefined || parentID.length === 0) {
        return; // top-level session, not a subagent spawn
      }
      appendRegistryLine(registryPath, {
        ts,
        kind: "created",
        childID: sessionID,
        parentID,
        ...(typeof props.agent === "string" ? { agent: props.agent } : {}),
        ...(typeof props.title === "string" ? { title: props.title } : {}),
      });
      return;
    }

    const status = SESSION_EVENT_STATUS[event.type];
    if (status !== undefined) {
      appendRegistryLine(registryPath, { ts, kind: "status", childID: sessionID, status });
    }
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

const hooks: Hooks = {
  name: "task-reliability",
  event: handleEvent,
  "tool.execute.after": handleToolExecAfter,
  "tool.definition": handleToolDefinition,
};

export default function taskReliabilityPlugin(
  _input?: unknown,
  _options?: unknown,
): Promise<Hooks> {
  return Promise.resolve(hooks);
}

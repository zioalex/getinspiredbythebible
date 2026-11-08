/**
 * Unit tests for the task-reliability plugin (BITB-169) and its helper
 * library (BITB-269 / T-1254PLG).
 *
 * Run with: node --experimental-strip-types --test .opencode/plugin/task-reliability.test.ts
 *
 * Both modules have side-effect-free top levels and zero runtime dependencies
 * beyond node: builtins, so they can be imported directly under Node's TS
 * type-stripping. All filesystem tests run against a temp directory via an
 * explicit path argument — never the real /workspace registry.
 *
 * The helpers live in task-reliability-helpers.ts; task-reliability.ts is the
 * opencode-loaded plugin entry whose export surface must stay exactly one
 * default function (the opencode 1.18.31 loader contract — see the plugin
 * module header). The last two tests enforce that contract: they are the
 * regression tests for the 2026-11-08 live incident where the plugin was
 * rejected with `Plugin export is not a function` because a string constant
 * sat on the plugin module's export surface.
 */

import { appendFileSync as appendFileSyncToTemp, mkdtempSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_REGISTRY_PATH,
  DEFAULT_STUCK_SECONDS,
  abortSession,
  appendRegistryLine,
  detectStuckChildren,
  findActiveChild,
  handleBusEvent,
  isCancelledTaskOutput,
  parseRegistryLine,
  readRegistryLines,
  readRegistryPath,
  readStuckSeconds,
  recordActivity,
  recoveryHint,
  registryLineToString,
  sweepIntervalMs,
  trackChild,
  untrackChild,
  type ChildInfo,
  type RegistryLine,
  type WatchdogState,
} from "./task-reliability-helpers.ts";

const freshState = (): WatchdogState => ({
  lastActivity: new Map(),
  stuckMarked: new Set(),
});

const busEvent = (type: string, properties: Record<string, unknown>): unknown => ({
  type,
  properties,
});

// ── parseRegistryLine ───────────────────────────────────────────────────────

test("parseRegistryLine round-trips a created line", () => {
  const line = registryLineToString({
    ts: "2026-09-30T18:00:00.000Z",
    kind: "created",
    childID: "ses_child",
    parentID: "ses_parent",
    agent: "verifier",
    title: "[T-169A] demo",
  });
  const parsed = parseRegistryLine(line);
  assert.ok(parsed !== null);
  assert.equal(parsed.kind, "created");
  assert.equal(parsed.childID, "ses_child");
  assert.equal(parsed.parentID, "ses_parent");
  if (parsed.kind === "created") {
    assert.equal(parsed.agent, "verifier");
    assert.equal(parsed.title, "[T-169A] demo");
  }
});

test("parseRegistryLine round-trips a status line", () => {
  const line = registryLineToString({
    ts: "2026-09-30T18:01:00.000Z",
    kind: "status",
    childID: "ses_child",
    status: "idle",
  });
  const parsed = parseRegistryLine(line);
  assert.ok(parsed !== null);
  assert.equal(parsed.kind, "status");
  if (parsed.kind === "status") {
    assert.equal(parsed.status, "idle");
  }
});

test("parseRegistryLine returns null on garbage without throwing", () => {
  assert.equal(parseRegistryLine("not json"), null);
  assert.equal(parseRegistryLine(""), null);
  assert.equal(parseRegistryLine('{"kind":"created"}'), null); // missing ids
  assert.equal(parseRegistryLine('{"kind":"status","childID":"x","status":"bogus"}'), null);
  assert.equal(parseRegistryLine('{"kind":"other"}'), null);
});

// ── appendRegistryLine / readRegistryLines ─────────────────────────────────

test("appendRegistryLine writes parseable JSONL that readRegistryLines reads back", () => {
  const dir = mkdtempSync(join(tmpdir(), "task-reliability-"));
  const path = join(dir, "nested", "task-registry.jsonl");
  try {
    assert.equal(
      appendRegistryLine(path, {
        ts: "2026-09-30T18:00:00.000Z",
        kind: "created",
        childID: "ses_child",
        parentID: "ses_parent",
      }),
      true,
    );
    assert.equal(
      appendRegistryLine(path, {
        ts: "2026-09-30T18:01:00.000Z",
        kind: "status",
        childID: "ses_child",
        status: "idle",
      }),
      true,
    );
    const lines = readRegistryLines(path);
    assert.equal(lines.length, 2);
    assert.equal(lines[0]?.kind, "created");
    assert.equal(lines[1]?.kind, "status");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("appendRegistryLine returns false (never throws) on an unwritable path", () => {
  // Deterministic ENOTDIR fixture: a regular FILE as the parent "directory".
  // (Do NOT use /proc/... here — mkdirSync(recursive) on a /proc path hangs
  // indefinitely on some kernels/containers instead of erroring.)
  const dir = mkdtempSync(join(tmpdir(), "task-reliability-blocker-"));
  try {
    const blocker = join(dir, "blocker.txt");
    appendFileSyncToTemp(blocker, "blocker\n", "utf8");
    assert.equal(
      appendRegistryLine(join(blocker, "sub", "task-registry.jsonl"), {
        ts: "2026-09-30T18:00:00.000Z",
        kind: "status",
        childID: "ses_child",
        status: "idle",
      }),
      false,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("readRegistryLines returns [] for a missing registry", () => {
  assert.deepEqual(readRegistryLines(join(tmpdir(), "task-reliability-missing.jsonl")), []);
});

// ── findActiveChild ─────────────────────────────────────────────────────────

const created = (childID: string, parentID: string): RegistryLine => ({
  ts: "2026-09-30T18:00:00.000Z",
  kind: "created",
  childID,
  parentID,
});
const status = (
  childID: string,
  s: "idle" | "stop" | "error" | "deleted" | "asking" | "stuck",
): RegistryLine => ({
  ts: "2026-09-30T18:00:01.000Z",
  kind: "status",
  childID,
  status: s,
});

test("findActiveChild finds a created child with no status yet", () => {
  const child = findActiveChild([created("ses_a", "ses_p")], "ses_p");
  assert.ok(child !== null);
  assert.equal(child.childID, "ses_a");
});

test("findActiveChild treats idle as recoverable (not terminal)", () => {
  const child = findActiveChild([created("ses_a", "ses_p"), status("ses_a", "idle")], "ses_p");
  assert.ok(child !== null);
  assert.equal(child.childID, "ses_a");
});

test("findActiveChild drops a child with a terminal status", () => {
  for (const terminal of ["stop", "error", "deleted"] as const) {
    assert.equal(
      findActiveChild([created("ses_a", "ses_p"), status("ses_a", terminal)], "ses_p"),
      null,
      `status=${terminal} should be terminal`,
    );
  }
});

test("findActiveChild picks the latest created child and resets on terminal", () => {
  const child = findActiveChild(
    [
      created("ses_a", "ses_p"),
      status("ses_a", "error"),
      created("ses_b", "ses_p"),
    ],
    "ses_p",
  );
  assert.ok(child !== null);
  assert.equal(child.childID, "ses_b");
});

test("findActiveChild ignores children of other parents", () => {
  assert.equal(findActiveChild([created("ses_a", "ses_other")], "ses_p"), null);
});

// ── isCancelledTaskOutput ───────────────────────────────────────────────────

test("isCancelledTaskOutput matches the empirical bare cancel string", () => {
  assert.equal(isCancelledTaskOutput("Task cancelled"), true);
  assert.equal(isCancelledTaskOutput("TASK CANCELLED"), true);
  assert.equal(isCancelledTaskOutput("The build finished successfully."), false);
  assert.equal(isCancelledTaskOutput(undefined), false);
});

test("isCancelledTaskOutput also inspects metadata status/state/error", () => {
  assert.equal(isCancelledTaskOutput("", { status: "cancelled" }), true);
  assert.equal(isCancelledTaskOutput("", { state: "Cancelled" }), true);
  assert.equal(isCancelledTaskOutput("", { error: "operation was cancelled" }), true);
  assert.equal(isCancelledTaskOutput("", { status: "ok" }), false);
});

// ── recoveryHint ────────────────────────────────────────────────────────────

test("recoveryHint with a child embeds the session id, task_id, and registry path", () => {
  const child: ChildInfo = { childID: "ses_child", parentID: "ses_p", agent: "verifier" };
  const hint = recoveryHint(child, "/tmp/registry.jsonl");
  assert.match(hint, /ses_child/);
  assert.match(hint, /task_id=ses_child/);
  assert.match(hint, /agent verifier/);
  assert.match(hint, /Do NOT re-dispatch/);
  assert.match(hint, /\/tmp\/registry\.jsonl/);
});

test("recoveryHint without a child says re-dispatch is safe and names the registry", () => {
  const hint = recoveryHint(null, "/tmp/registry.jsonl");
  assert.match(hint, /no child session was recorded/);
  assert.match(hint, /re-dispatching after a short wait is safe/);
  assert.match(hint, /\/tmp\/registry\.jsonl/);
});

// ── registry path resolution ─────────────────────────────────────────────────

test("readRegistryPath honours TASK_RELIABILITY_REGISTRY and falls back to the default", () => {
  const previous = process.env.TASK_RELIABILITY_REGISTRY;
  try {
    process.env.TASK_RELIABILITY_REGISTRY = "/tmp/override.jsonl";
    assert.equal(readRegistryPath(), "/tmp/override.jsonl");
    delete process.env.TASK_RELIABILITY_REGISTRY;
    assert.equal(readRegistryPath(), DEFAULT_REGISTRY_PATH);
    assert.equal(DEFAULT_REGISTRY_PATH, "/workspace/.opencode/task-registry.jsonl");
  } finally {
    if (previous === undefined) {
      delete process.env.TASK_RELIABILITY_REGISTRY;
    } else {
      process.env.TASK_RELIABILITY_REGISTRY = previous;
    }
  }
});

// ── stuck-child watchdog (BITB-269) ─────────────────────────────────────────

test("parseRegistryLine round-trips asking and stuck status lines", () => {
  for (const s of ["asking", "stuck"] as const) {
    const parsed = parseRegistryLine(
      registryLineToString({
        ts: "2026-11-07T23:09:29.000Z",
        kind: "status",
        childID: "ses_child",
        status: s,
      }),
    );
    assert.ok(parsed !== null);
    assert.equal(parsed.kind, "status");
    if (parsed.kind === "status") assert.equal(parsed.status, s);
  }
  // asking/stuck are NOT terminal — a stuck child stays recoverable.
  const child = findActiveChild(
    [created("ses_a", "ses_p"), status("ses_a", "asking"), status("ses_a", "stuck")],
    "ses_p",
  );
  assert.ok(child !== null);
  assert.equal(child.childID, "ses_a");
});

test("handleBusEvent records a created child and an asking line for it", () => {
  const state = freshState();
  const t0 = Date.parse("2026-11-07T23:02:41.000Z");
  const lines = handleBusEvent(
    state,
    busEvent("session.created", { sessionID: "ses_child", parentID: "ses_parent", agent: "fullstack-engineer" }),
    t0,
  );
  assert.equal(lines.length, 1);
  assert.equal(lines[0]?.kind, "created");

  const t1 = Date.parse("2026-11-07T23:09:29.000Z");
  const asking = handleBusEvent(
    state,
    busEvent("question.asked", { sessionID: "ses_child", id: "que_1b8462d6", questions: [{ question: "?" }] }),
    t1,
  );
  assert.equal(asking.length, 1);
  assert.equal(asking[0]?.kind, "status");
  if (asking[0]?.kind === "status") {
    assert.equal(asking[0].status, "asking");
    assert.equal(asking[0].childID, "ses_child");
  }
});

test("handleBusEvent ignores asking events for untracked (top-level) sessions", () => {
  const state = freshState();
  const lines = handleBusEvent(
    state,
    busEvent("question.asked", { sessionID: "ses_toplevel_user" }),
    Date.now(),
  );
  assert.deepEqual(lines, []);
});

test("handleBusEvent reads the empirical opencode 1.18.31 nested session.created shape", () => {
  // Captured live in a scratch instance (T-1254PLG): 1.18.31 emits
  // properties = {sessionID, info: {parentID, agent, title}} — the parent
  // linkage is nested under `info`, NOT at the properties top level. The
  // flat-property shape (accepted as a fallback above) never occurs in
  // 1.18.31; without this nested read no `created` line is ever written and
  // the stuck-child watchdog never arms.
  const state = freshState();
  const lines = handleBusEvent(
    state,
    busEvent("session.created", {
      sessionID: "ses_child",
      info: {
        id: "ses_child",
        parentID: "ses_parent",
        agent: "fullstack-engineer",
        title: "[T-1254PLG] demo (@fullstack-engineer subagent)",
      },
    }),
    Date.parse("2026-11-08T20:57:51.905Z"),
  );
  assert.equal(lines.length, 1);
  assert.equal(lines[0]?.kind, "created");
  if (lines[0]?.kind === "created") {
    assert.equal(lines[0].childID, "ses_child");
    assert.equal(lines[0].parentID, "ses_parent");
    assert.equal(lines[0].agent, "fullstack-engineer");
    assert.equal(lines[0].title, "[T-1254PLG] demo (@fullstack-engineer subagent)");
  }
  // created → the child is armed in the watchdog for stuck detection.
  assert.equal(state.lastActivity.has("ses_child"), true);

  // An info object WITHOUT parentID is a top-level session — no line.
  const topLevel = handleBusEvent(
    state,
    busEvent("session.created", { sessionID: "ses_top", info: { id: "ses_top" } }),
    Date.now(),
  );
  assert.deepEqual(topLevel, []);
});

test("handleBusEvent marks stuck after the threshold, once per stall, and re-arms on activity", () => {
  const state = freshState();
  const t0 = 1_000_000;
  handleBusEvent(state, busEvent("session.created", { sessionID: "ses_c", parentID: "ses_p" }), t0);
  recordActivity(state, "ses_c", t0);

  const threshold = DEFAULT_STUCK_SECONDS * 1000;
  // Just under the threshold: not stuck yet.
  assert.deepEqual(detectStuckChildren(state, t0 + threshold - 1, DEFAULT_STUCK_SECONDS), []);
  // Over the threshold: stuck detected exactly once…
  assert.deepEqual(detectStuckChildren(state, t0 + threshold, DEFAULT_STUCK_SECONDS), ["ses_c"]);
  // …and not again for the same stall, however many sweeps run.
  assert.deepEqual(detectStuckChildren(state, t0 + 10 * threshold, DEFAULT_STUCK_SECONDS), []);

  // New activity ends the stall and re-arms detection.
  recordActivity(state, "ses_c", t0 + 11 * threshold);
  assert.deepEqual(detectStuckChildren(state, t0 + 11 * threshold + threshold, DEFAULT_STUCK_SECONDS), [
    "ses_c",
  ]);
});

test("handleBusEvent untracks children on terminal status (no stuck lines for dead children)", () => {
  const state = freshState();
  const t0 = 1_000_000;
  handleBusEvent(state, busEvent("session.created", { sessionID: "ses_c", parentID: "ses_p" }), t0);
  handleBusEvent(state, busEvent("session.stop", { sessionID: "ses_c" }), t0);
  assert.deepEqual(detectStuckChildren(state, t0 + 100 * DEFAULT_STUCK_SECONDS * 1000, DEFAULT_STUCK_SECONDS), []);
});

test("handleBusEvent is inert on malformed events", () => {
  const state = freshState();
  assert.deepEqual(handleBusEvent(state, null, Date.now()), []);
  assert.deepEqual(handleBusEvent(state, undefined, Date.now()), []);
  assert.deepEqual(handleBusEvent(state, "string", Date.now()), []);
  assert.deepEqual(handleBusEvent(state, {}, Date.now()), []);
  assert.deepEqual(handleBusEvent(state, { type: 42 }, Date.now()), []);
  assert.deepEqual(handleBusEvent(state, busEvent("session.created", {}), Date.now()), []);
  assert.deepEqual(
    handleBusEvent(state, busEvent("session.created", { parentID: "" }), Date.now()),
    [],
  ); // missing sessionID + empty parentID
});

test("abortSession calls client.session.abort and never throws", async () => {
  const ok = { session: { abort: async () => ({}) } };
  assert.equal(await abortSession(ok, "ses_c"), true);
  // Throwing abort → false, not a rejection.
  const bad = {
    session: {
      abort: async () => {
        throw new Error("kaboom");
      },
    },
  };
  assert.equal(await abortSession(bad, "ses_c"), false);
  // Missing / mis-shaped clients → false.
  assert.equal(await abortSession(undefined, "ses_c"), false);
  assert.equal(await abortSession(null, "ses_c"), false);
  assert.equal(await abortSession({}, "ses_c"), false);
  assert.equal(await abortSession({ session: {} }, "ses_c"), false);
  assert.equal(await abortSession("nope", "ses_c"), false);
});

test("stuck threshold and sweep interval read env overrides safely", () => {
  const previousStuck = process.env.TASK_RELIABILITY_STUCK_SECONDS;
  try {
    assert.equal(DEFAULT_STUCK_SECONDS, 1200);
    assert.equal(readStuckSeconds(), 1200);
    process.env.TASK_RELIABILITY_STUCK_SECONDS = "300";
    assert.equal(readStuckSeconds(), 300);
    process.env.TASK_RELIABILITY_STUCK_SECONDS = "not-a-number";
    assert.equal(readStuckSeconds(), 1200);
    process.env.TASK_RELIABILITY_STUCK_SECONDS = "-5";
    assert.equal(readStuckSeconds(), 1200);
    delete process.env.TASK_RELIABILITY_STUCK_SECONDS;
    // Sweep cadence: clamped to [1s, 60s].
    assert.equal(sweepIntervalMs(1200), 60_000);
    assert.equal(sweepIntervalMs(100), 25_000);
    assert.equal(sweepIntervalMs(2), 1_000);
    assert.equal(sweepIntervalMs(-1), 1_000);
  } finally {
    if (previousStuck === undefined) {
      delete process.env.TASK_RELIABILITY_STUCK_SECONDS;
    } else {
      process.env.TASK_RELIABILITY_STUCK_SECONDS = previousStuck;
    }
  }
});

test("trackChild/untrackChild keep watchdog state consistent", () => {
  const state = freshState();
  const t0 = 5_000_000;
  trackChild(state, "ses_c", t0);
  assert.equal(state.lastActivity.get("ses_c"), t0);
  // A stuck-marked child that becomes active again is re-armed by recordActivity.
  detectStuckChildren(state, t0 + 100 * DEFAULT_STUCK_SECONDS * 1000, DEFAULT_STUCK_SECONDS);
  assert.equal(state.stuckMarked.has("ses_c"), true);
  trackChild(state, "ses_c", t0 + 1); // trackChild also re-arms
  assert.equal(state.stuckMarked.has("ses_c"), false);
  untrackChild(state, "ses_c");
  assert.equal(state.lastActivity.has("ses_c"), false);
  assert.equal(state.stuckMarked.has("ses_c"), false);
});

// ── module import is side-effect-free ───────────────────────────────────────

test("importing the plugin module writes nothing to the filesystem", async () => {
  const dir = mkdtempSync(join(tmpdir(), "task-reliability-import-"));
  const canary = join(dir, "task-registry.jsonl");
  try {
    process.env.TASK_RELIABILITY_REGISTRY = canary;
    const freshImport = await import("./task-reliability.ts");
    assert.ok(typeof freshImport.default === "function");
    assert.equal(existsSync(canary), false, "import must not create the registry file");
  } finally {
    delete process.env.TASK_RELIABILITY_REGISTRY;
    rmSync(dir, { recursive: true, force: true });
  }
});

// ── opencode 1.18.31 loader contract (BITB-269 / T-1254PLG regression) ──────

test("plugin module's runtime export surface is exactly one default function", async () => {
  // opencode 1.18.31 iterates Object.values(module) over the plugin module's
  // export surface: ANY non-function export (a string/number constant, an
  // options object, …) makes the whole plugin fail to load with
  // `TypeError: Plugin export is not a function` — the exact 2026-11-08 live
  // incident (runtime log 18:52:00Z, path
  // file:///workspace/repo/.opencode/plugin/task-reliability.ts). The old
  // module died on `export const DEFAULT_REGISTRY_PATH = "…"`. Helpers must
  // live in task-reliability-helpers.ts, never re-exported here.
  const mod = await import("./task-reliability.ts");
  assert.deepEqual(
    Object.keys(mod).sort(),
    ["default"],
    `plugin module must export only 'default', got: ${Object.keys(mod).join(", ")}`,
  );
  for (const [name, value] of Object.entries(mod)) {
    assert.equal(
      typeof value,
      "function",
      `export '${name}' must be a function (opencode 1.18.31 loader contract)`,
    );
  }
});

test("default export called as the loader calls it returns the hooks object", async () => {
  // The loader invokes every function export as plugin(ctx, options) and
  // registers the resolved value as the plugin's hooks. Prove the default
  // export tolerates the real call shape and yields the hooks contract.
  const mod = await import("./task-reliability.ts");
  const hooks = await mod.default({ client: {}, directory: "/tmp", project: {} }, {});
  assert.equal(hooks.name, "task-reliability");
  assert.equal(typeof hooks.event, "function");
  assert.equal(typeof hooks["tool.execute.after"], "function");
  assert.equal(typeof hooks["tool.definition"], "function");
  // A second load (auto-discovery + explicit config entry) must be harmless.
  const again = await mod.default(undefined, undefined);
  assert.equal(again.name, "task-reliability");
});

/**
 * Unit tests for the task-reliability plugin's helpers (BITB-169).
 *
 * Run with: node --experimental-strip-types --test .opencode/plugin/task-reliability.test.ts
 *
 * The plugin module has a side-effect-free top level and zero runtime
 * dependencies beyond node: builtins, so it can be imported directly under
 * Node's TS type-stripping. All filesystem tests run against a temp directory
 * via an explicit path argument — never the real /workspace registry.
 */

import { appendFileSync as appendFileSyncToTemp, mkdtempSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_REGISTRY_PATH,
  appendRegistryLine,
  findActiveChild,
  isCancelledTaskOutput,
  parseRegistryLine,
  readRegistryLines,
  readRegistryPath,
  recoveryHint,
  registryLineToString,
  type ChildInfo,
  type RegistryLine,
} from "./task-reliability.ts";

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
const status = (childID: string, s: "idle" | "stop" | "error" | "deleted"): RegistryLine => ({
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

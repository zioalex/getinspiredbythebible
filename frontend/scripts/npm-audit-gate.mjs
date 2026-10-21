#!/usr/bin/env node
/**
 * CI gate around `npm audit` that fails on high/critical advisories, except
 * those listed in audit-allowlist.json.
 *
 * `npm audit` has no way to ignore a single advisory, and some advisories have
 * no patched release at all (e.g. GHSA-vfj7-8cjw-p6xm affects every `braces`
 * version). Rather than drop dev dependencies from the audit entirely, this
 * script keeps auditing everything and ignores only the advisories named in
 * the allowlist, each with a reason and a reviewBy date. An expired entry
 * fails the gate, so an exception is re-examined instead of living forever.
 *
 * Usage (from frontend/): node scripts/npm-audit-gate.mjs
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const BLOCKING_SEVERITIES = new Set(["high", "critical"]);

/**
 * Pure evaluation of an `npm audit --json` report against an allowlist.
 *
 * Every vulnerable package's chain ends in an advisory object (`via` entries
 * that are objects rather than package-name strings), so checking those
 * advisory objects covers transitive findings too.
 *
 * @param {object} report parsed `npm audit --json` output
 * @param {{advisories?: {url: string, reviewBy: string}[]}} allowlist
 * @param {string} today ISO date (YYYY-MM-DD)
 * @returns {{blocking: {url: string, package: string, severity: string, title: string}[],
 *            ignored: string[], expired: string[]}}
 */
export function evaluateAudit(report, allowlist, today) {
  const entries = allowlist?.advisories ?? [];
  const expired = entries
    .filter((entry) => !entry.reviewBy || entry.reviewBy < today)
    .map((entry) => entry.url);
  const active = new Set(
    entries
      .filter((entry) => entry.reviewBy && entry.reviewBy >= today)
      .map((entry) => entry.url),
  );

  const seen = new Map();
  for (const vuln of Object.values(report?.vulnerabilities ?? {})) {
    for (const via of vuln.via ?? []) {
      if (typeof via !== "object" || via === null) continue;
      if (!BLOCKING_SEVERITIES.has(via.severity)) continue;
      if (!seen.has(via.url)) {
        seen.set(via.url, {
          url: via.url,
          package: via.name ?? vuln.name,
          severity: via.severity,
          title: via.title ?? "",
        });
      }
    }
  }

  const blocking = [];
  const ignored = [];
  for (const advisory of seen.values()) {
    if (active.has(advisory.url)) ignored.push(advisory.url);
    else blocking.push(advisory);
  }
  return { blocking, ignored, expired };
}

function runAudit() {
  try {
    return execFileSync("npm", ["audit", "--json"], {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (error) {
    // npm audit exits non-zero when it finds anything; the JSON is still on stdout.
    if (error.stdout) return error.stdout;
    throw error;
  }
}

function main() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const allowlist = JSON.parse(
    readFileSync(resolve(root, "audit-allowlist.json"), "utf8"),
  );
  const report = JSON.parse(runAudit());
  if (report.error) {
    console.error("npm audit failed:", report.error.summary ?? report.error);
    process.exit(1);
  }
  const today = new Date().toISOString().slice(0, 10);
  const { blocking, ignored, expired } = evaluateAudit(
    report,
    allowlist,
    today,
  );

  for (const url of ignored) {
    console.log(`Ignored (allowlisted in audit-allowlist.json): ${url}`);
  }
  let failed = false;
  for (const url of expired) {
    console.error(
      `Allowlist entry past its reviewBy date — re-check and renew or remove it: ${url}`,
    );
    failed = true;
  }
  for (const advisory of blocking) {
    console.error(
      `${advisory.severity}: ${advisory.package} — ${advisory.title} (${advisory.url})`,
    );
    failed = true;
  }
  if (failed) {
    console.error("\nRun `npm audit` in frontend/ for details and fixes.");
    process.exit(1);
  }
  console.log("npm audit gate: no blocking high/critical advisories.");
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main();
}

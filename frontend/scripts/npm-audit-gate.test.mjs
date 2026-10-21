import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { evaluateAudit } from "./npm-audit-gate.mjs";

const BRACES = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm";
const OTHER = "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz";

// Shape of real `npm audit --json` output: the leaf package carries the
// advisory object; packages that depend on it only name it as a string.
const report = (extra = {}) => ({
  vulnerabilities: {
    braces: {
      name: "braces",
      severity: "high",
      via: [
        {
          source: 1240992,
          name: "braces",
          title: "braces stack exhaustion",
          url: BRACES,
          severity: "high",
        },
      ],
    },
    micromatch: { name: "micromatch", severity: "high", via: ["braces"] },
    tailwindcss: { name: "tailwindcss", severity: "high", via: ["micromatch"] },
    ...extra,
  },
});

const allow = (reviewBy = "2027-01-04") => ({
  advisories: [{ url: BRACES, package: "braces", reason: "test", reviewBy }],
});

describe("evaluateAudit", () => {
  it("ignores an allowlisted advisory and its transitive dependents", () => {
    const result = evaluateAudit(report(), allow(), "2026-10-04");
    expect(result.blocking).toEqual([]);
    expect(result.ignored).toEqual([BRACES]);
    expect(result.expired).toEqual([]);
  });

  it("blocks the same advisory when it is not allowlisted", () => {
    const result = evaluateAudit(report(), { advisories: [] }, "2026-10-04");
    expect(result.blocking.map((a) => a.url)).toEqual([BRACES]);
  });

  it("still blocks any other high or critical advisory", () => {
    const result = evaluateAudit(
      report({
        lodash: {
          name: "lodash",
          severity: "critical",
          via: [
            {
              name: "lodash",
              title: "proto pollution",
              url: OTHER,
              severity: "critical",
            },
          ],
        },
      }),
      allow(),
      "2026-10-04",
    );
    expect(result.blocking.map((a) => a.url)).toEqual([OTHER]);
  });

  it("does not block moderate or low advisories", () => {
    const result = evaluateAudit(
      report({
        foo: {
          name: "foo",
          severity: "moderate",
          via: [
            { name: "foo", title: "minor", url: OTHER, severity: "moderate" },
          ],
        },
      }),
      allow(),
      "2026-10-04",
    );
    expect(result.blocking).toEqual([]);
  });

  it("reports and stops honouring an entry past its reviewBy date", () => {
    const result = evaluateAudit(report(), allow("2026-10-03"), "2026-10-04");
    expect(result.expired).toEqual([BRACES]);
    expect(result.blocking.map((a) => a.url)).toEqual([BRACES]);
  });

  it("treats an entry without reviewBy as expired", () => {
    const result = evaluateAudit(
      report(),
      { advisories: [{ url: BRACES, package: "braces", reason: "x" }] },
      "2026-10-04",
    );
    expect(result.expired).toEqual([BRACES]);
    expect(result.blocking).toHaveLength(1);
  });

  it("passes a clean report", () => {
    expect(
      evaluateAudit({ vulnerabilities: {} }, allow(), "2026-10-04"),
    ).toEqual({
      blocking: [],
      ignored: [],
      expired: [],
    });
  });

  it("ships an allowlist where every entry has a url, reason and reviewBy", () => {
    const file = JSON.parse(
      readFileSync(resolve(__dirname, "..", "audit-allowlist.json"), "utf8"),
    );
    expect(file.advisories.length).toBeGreaterThan(0);
    for (const entry of file.advisories) {
      expect(entry.url).toMatch(/^https:\/\/github\.com\/advisories\/GHSA-/);
      expect(entry.reason.length).toBeGreaterThan(20);
      expect(entry.reviewBy).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });
});

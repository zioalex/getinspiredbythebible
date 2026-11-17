import { describe, it, expect } from "vitest";
import {
  SOURCES,
  buildLastmod,
  hasFullHistory,
  lastCommitDate,
} from "./generate-lastmod.mjs";

describe("lastCommitDate", () => {
  it("returns the newest date across paths", () => {
    const dates = {
      a: "2026-01-01T00:00:00+00:00",
      b: "2026-03-01T00:00:00+00:00",
    };
    const run = (args) => dates[args.at(-1)] ?? "";
    expect(lastCommitDate(["a", "b", "c"], run)).toBe(dates.b);
  });

  it("returns undefined when git has nothing or throws", () => {
    expect(lastCommitDate(["a"], () => "")).toBeUndefined();
    expect(
      lastCommitDate(["a"], () => {
        throw new Error("boom");
      }),
    ).toBeUndefined();
  });
});

describe("hasFullHistory", () => {
  it("is false for shallow clones and non-repos", () => {
    const shallow = (args) =>
      args[1] === "--is-inside-work-tree" ? "true" : "true";
    expect(hasFullHistory(shallow)).toBe(false);
    expect(
      hasFullHistory(() => {
        throw new Error("not a repo");
      }),
    ).toBe(false);
  });

  it("is true for a complete work tree", () => {
    const full = (args) =>
      args[1] === "--is-inside-work-tree" ? "true" : "false";
    expect(hasFullHistory(full)).toBe(true);
  });
});

describe("buildLastmod", () => {
  it("covers every sitemap path and scopes legal pages to their own Markdown", () => {
    const seen = [];
    const run = (args) => {
      seen.push(args.at(-1));
      return "2026-02-02T00:00:00+00:00";
    };
    const result = buildLastmod(run);
    expect(Object.keys(result).sort()).toEqual(Object.keys(SOURCES).sort());
    expect(seen).toContain("public/legal/privacy-policy*.md");
    expect(seen).toContain("public/legal/terms-of-service*.md");
  });

  it("omits paths with no commit", () => {
    expect(buildLastmod(() => "")).toEqual({});
  });
});

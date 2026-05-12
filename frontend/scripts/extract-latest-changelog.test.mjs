import path from "path";
import { fileURLToPath } from "url";
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "fs";
import { parseLatestEntry } from "./extract-latest-changelog.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe("parseLatestEntry", () => {
  it("extracts version, date, and body from a standard release-please CHANGELOG", () => {
    const changelog = `# Changelog

## [1.2.3](https://github.com/example/repo/compare/v1.2.2...v1.2.3) (2024-06-01)

### Features

* add changelog page ([#100](https://github.com/example/repo/issues/100))

### Bug Fixes

* fix typo in footer

## [1.2.2](https://github.com/example/repo/compare/v1.2.1...v1.2.2) (2024-05-15)

### Bug Fixes

* older fix
`;
    const result = parseLatestEntry(changelog);
    expect(result).not.toBeNull();
    expect(result?.version).toBe("1.2.3");
    expect(result?.date).toBe("2024-06-01");
    expect(result?.body).toContain("add changelog page");
    expect(result?.body).not.toContain("older fix");
  });

  it("extracts version without date", () => {
    const changelog = `## 2.0.0\n\n### Features\n\n* new stuff\n`;
    const result = parseLatestEntry(changelog);
    expect(result?.version).toBe("2.0.0");
    expect(result?.date).toBeNull();
    expect(result?.body).toContain("new stuff");
  });

  it("returns null for empty / no-version content", () => {
    expect(parseLatestEntry("# Changelog\n\nNothing here.\n")).toBeNull();
    expect(parseLatestEntry("")).toBeNull();
  });

  it("handles a single release entry (no next header)", () => {
    const changelog = `## [0.1.0] (2024-01-01)\n\n* initial release\n`;
    const result = parseLatestEntry(changelog);
    expect(result?.version).toBe("0.1.0");
    expect(result?.body).toContain("initial release");
  });
});

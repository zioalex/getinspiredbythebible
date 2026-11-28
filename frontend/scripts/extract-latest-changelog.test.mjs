import path from "path";
import { fileURLToPath } from "url";
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "fs";
import {
  buildWhatsNew,
  parseLatestEntry,
  readUserNotes,
  versionFromManifest,
} from "./extract-latest-changelog.mjs";

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

describe("curated What's new (BITB-175)", () => {
  const root = path.join(__dirname, "__tmp_release_notes__");

  beforeAll(() => {
    mkdirSync(path.join(root, "1.63.0"), { recursive: true });
    writeFileSync(
      path.join(root, "1.63.0", "en.md"),
      "- Read aloud keeps going\n",
    );
    writeFileSync(
      path.join(root, "1.63.0", "it.md"),
      "- La lettura continua\n",
    );
    writeFileSync(path.join(root, "1.63.0", "de.md"), "   \n");
    mkdirSync(path.join(root, "1.64.0"), { recursive: true });
    writeFileSync(path.join(root, "1.64.0", "it.md"), "- Solo italiano\n");
  });

  afterAll(() => {
    rmSync(root, { recursive: true, force: true });
  });

  it("reads the released version from the release-please manifest", () => {
    expect(versionFromManifest('{ ".": "1.63.0" }')).toBe("1.63.0");
    expect(versionFromManifest('{ ".": "next" }')).toBeNull();
    expect(versionFromManifest("not json")).toBeNull();
  });

  it("reads every non-empty locale file for the version", () => {
    expect(readUserNotes(root, "1.63.0")).toEqual({
      en: "- Read aloud keeps going",
      it: "- La lettura continua",
    });
  });

  it("returns null without English, without the folder, or without a version", () => {
    expect(readUserNotes(root, "1.64.0")).toBeNull();
    expect(readUserNotes(root, "9.9.9")).toBeNull();
    expect(readUserNotes(root, null)).toBeNull();
    expect(readUserNotes(null, "1.63.0")).toBeNull();
  });

  it("builds the popup payload with the English body and the CHANGELOG date", () => {
    const notes = { en: "- A", it: "- B" };
    const changelog =
      "## [1.63.0](https://x) (2026-12-01)\n\n### Features\n\n* opencode stuff\n";
    expect(buildWhatsNew("1.63.0", notes, changelog)).toEqual({
      version: "1.63.0",
      date: "2026-12-01",
      body: "- A",
      notes,
    });
    expect(buildWhatsNew("1.63.0", notes, null).date).toBeNull();
  });

  it("writes the no-popup sentinel when the release has no curated notes", () => {
    expect(buildWhatsNew("1.63.0", null, "## [1.63.0] (2026-12-01)\n")).toEqual(
      { version: null },
    );
    expect(buildWhatsNew(null, { en: "- A" }, null)).toEqual({ version: null });
  });
});

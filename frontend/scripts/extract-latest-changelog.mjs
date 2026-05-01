#!/usr/bin/env node
/**
 * Reads the root CHANGELOG.md and extracts the topmost release entry.
 * Writes frontend/public/changelog.json with:
 *   { "version": "X.Y.Z", "date": "YYYY-MM-DD", "body": "..." }
 * If CHANGELOG.md is missing or has no entries, writes { "version": null }.
 *
 * Run via `prebuild` / `predev` in package.json so next build always has
 * a fresh public/changelog.json.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../../");
const changelogPath = resolve(repoRoot, "CHANGELOG.md");
const outputDir = resolve(__dirname, "../public");
const outputPath = resolve(outputDir, "changelog.json");

/** Parse topmost ## [X.Y.Z] or ## X.Y.Z entry from a CHANGELOG string. */
export function parseLatestEntry(content) {
  // Match headers like:
  //   ## [1.2.3](url) (2024-06-01)   ← release-please format
  //   ## [1.2.3] — 2024-06-01
  //   ## 1.2.3
  const headerRe =
    /^##\s+\[?([\d]+\.[\d]+\.[\d]+[^\]\s]*)\]?(?:\([^)]*\))?(?:\s*[-–—]\s*(\d{4}-\d{2}-\d{2})|\s+\((\d{4}-\d{2}-\d{2})\))?/m;

  const match = headerRe.exec(content);
  if (!match) return null;

  const version = match[1];
  // date can be in group 2 (dash syntax) or group 3 (paren syntax)
  const date = match[2] ?? match[3] ?? null;
  const headerEnd = match.index + match[0].length;

  // Everything from end of this header until the next ## header (or EOF)
  const rest = content.slice(headerEnd);
  const nextHeaderIdx = rest.search(/^##\s/m);
  const body =
    nextHeaderIdx === -1 ? rest.trim() : rest.slice(0, nextHeaderIdx).trim();

  return { version, date, body };
}

function main() {
  if (!existsSync(changelogPath)) {
    console.log(
      "[extract-latest-changelog] CHANGELOG.md not found — writing empty sentinel.",
    );
    mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, JSON.stringify({ version: null }, null, 2));
    return;
  }

  const content = readFileSync(changelogPath, "utf8");
  const entry = parseLatestEntry(content);

  if (!entry) {
    console.log(
      "[extract-latest-changelog] No versioned entries found — writing empty sentinel.",
    );
    mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, JSON.stringify({ version: null }, null, 2));
    return;
  }

  const payload = {
    version: entry.version,
    date: entry.date,
    body: entry.body,
  };
  mkdirSync(outputDir, { recursive: true });
  writeFileSync(outputPath, JSON.stringify(payload, null, 2));
  console.log(
    `[extract-latest-changelog] Wrote v${entry.version} to public/changelog.json`,
  );
}

main();

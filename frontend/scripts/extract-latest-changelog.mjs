#!/usr/bin/env node
/**
 * Reads the CHANGELOG.md and extracts the topmost release entry.
 * Writes frontend/public/changelog.json with:
 *   { "version": "X.Y.Z", "date": "YYYY-MM-DD", "body": "..." }
 * Also copies the full CHANGELOG.md verbatim to frontend/public/CHANGELOG.md
 * so /[locale]/changelog can read it at build time. The file is shipped via
 * the standalone Docker image's `public/` folder.
 *
 * Looks first in the repo root (local dev), then in the frontend dir
 * (Docker build: CI is expected to stage CHANGELOG.md into ./frontend
 * before `docker build` because the build context is ./frontend and the
 * repo-root CHANGELOG.md is otherwise invisible inside the container).
 *
 * If CHANGELOG.md is missing or has no entries, writes { "version": null }
 * and does not create public/CHANGELOG.md (the page falls back to its
 * empty state).
 *
 * Run via `prebuild` / `predev` in package.json so next build always has
 * fresh artifacts in public/.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../../");
const candidatePaths = [
  resolve(repoRoot, "CHANGELOG.md"),
  resolve(__dirname, "../CHANGELOG.md"),
];
const changelogPath =
  candidatePaths.find((p) => existsSync(p)) ?? candidatePaths[0];
const outputDir = resolve(__dirname, "../public");
const outputPath = resolve(outputDir, "changelog.json");
const outputMarkdownPath = resolve(outputDir, "CHANGELOG.md");

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
  // Also ship the full CHANGELOG.md so /[locale]/changelog can render it.
  writeFileSync(outputMarkdownPath, content);
  console.log(
    `[extract-latest-changelog] Wrote v${entry.version} to public/changelog.json + full CHANGELOG.md`,
  );
}

main();

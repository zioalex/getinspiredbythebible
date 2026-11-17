#!/usr/bin/env node
/**
 * Writes frontend/src/generated/lastmod.json (BITB-300): sitemap path -> ISO
 * date of the last git commit that touched that page's source (and, for the
 * legal pages, its Markdown). `src/app/sitemap.ts` reads it so <lastmod>
 * reflects real content changes instead of the build time.
 *
 * The generated file is COMMITTED. The Docker build context is `frontend/`
 * with no `.git`, and CI checkouts are shallow, so git history is often
 * unavailable at build time. In that case this script leaves the existing file
 * untouched (exit 0). Locally, with full history, it refreshes the dates; commit
 * the result when it changes.
 *
 * Run via `prebuild` in package.json.
 */

import { execFileSync } from "child_process";
import { existsSync, mkdirSync, writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(__dirname, "..");
const outputDir = resolve(frontendDir, "src/generated");
const outputPath = resolve(outputDir, "lastmod.json");

/** Sitemap path -> repo-relative (to frontend/) files whose changes bump it. */
export const SOURCES = {
  "": ["src/app/[locale]/page.tsx", "src/app/[locale]/ChatIsland.tsx"],
  "/app": ["src/app/[locale]/app/page.tsx"],
  "/about": ["src/app/[locale]/about/page.tsx"],
  "/privacy": ["src/app/[locale]/privacy/page.tsx", "public/legal"],
  "/terms": ["src/app/[locale]/terms/page.tsx", "public/legal"],
  "/changelog": ["src/app/[locale]/changelog/page.tsx", "../CHANGELOG.md"],
};

// Legal pages: only their own Markdown, not the whole directory.
const LEGAL_PREFIX = {
  "/privacy": "privacy-policy",
  "/terms": "terms-of-service",
};

function git(args) {
  return execFileSync("git", args, {
    cwd: frontendDir,
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
}

/** True when git history is complete enough to trust commit dates. */
export function hasFullHistory(run = git) {
  try {
    return (
      run(["rev-parse", "--is-inside-work-tree"]) === "true" &&
      run(["rev-parse", "--is-shallow-repository"]) === "false"
    );
  } catch {
    return false;
  }
}

/** ISO date of the newest commit touching any of `paths`, or undefined. */
export function lastCommitDate(paths, run = git) {
  let best;
  for (const p of paths) {
    let out = "";
    try {
      out = run(["log", "-1", "--format=%cI", "--", p]);
    } catch {
      continue;
    }
    if (out && (!best || Date.parse(out) > Date.parse(best))) best = out;
  }
  return best;
}

export function buildLastmod(run = git) {
  const result = {};
  for (const [path, files] of Object.entries(SOURCES)) {
    const paths = LEGAL_PREFIX[path]
      ? files.map((f) =>
          f === "public/legal" ? `public/legal/${LEGAL_PREFIX[path]}*.md` : f,
        )
      : files;
    const date = lastCommitDate(paths, run);
    if (date) result[path] = date;
  }
  return result;
}

function main() {
  if (!hasFullHistory()) {
    console.log(
      "[generate-lastmod] No full git history (shallow clone / Docker); keeping existing src/generated/lastmod.json",
    );
    if (!existsSync(outputPath)) {
      mkdirSync(outputDir, { recursive: true });
      writeFileSync(outputPath, "{}\n");
    }
    return;
  }
  const data = buildLastmod();
  mkdirSync(outputDir, { recursive: true });
  writeFileSync(outputPath, JSON.stringify(data, null, 2) + "\n");
  console.log(
    `[generate-lastmod] Wrote ${Object.keys(data).length} dates to src/generated/lastmod.json`,
  );
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main();
}

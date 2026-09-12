#!/usr/bin/env node
/**
 * Writes frontend/public/build-info.json with a per-build id used to
 * cache-bust the service worker's shell cache (BITB-102):
 *   { "buildId": "<id>", "generatedAt": "<ISO-8601>" }
 *
 * The id comes from NEXT_PUBLIC_BUILD_ID when set (CI passes the deploy
 * SHA — see .github/workflows/azure-deploy.yml and frontend/Dockerfile),
 * sanitized to a safe subset of characters since it ends up in a URL query
 * string (`/sw.js?v=<id>`). Locally, where NEXT_PUBLIC_BUILD_ID is usually
 * unset, it falls back to a `dev-<timestamp>` id so every local build still
 * gets its own shell cache rather than sharing one across dev sessions.
 *
 * The client (`src/lib/registerServiceWorker.ts`) fetches this file at
 * runtime rather than reading `process.env` directly, so the same static
 * export works regardless of how/when the page was rendered.
 *
 * Run via `predev` / `prebuild` in package.json, mirroring
 * `extract-latest-changelog.mjs`.
 */

import { writeFileSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outputDir = resolve(__dirname, "../public");
const outputPath = resolve(outputDir, "build-info.json");

const MAX_BUILD_ID_LENGTH = 64;

/**
 * Resolve the build id from an env-like object. Pure — unit-testable without
 * touching `process.env` or the filesystem.
 */
export function resolveBuildId(env) {
  const raw = (env?.NEXT_PUBLIC_BUILD_ID ?? "").trim();
  if (raw) {
    return raw.replace(/[^A-Za-z0-9._-]/g, "-").slice(0, MAX_BUILD_ID_LENGTH);
  }
  return `dev-${Date.now()}`;
}

function main() {
  const buildId = resolveBuildId(process.env);
  const payload = {
    buildId,
    generatedAt: new Date().toISOString(),
  };
  mkdirSync(outputDir, { recursive: true });
  writeFileSync(outputPath, JSON.stringify(payload, null, 2));
  console.log(`[generate-build-info] Wrote buildId=${buildId} to public/build-info.json`);
}

main();

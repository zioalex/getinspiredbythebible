#!/usr/bin/env node
/**
 * Builds the two changelog artifacts the web app ships in public/:
 *
 *   public/CHANGELOG.md   the full developer CHANGELOG (release-please), rendered by
 *                         /[locale]/changelog. Unchanged.
 *   public/changelog.json what the "What's new" popup (WhatsNewModal) shows after an update.
 *
 * BITB-175: the popup no longer shows the raw CHANGELOG entry (English only, full of tooling
 * scopes and BITB ids). It shows the curated end-user notes for the released version,
 * release-notes/<version>/<locale>.md (docs/RELEASE_PROCESS.md, "Writing the user What's
 * New"), as { "version", "date", "body": <en>, "notes": { "<locale>": "..." } }. When that
 * release has no curated notes (a hotfix, say), it writes { "version": null } and no popup is
 * shown. The released version is read from .release-please-manifest.json.
 *
 * Inputs are looked up in the repo root (local dev) and then in the frontend dir (Docker build:
 * azure-deploy.yml stages CHANGELOG.md, release-notes/ and the manifest into ./frontend because
 * the build context is ./frontend).
 *
 * Run via `prebuild` / `predev` in package.json so next build always has fresh artifacts.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath, pathToFileURL } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../../");
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

const LOCALES = [
  "en",
  "it",
  "de",
  "es",
  "fr",
  "pt",
  "ar",
  "ru",
  "zh",
  "hi",
  "ko",
];

function firstExisting(relPath) {
  const candidates = [
    resolve(repoRoot, relPath),
    resolve(__dirname, "..", relPath),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

/** The released version from a .release-please-manifest.json string, or null. */
export function versionFromManifest(content) {
  try {
    const version = JSON.parse(content)["."];
    return typeof version === "string" && /^\d+\.\d+\.\d+$/.test(version)
      ? version
      : null;
  } catch {
    return null;
  }
}

/**
 * Curated end-user notes for one release: { "<locale>": "<markdown>" } for every
 * release-notes/<version>/<locale>.md that exists and is not empty, or null without English.
 */
export function readUserNotes(notesRoot, version) {
  if (!notesRoot || !version) return null;
  const folder = resolve(notesRoot, version);
  if (!existsSync(folder)) return null;
  const notes = {};
  for (const locale of LOCALES) {
    const file = resolve(folder, `${locale}.md`);
    if (!existsSync(file)) continue;
    const text = readFileSync(file, "utf8").trim();
    if (text) notes[locale] = text;
  }
  return notes.en ? notes : null;
}

/** The popup payload for a release, or the { version: null } sentinel. */
export function buildWhatsNew(version, notes, changelogContent) {
  if (!version || !notes) return { version: null };
  const entry = changelogContent ? parseLatestEntry(changelogContent) : null;
  const date = entry && entry.version === version ? entry.date : null;
  return { version, date, body: notes.en, notes };
}

function main() {
  mkdirSync(outputDir, { recursive: true });

  const changelogPath = firstExisting("CHANGELOG.md");
  const changelog = changelogPath ? readFileSync(changelogPath, "utf8") : null;
  if (changelog) {
    // The full developer CHANGELOG, for /[locale]/changelog.
    writeFileSync(outputMarkdownPath, changelog);
  } else {
    console.log(
      "[extract-latest-changelog] CHANGELOG.md not found — /changelog will render its empty state.",
    );
  }

  const manifestPath = firstExisting(".release-please-manifest.json");
  const version = manifestPath
    ? versionFromManifest(readFileSync(manifestPath, "utf8"))
    : null;
  const notes = readUserNotes(firstExisting("release-notes"), version);
  const payload = buildWhatsNew(version, notes, changelog);
  writeFileSync(outputPath, JSON.stringify(payload, null, 2));
  console.log(
    payload.version
      ? `[extract-latest-changelog] What's new for v${payload.version}: ${Object.keys(notes).join(", ")}`
      : `[extract-latest-changelog] No curated notes for v${version ?? "?"} — no "What's new" popup.`,
  );
}

// Run only as a script (prebuild / predev), not when the tests import the helpers.
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main();
}

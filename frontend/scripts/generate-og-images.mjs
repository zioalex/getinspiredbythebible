#!/usr/bin/env node
/**
 * Generates the static share (Open Graph / Twitter) images, one PNG per
 * locale, at frontend/public/og/<locale>.png, plus public/og/manifest.json
 * (BITB-299).
 *
 * Why pre-rendered: `next/og` cannot shape Arabic/Devanagari (Arabic 503'd,
 * Hindi conjuncts broke). A real Chromium shapes both correctly, so we render
 * an HTML template with Playwright and commit the PNGs.
 *
 * Fonts come from the exact-pinned `@fontsource/noto-sans*` devDependencies
 * (SIL OFL; licences ship inside the packages), never from system fonts.
 *
 * Usage:   npm run og:generate
 * Sandbox: OG_CHROMIUM_PATH=/path/to/chrome npm run og:generate
 * (use the env override when the Playwright-matching browser is not installed)
 *
 * Re-run whenever `Metadata.title` / `Metadata.description` change in any
 * messages/<locale>.json — the staleness test fails until you do.
 */

import { createHash } from "crypto";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
} from "fs";
import { tmpdir } from "os";
import { resolve, dirname, join } from "path";
import { fileURLToPath, pathToFileURL } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(__dirname, "..");
const messagesDir = join(frontendDir, "messages");
const outputDir = join(frontendDir, "public", "og");

export const LOCALES = [
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
export const RTL_LOCALES = new Set(["ar"]);

export const WIDTH = 1200;
export const HEIGHT = 630;

/** locale -> [font-family name, @fontsource package] of the script font. */
const SCRIPT_FONTS = {
  ar: ["Noto Sans Arabic", "noto-sans-arabic"],
  hi: ["Noto Sans Devanagari", "noto-sans-devanagari"],
  zh: ["Noto Sans SC", "noto-sans-sc"],
  ko: ["Noto Sans KR", "noto-sans-kr"],
};
const LATIN_FONT = ["Noto Sans", "noto-sans"];

/** Direction for a locale. */
export function localeDir(locale) {
  return RTL_LOCALES.has(locale) ? "rtl" : "ltr";
}

/** The @fontsource packages (dir names) needed to render a locale. */
export function fontPackages(locale) {
  const script = SCRIPT_FONTS[locale];
  return script ? [script[1], LATIN_FONT[1]] : [LATIN_FONT[1]];
}

/** CSS font-family stack: the locale's script font first, Noto Sans always. */
export function fontFamily(locale) {
  const script = SCRIPT_FONTS[locale];
  const names = script ? [script[0], LATIN_FONT[0]] : [LATIN_FONT[0]];
  return [...names.map((n) => `'${n}'`), "sans-serif"].join(", ");
}

/** SHA-256 hex of `title + "\n" + description` — the staleness fingerprint. */
export function manifestHash(title, description) {
  return createHash("sha256").update(`${title}\n${description}`).digest("hex");
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Rewrite relative `url(./files/x)` in a fontsource stylesheet to absolute
 * file:// URLs under `filesDir`, keeping only the woff2 source.
 */
export function rewriteFontCss(css, filesDirUrl) {
  return css.replace(
    /url\(\.\/files\/([^)]+\.woff2)\) format\('woff2'\)(?:, url\([^)]+\) format\('woff'\))?/g,
    (_m, file) => `url(${filesDirUrl}/${file}) format('woff2')`,
  );
}

/** Build the 1200x630 HTML for one locale. Pure; unit-testable. */
export function buildHtml(locale, title, description, fontCss = "") {
  const dir = localeDir(locale);
  return `<!doctype html>
<html lang="${locale}" dir="${dir}">
<head>
<meta charset="utf-8">
<style>
${fontCss}
html, body { margin: 0; padding: 0; }
body {
  width: ${WIDTH}px; height: ${HEIGHT}px; position: relative; overflow: hidden;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background-color: #3A2210;
  font-family: ${fontFamily(locale)};
}
.halo { position: absolute; top: 90px; left: 50%; margin-left: -80px; width: 160px; height: 160px;
  border-radius: 50%; background-color: #F0B830; opacity: 0.25; }
.dot { position: absolute; top: 140px; left: 50%; margin-left: -30px; width: 60px; height: 60px;
  border-radius: 50%; background-color: #FFE880; }
.title { margin-top: 140px; font-size: 72px; line-height: 90px; font-weight: 700; color: #FFE880; }
.tagline { margin-top: 24px; font-size: 32px; line-height: 48px; color: #F5C842; text-align: center; }
</style>
</head>
<body>
<div class="halo"></div>
<div class="dot"></div>
<div class="title">${escapeHtml(title)}</div>
<div class="tagline">${escapeHtml(description)}</div>
</body>
</html>
`;
}

function loadFontCss(locale) {
  const parts = [];
  for (const pkg of fontPackages(locale)) {
    const pkgDir = join(frontendDir, "node_modules", "@fontsource", pkg);
    const filesUrl = pathToFileURL(join(pkgDir, "files")).href;
    for (const weight of ["400", "700"]) {
      const css = readFileSync(join(pkgDir, `${weight}.css`), "utf8");
      parts.push(rewriteFontCss(css, filesUrl));
    }
  }
  return parts.join("\n");
}

function readMetadata(locale) {
  const messages = JSON.parse(
    readFileSync(join(messagesDir, `${locale}.json`), "utf8"),
  );
  return messages.Metadata;
}

async function main() {
  const { chromium } = await import("@playwright/test");
  const executablePath = process.env.OG_CHROMIUM_PATH || undefined;
  const browser = await chromium.launch({ executablePath });
  const tmp = mkdtempSync(join(tmpdir(), "og-"));
  mkdirSync(outputDir, { recursive: true });
  const manifest = {};
  try {
    const page = await browser.newPage({
      viewport: { width: WIDTH, height: HEIGHT },
    });
    for (const locale of LOCALES) {
      const { title, description } = readMetadata(locale);
      const html = buildHtml(locale, title, description, loadFontCss(locale));
      const file = join(tmp, `${locale}.html`);
      writeFileSync(file, html);
      await page.goto(pathToFileURL(file).href);
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({
        path: join(outputDir, `${locale}.png`),
        clip: { x: 0, y: 0, width: WIDTH, height: HEIGHT },
      });
      manifest[locale] = manifestHash(title, description);
      console.log(`og: wrote public/og/${locale}.png`);
    }
  } finally {
    await browser.close();
    rmSync(tmp, { recursive: true, force: true });
  }
  writeFileSync(
    join(outputDir, "manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  console.log("og: wrote public/og/manifest.json");
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

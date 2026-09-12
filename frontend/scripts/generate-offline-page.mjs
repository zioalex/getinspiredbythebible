#!/usr/bin/env node
/**
 * Generates frontend/public/offline.html — the offline fallback page served
 * by the service worker (BITB-102, `public/sw.js`) when a navigation request
 * fails while the app has no connection.
 *
 * This is a FULLY SELF-CONTAINED, generated static HTML file — not a Next.js
 * `[locale]/offline` route. A Next route would reference external
 * `_next/static/...` chunks/stylesheets to render, and those are exactly the
 * assets that are unreachable when the browser is offline in the first
 * place. Inlining everything (CSS, an SVG mark, and the locale strings as a
 * JS object) means the file works standalone, served straight from the
 * shell cache, with zero further network requests.
 *
 * The locale is chosen client-side at load time (see `buildOfflineHtml`
 * below) from the URL path or the browser's language, since a single static
 * file can't be localized server-side.
 *
 * Run via `predev` / `prebuild` in package.json, mirroring
 * `extract-latest-changelog.mjs` / `generate-build-info.mjs`.
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "fs";
import { resolve, dirname, basename } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const messagesDir = resolve(__dirname, "../messages");
const outputDir = resolve(__dirname, "../public");
const outputPath = resolve(outputDir, "offline.html");

const DEFAULT_LOCALE = "en";
const RTL_LOCALES = new Set(["ar"]);

/**
 * Escape a string for safe embedding inside a JS string literal produced by
 * JSON.stringify — specifically, break up sequences that could terminate the
 * surrounding <script> block or smuggle a comment into it, even though the
 * text sits inside a JSON string rather than raw markup. Applied to the
 * *whole* JSON.stringify output, not per-field, so it can't be bypassed by a
 * value split across object boundaries.
 */
function escapeForInlineScript(json) {
  return json.replace(/<\//g, "<\\/").replace(/<!--/g, "<\\!--");
}

/**
 * Build the offline.html document as a string. Pure — no filesystem access —
 * so it's unit-testable directly.
 *
 * @param {Record<string, {title: string, description: string, retry: string}>} messagesByLocale
 * @param {string[]} locales
 * @param {string} defaultLocale
 */
export function buildOfflineHtml(messagesByLocale, locales, defaultLocale) {
  const messagesJson = escapeForInlineScript(JSON.stringify(messagesByLocale));
  const localesJson = JSON.stringify(locales);
  const rtlJson = JSON.stringify([...RTL_LOCALES]);
  const defaultMsg = messagesByLocale[defaultLocale] ?? {
    title: "You're offline",
    description: "Check your connection and try again.",
    retry: "Try again",
  };

  return `<!doctype html>
<html lang="${defaultLocale}" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#874a30">
<title>${escapeHtml(defaultMsg.title)}</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    background: #faf5f0;
    color: #3a2a20;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  body {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: max(1.5rem, env(safe-area-inset-top)) max(1.5rem, env(safe-area-inset-right))
      max(1.5rem, env(safe-area-inset-bottom)) max(1.5rem, env(safe-area-inset-left));
  }
  .card {
    max-width: 26rem;
    width: 100%;
    text-align: center;
  }
  .mark {
    width: 4rem;
    height: 4rem;
    margin: 0 auto 1.25rem;
    color: #874a30;
  }
  h1 {
    font-size: 1.5rem;
    line-height: 1.3;
    margin: 0 0 0.75rem;
    color: #3a2a20;
  }
  p {
    font-size: 1rem;
    line-height: 1.5;
    margin: 0 0 1.5rem;
    color: #6b584a;
  }
  button {
    font: inherit;
    font-weight: 600;
    font-size: 1rem;
    padding: 0.75rem 1.75rem;
    border: none;
    border-radius: 999px;
    background: #874a30;
    color: #faf5f0;
    cursor: pointer;
  }
  button:hover { background: #6b3a26; }
  button:focus-visible { outline: 2px solid #874a30; outline-offset: 2px; }
  [dir="rtl"] .card { text-align: center; }
  @media (prefers-color-scheme: dark) {
    html, body { background: #241812; color: #f2e6dc; }
    h1 { color: #f2e6dc; }
    p { color: #cbb6a6; }
    .mark { color: #d99a6c; }
    button { background: #d99a6c; color: #241812; }
    button:hover { background: #e6ac83; }
  }
</style>
</head>
<body>
  <main class="card">
    <svg class="mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M12 3v12" />
      <path d="M8 7c0-2.2 1.8-4 4-4s4 1.8 4 4" />
      <path d="M4 21h16" />
      <path d="M6 21v-6a6 6 0 0 1 12 0v6" />
      <line x1="2" y1="2" x2="22" y2="22" />
    </svg>
    <h1 id="vq-offline-title">${escapeHtml(defaultMsg.title)}</h1>
    <p id="vq-offline-description">${escapeHtml(defaultMsg.description)}</p>
    <button id="vq-offline-retry" type="button">${escapeHtml(defaultMsg.retry)}</button>
  </main>
  <script>
    var VQ_OFFLINE_MESSAGES = ${messagesJson};
    var VQ_OFFLINE_LOCALES = ${localesJson};
    var VQ_OFFLINE_RTL_LOCALES = ${rtlJson};
    var VQ_OFFLINE_DEFAULT_LOCALE = ${JSON.stringify(defaultLocale)};

    function vqDetectLocale() {
      var pathSegments = location.pathname.split("/").filter(Boolean);
      if (pathSegments.length > 0 && VQ_OFFLINE_LOCALES.indexOf(pathSegments[0]) !== -1) {
        return pathSegments[0];
      }
      var nav = (navigator.language || "").split("-")[0];
      if (nav && VQ_OFFLINE_LOCALES.indexOf(nav) !== -1) {
        return nav;
      }
      return VQ_OFFLINE_DEFAULT_LOCALE;
    }

    (function vqApplyLocale() {
      var locale = vqDetectLocale();
      var messages = VQ_OFFLINE_MESSAGES[locale] || VQ_OFFLINE_MESSAGES[VQ_OFFLINE_DEFAULT_LOCALE];
      var isRtl = VQ_OFFLINE_RTL_LOCALES.indexOf(locale) !== -1;

      document.documentElement.lang = locale;
      document.documentElement.dir = isRtl ? "rtl" : "ltr";
      document.title = messages.title;

      document.getElementById("vq-offline-title").textContent = messages.title;
      document.getElementById("vq-offline-description").textContent = messages.description;
      document.getElementById("vq-offline-retry").textContent = messages.retry;
    })();

    document.getElementById("vq-offline-retry").addEventListener("click", function () {
      location.reload();
    });
    window.addEventListener("online", function () {
      location.reload();
    });
  </script>
</body>
</html>
`;
}

/** Minimal HTML-escaping for the server-rendered (default-locale) fallback text. */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function loadMessages(locale) {
  const raw = readFileSync(resolve(messagesDir, `${locale}.json`), "utf8");
  const parsed = JSON.parse(raw);
  const offline = parsed.Offline || {};
  return {
    title: offline.title || "You're offline",
    description: offline.description || "Check your connection and try again.",
    retry: offline.retry || "Try again",
  };
}

function main() {
  const locales = readdirSync(messagesDir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => basename(f, ".json"))
    .sort();

  const messagesByLocale = {};
  for (const locale of locales) {
    messagesByLocale[locale] = loadMessages(locale);
  }

  const defaultLocale = locales.includes(DEFAULT_LOCALE)
    ? DEFAULT_LOCALE
    : locales[0];

  const html = buildOfflineHtml(messagesByLocale, locales, defaultLocale);

  mkdirSync(outputDir, { recursive: true });
  writeFileSync(outputPath, html);
  console.log(
    `[generate-offline-page] Wrote public/offline.html with ${locales.length} locale(s)`,
  );
}

main();

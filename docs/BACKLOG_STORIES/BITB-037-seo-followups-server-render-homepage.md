# BITB-037: SEO Follow-ups — Server-Render Homepage, JSON-LD, OG Image

**Status:** 📋 Backlog (production verified 2026-05-31 — see Live verification)

## User Story

As a person searching for Bible inspiration on Google (or asking an AI
assistant), I want Vox Quieta's pages to be fully indexable — with real
server-rendered text, structured data, rich link previews, and a
crawlable robots/sitemap — so the site can actually be discovered rather
than served as an empty client-rendered shell.

## Background

The SEO **foundation** landed in PR #636 (merged): `metadataBase`,
`frontend/src/app/sitemap.ts`, `frontend/src/app/robots.ts`,
`frontend/src/app/icon.svg`, Open Graph / Twitter tags, per-page
canonical and hreflang (incl. `x-default`), and a descriptive home
`<title>` with a `%s · Vox Quieta` template. The shared helper lives at
`frontend/src/lib/seo.ts`. The static checker
(`scripts/seo-static-check.sh`) now reports **0 FAIL, 2 WARN**.

This story tracks the work that was deliberately deferred from #636
because it touches the client/server boundary or needs a design asset.

## Live verification (2026-05-31)

A `scripts/seo-live-check.sh` run against production confirms the #636
foundation is live: `/sitemap.xml` serves real XML (200), per-page
canonical + hreflang (incl. `x-default`) are correct, OG/Twitter tags
render, the home title is the descriptive 50-char version, and the
`%s · Vox Quieta` template applies on sub-pages.

The run surfaced two real findings:

1. **`/en` is still 0 server-rendered words.** `/en/privacy` renders
   ~493 server-side words, proving SSR works on this stack. This is
   the only thing currently blocking homepage indexability.
2. **`/favicon.ico` 404** — `app/icon.svg` resolves for modern clients
   but legacy crawlers / link-preview bots hardcoded to `/favicon.ico`
   miss the brand. Addressed in this branch (see Recent progress).

It also clarified one non-finding:

- **Cloudflare `/robots.txt` is fine.** Cloudflare's AI Audit appends
  the origin's body *after* its own managed content, so the served
  body contains both the per-bot `Disallow:` rules (GPTBot, ClaudeBot,
  Google-Extended, CCBot, Bytespider, etc.), the
  `Content-Signal: search=yes,ai-train=no` declaration, *and* the
  `Sitemap: https://voxquieta.org/sitemap.xml` line from
  `app/robots.ts`. An earlier draft of this story flagged this as
  broken — that was a misread caused by the live-check script
  truncating output at 20 lines. The script is fixed in this branch.

## Proposed Changes

### 1. Server-render the homepage hero (highest impact, P1) 🔴

`frontend/src/app/[locale]/page.tsx:1` is `"use client"`. Lift the static
hero copy (`Welcome.heading`, `Welcome.description`, and an intro
paragraph) into a **server component** rendered above the interactive
chat island, keeping the chat UI as a `"use client"` child so it still
hydrates. Mind the Turnstile preload + hydration path in
`frontend/src/app/[locale]/providers.tsx` and the existing layout
`<head>` preconnect logic.

**Why P1 (was P2):** the live check confirms the homepage is empty to
crawlers (0 server words). Every other remaining task is incremental
polish; this is the only one that meaningfully moves the needle on
whether search and AI bots can index the landing page at all.

### 2. Add JSON-LD structured data (P3) 🟢

Inject `WebSite` + `Organization` schema (`application/ld+json`), ideally
via `frontend/src/lib/seo.ts` so all 11 locales get it consistently.

### 3. Add a real Open Graph image (P3) 🟢

PR #636 set `twitter.card = "summary"` and OG tags but there is **no
`og:image` asset** — link previews render without a card image. Add a
branded share image (`frontend/src/app/opengraph-image.*`, or a `public/`
asset referenced from `lib/seo.ts`) and upgrade the Twitter card to
`summary_large_image`. The brand mark to base it on is
`android/play_store_assets/icon.svg` (also the source for `app/icon.svg`
and the new `app/favicon.ico`).

### 4. Post-deploy live re-verification (P3) 🟢

After tasks 1–3 land, re-run `bash scripts/seo-live-check.sh` against
production to confirm `/en` server-rendered word count is no longer
thin, `og:image` resolves, and `/favicon.ico` returns 200. Then submit
the sitemap to Google Search Console.

## Recent progress

- **`/favicon.ico` 404** — fixed in this branch by adding
  `frontend/src/app/favicon.ico` derived from
  `android/play_store_assets/icon.svg` (multi-resolution 16/32/48 px via
  `rsvg-convert` + `icotool`). Next App Router auto-wires it as
  `<link rel="icon">` for legacy crawlers; modern clients keep using
  `app/icon.svg`.
- **`seo-live-check.sh` truncation bug** — the script was passing the
  `/robots.txt` body through `head -20`, which cut off Cloudflare's full
  managed block and hid the appended origin `Sitemap:` line. Replaced
  with the full body plus two explicit PASS/FAIL probes (Sitemap
  directive present? Content-Signal present?).
- **Cloudflare robots.txt** — verified working as-is; no operator
  action needed. See the non-finding note in Live verification above.

## Acceptance Criteria

- [ ] **(P1)** `scripts/seo-live-check.sh` shows `/en` server-rendered
      word count is no longer thin (homepage hero text is in the initial
      HTML).
- [ ] **(P1)** Chat UI still hydrates and works (Turnstile, streaming,
      modals) after the server/client split.
- [x] `/favicon.ico` returns 200 with the brand icon.
- [x] Production `/robots.txt` contains the `Sitemap:` directive (live
      check confirms — Cloudflare appends the origin body).
- [ ] **(P3)** `WebSite` + `Organization` JSON-LD present on all
      locales; `seo-static-check.sh` JSON-LD WARN clears.
- [ ] **(P3)** `og:image` resolves and Twitter card is
      `summary_large_image`.
- [ ] **(P3)** Sitemap submitted to Google Search Console.

## Files to Modify

| File | Change |
|---|---|
| `frontend/src/app/[locale]/page.tsx` | Split: server-rendered hero + `"use client"` chat island (task 1) |
| `frontend/src/lib/seo.ts` | Add JSON-LD helper (WebSite/Organization); reference OG image (tasks 2, 3) |
| `frontend/src/app/opengraph-image.*` (new) or `frontend/public/` asset | Branded OG share image (task 3) |
| `frontend/src/app/favicon.ico` | ✅ Done in this branch — derived from `android/play_store_assets/icon.svg` |
| `scripts/seo-live-check.sh` | ✅ Done in this branch — show full robots.txt body + explicit probes |

## Out of Scope

- The metadata foundation already shipped in #636.
- Cloudflare robots.txt change (verified working as-is).
- Android / iOS apps.
- Any content/copywriting beyond the homepage hero text.

## Priority

P1 for task 1 (server-render homepage); P3 for tasks 2–4. Bumped task 1
to P1 after the 2026-05-31 live check confirmed the homepage is empty
to crawlers.

## Size

M overall. Task 1 needs care around the client/server boundary and
hydration; tasks 2–4 are small.

## Dependencies / Related Work

- Builds directly on PR #636 (SEO metadata foundation, merged).
- Verification tooling: `scripts/seo-static-check.sh`,
  `scripts/seo-live-check.sh`, and the `/seo-audit` skill.

## Assignee

frontend-expert

# BITB-037: SEO Follow-ups — Server-Render Homepage, JSON-LD, OG Image, Edge robots Verification

**Status:** 📋 Backlog

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
because it touches the client/server boundary, needs a design asset, or
can only be verified post-deploy.

## Problem

The live check against production found the home page renders
**~0 server-side words** — `frontend/src/app/[locale]/page.tsx` is a
`"use client"` component, so crawlers and AI bots get an empty shell. By
contrast `/en/privacy` (a server component) renders ~493 words. The two
remaining static-checker WARNs (no JSON-LD, client-rendered homepage)
correspond to the first two tasks below.

## Proposed Changes

### 1. Server-render the homepage hero (highest impact) 🔴

`frontend/src/app/[locale]/page.tsx:1` is `"use client"`. Lift the static
hero copy (`Welcome.heading`, `Welcome.description`, and an intro
paragraph) into a **server component** rendered above the interactive
chat island, keeping the chat UI as a `"use client"` child so it still
hydrates. Mind the Turnstile preload + hydration path in
`frontend/src/app/[locale]/providers.tsx` and the existing layout
`<head>` preconnect logic.

### 2. Add JSON-LD structured data 🟡

Inject `WebSite` + `Organization` schema (`application/ld+json`), ideally
via `frontend/src/lib/seo.ts` so all 11 locales get it consistently.

### 3. Add a real Open Graph image 🟡

PR #636 set `twitter.card = "summary"` and OG tags but there is **no
`og:image` asset** — link previews render without a card image. Add a
branded share image (`frontend/src/app/opengraph-image.*`, or a `public/`
asset referenced from `lib/seo.ts`) and upgrade the Twitter card to
`summary_large_image`. The brand mark to base it on is
`android/play_store_assets/icon.svg` (now also the web favicon).

### 4. Verify edge robots.txt precedence (post-deploy) 🟡

The live `/robots.txt` is currently served by **Cloudflare** (the
content-signals boilerplate). The new Next `app/robots.ts` emits a
`Sitemap:` directive, but it only helps if it actually wins at the edge.
After deploy, confirm whether Cloudflare or Next serves `/robots.txt`,
and ensure the served file contains
`Sitemap: https://voxquieta.org/sitemap.xml`.

### 5. Post-deploy live re-verification 🟢

Run `bash scripts/seo-live-check.sh` against production and confirm the
foundation from #636 is live, then submit the sitemap to Google Search
Console.

## Acceptance Criteria

- [ ] `scripts/seo-live-check.sh` shows `/en` server-rendered word count
      is no longer thin (homepage hero text is in the initial HTML).
- [ ] Chat UI still hydrates and works (Turnstile, streaming, modals)
      after the server/client split.
- [ ] `WebSite` + `Organization` JSON-LD present on all locales;
      `seo-static-check.sh` JSON-LD WARN clears.
- [ ] `og:image` resolves and Twitter card is `summary_large_image`.
- [ ] Production `/robots.txt` contains the `Sitemap:` directive
      (whichever layer serves it).
- [ ] Live check confirms: `/sitemap.xml` returns 200 (was a noindex
      soft-404 before #636), `/icon.svg` resolves, `/en` shows canonical
      + OG + Twitter tags, and `/en/privacy` hreflang points to
      `/it/privacy` etc. (not locale roots).
- [ ] Sitemap submitted to Google Search Console.

## Files to Modify

| File | Change |
|---|---|
| `frontend/src/app/[locale]/page.tsx` | Split: server-rendered hero + `"use client"` chat island |
| `frontend/src/lib/seo.ts` | Add JSON-LD helper (WebSite/Organization); reference OG image |
| `frontend/src/app/opengraph-image.*` (new) or `frontend/public/` asset | Branded OG share image |
| (post-deploy) Cloudflare config / `frontend/src/app/robots.ts` | Ensure `Sitemap:` wins at the edge |

## Out of Scope

- The metadata foundation already shipped in #636.
- Android / iOS apps.
- Any content/copywriting beyond the homepage hero text.

## Priority

P2 — Medium. Task 1 (server-render homepage) is the biggest ranking
lever; the rest are incremental.

## Size

M — task 1 needs care around the client/server boundary and hydration;
tasks 2–5 are small.

## Dependencies / Related Work

- Builds directly on PR #636 (SEO metadata foundation, merged).
- Verification tooling: `scripts/seo-static-check.sh`,
  `scripts/seo-live-check.sh`, and the `/seo-audit` skill.

## Assignee

frontend-expert

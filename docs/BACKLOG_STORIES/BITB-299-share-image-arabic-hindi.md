# BITB-299: Share Image — Arabic Returns 503, Hindi Is Mis-Shaped

**Status:** 🔍 In Review
**Priority:** P1
**Size:** S
**Created:** 2026-11-11
**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows S1, S2.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 2.
**Commit:** `fix(frontend): pre-rendered share images for all 11 locales (BITB-299)`

## Problem

`frontend/src/app/[locale]/opengraph-image.tsx` renders the share image at request time
with `next/og` (`ImageResponse`), putting the localized tagline (`Metadata.description`)
under the brand name.

- **Arabic is down in production.** `GET https://voxquieta.org/ar/opengraph-image` → `503`
  (three attempts, 2026-11-11); the other ten locales → `200`. Reproduced on `next dev`:

  ```text
  ⨯ Error: failed to pipe response
    [cause]: Error: lookupType: 5 - substFormat: 3 is not yet supported
  GET /ar/opengraph-image 500
  ```

  The image renderer cannot process the font tables of the Arabic fallback font. Every
  Arabic link shared on WhatsApp, Telegram, Facebook or X shows no preview.
- **Hindi renders, but wrongly.** The live image shows split conjuncts and a misplaced
  vowel sign in `परमेश्वर के वचन से हर दिन प्रेरित हों`. The renderer does not do complex
  text shaping.
- English, Chinese and Korean images were inspected and are correct. Russian, Italian,
  German, Spanish, French and Portuguese return `200` and use Latin or Cyrillic, which
  need no shaping.

The same `503` URL is what `og:image` and `twitter:image` point to on every Arabic page.

## Decisions already made

1. **Stop rendering at request time. Pre-render one PNG per locale with a real browser
   engine and commit it.** A browser shapes Arabic and Devanagari correctly; a renderer
   without a shaping engine never will, whichever font is bundled.
2. **Generator:** `frontend/scripts/generate-og-images.mjs`, using the Playwright
   Chromium that is already a dev dependency (`@playwright/test`). It renders the same
   layout as today's component (1200×630, background `#3A2210`, the two circles, brand
   name, tagline) from an HTML template, with `lang` and `dir` set per locale, and writes
   `frontend/public/og/<locale>.png`.
3. **Fonts are bundled in the repo** under `frontend/scripts/og-fonts/` (Noto Sans,
   Noto Sans Arabic, Noto Sans Devanagari, Noto Sans SC, Noto Sans KR — all SIL OFL;
   include each licence file) and loaded by the template with `@font-face`, so output
   does not depend on the fonts installed on the machine that runs the script.
4. **Staleness guard:** the script also writes `frontend/public/og/manifest.json` mapping
   each locale to a SHA-256 of `title + "\n" + description`. A Vitest test recomputes the
   hashes from `frontend/messages/*.json` and fails when they differ, with the message
   "run `npm run og:generate`".
5. **Delete `opengraph-image.tsx`** and set the image explicitly in `pageMetadata`
   (`frontend/src/lib/seo.ts`): `openGraph.images` and `twitter.images` →
   `/og/<locale>.png`, width 1200, height 630, `alt` = the localized
   `"<title> — <description>"`.

## Requirements

1. Generator script, fonts and `npm run og:generate` (decisions 2–3).
2. Eleven committed PNGs, each under 150 KB (the repo's large-file hook must pass).
3. Manifest and staleness test (decision 4).
4. `pageMetadata` emits the static image for every page of every locale (decision 5);
   the localized `alt` replaces the hard-coded `"Vox Quieta"`.
5. Remove `opengraph-image.tsx` and any test that imports it; update
   `scripts/seo-static-check.sh` if it looks for that file.
6. Document the regeneration step in `frontend/README.md` (or the doc that already
   describes frontend assets) — one short section.

## Tests (minimum)

- Parametrized over all 11 locales: `frontend/public/og/<locale>.png` exists, is a
  1200×630 PNG, and the manifest hash matches the messages.
- `pageMetadata` for `ar` and `hi` returns `openGraph.images[0].url` ending in
  `/og/ar.png` / `/og/hi.png` and a non-empty localized `alt`.
- The builder **looks at** the Arabic and Hindi images and attaches both to the PR
  description. Arabic must read right-to-left with joined letters; Hindi conjuncts
  (`श्व`, `प्रे`) must be single glyph clusters.

## Acceptance criteria

- [ ] `curl -o /dev/null -w "%{http_code}" https://voxquieta.org/og/ar.png` → `200` after deploy (**owner step**)
- [x] No request-time image rendering remains (`grep -rn "next/og" frontend/src` is empty)
- [x] Changing any `Metadata.description` without regenerating fails the unit tests
- [x] Arabic and Hindi images verified by eye, screenshots in the PR

## Out of scope

- Per-page share images (topic and verse pages get theirs in BITB-301/302, reusing this
  generator).
- Redesigning the image.

## Related

BITB-136 (introduced the generated image), BITB-300, BITB-301, BITB-302.

## Build notes

- **Font deviation from decision 3.** Fonts are not committed under `scripts/og-fonts/`.
  Noto Sans SC/KR are many MB each and the `check-added-large-files` hook caps files at
  1000 KB. Instead the generator loads `400.css`/`700.css` from exact-pinned
  `@fontsource/noto-sans`, `-arabic`, `-devanagari`, `-sc`, `-kr` devDependencies (rewritten
  to `file://` URLs), so output still never depends on system fonts. The OFL licences ship
  inside those packages.
- `OG_CHROMIUM_PATH` overrides the Chromium binary when Playwright's matching browser is not
  installed (sandboxes).
- `pageMetadata` takes a required `ogImageAlt`; callers get it from `getOgImageAlt(locale)`
  (`src/lib/ogImage.ts`, server-only) = localized `"<Metadata.title> — <Metadata.description>"`.
- Added explicit line-heights in the template so the title/tagline sit at the same position in
  every locale despite per-script font metrics.
- Arabic (RTL, joined) and Hindi (`श्व`, `प्रे` single clusters) verified by eye.

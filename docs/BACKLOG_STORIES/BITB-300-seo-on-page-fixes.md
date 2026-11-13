---
id: BITB-300
status: todo
priority: P1
size: S
rank: 30
created: 2026-11-11
---

# BITB-300: SEO On-Page Fixes — Headings, Descriptions, Noindex, Localized 404, Honest Sitemap Dates

**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows S5–S11, S15, S16.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 2.
**Commit:** `feat(frontend): SEO on-page fixes across 11 locales (BITB-300)`

## Problem

Checked against the live site on 2026-11-11. The foundations pass (canonical, 11
hreflang + `x-default`, Open Graph, Twitter card, JSON-LD, sitemap, robots, redirects for
un-prefixed paths). These do not:

| # | Finding | Evidence |
|---|---|---|
| 1 | Homepage has two `<h1>`, both "Vox Quieta"; the only descriptive heading is `<h2>Welcome</h2>` | live `/en`; `ChatIsland.tsx:1098`, `SplashScreen.tsx:296`, `[locale]/page.tsx:15` |
| 2 | Meta description repeats the title's tagline (32 characters) | live `/en`; `[locale]/layout.tsx:28,34` |
| 3 | `/[locale]/tester` is indexable | live `/en/tester` → `200`, no `robots` meta |
| 4 | 404 page is English in every locale | live `/ar/__x404`; `[locale]/not-found.tsx` |
| 5 | All 66 sitemap entries share one build timestamp | live sitemap; `sitemap.ts:11` |
| 6 | `og:locale` is a bare language code (`en`) | live `/en`; `seo.ts:65` |
| 7 | Organization logo in JSON-LD is an SVG | `seo.ts:98` |
| 8 | 27 physical Tailwind direction classes do not mirror in Arabic | grep in the review, row S16 |

## Decisions already made

1. **One `<h1>` per page, and it describes the page.** Homepage: the server-rendered
   hero heading becomes the `<h1>`. The sticky header brand and the splash-screen brand
   become non-heading elements (`<p>` or `<div>`) with unchanged classes.
2. **Hero heading copy changes** from "Welcome" to a descriptive line. English:
   "Find comfort and guidance in Scripture". Translate into all 11 locales; keep the
   existing `Welcome.heading` key so both clients of that key update together (grep for
   other users of the key first — if Android or another component shows it, add a new key
   `Welcome.seoHeading` instead and leave the old one).
3. **New `Metadata.homeDescription`** per locale, 120–155 characters, saying what the
   site does (ask questions in your own words, answers grounded in Scripture, 11
   languages, free, no account). Used for `<meta name="description">`, `og:description`,
   `twitter:description` and JSON-LD on the homepage. `Metadata.description` stays as the
   short tagline in the title.
4. **`/tester` gets `robots: { index: false, follow: false }`** in its
   `generateMetadata`.
5. **404 is localized:** new `NotFound` message namespace (`title`, `body`, `backHome`)
   in all 11 files; the page uses the active locale and offers a link home.
6. **Sitemap dates come from git, at build time.** A small build script writes
   `frontend/src/generated/lastmod.json` (path → ISO date of the last commit touching
   that page's source file or its legal Markdown); `sitemap.ts` reads it and omits
   `lastModified` when a path has no entry. Never `new Date()`.
7. **`og:locale` uses a region-qualified value** from one map in `seo.ts`:
   `en_US, it_IT, de_DE, es_ES, fr_FR, pt_BR, ar_AR, ru_RU, zh_CN, hi_IN, ko_KR`; the
   other ten go in `openGraph.alternateLocale`.
8. **Logo:** `Organization.logo` → `/icons/icon-512.png` (exists in
   `frontend/public/icons/`).
9. **RTL:** replace the 27 physical classes with logical ones (`ms-`, `me-`, `ps-`,
   `pe-`, `text-start`, `text-end`, `start-`, `end-`) **except** where the element is
   deliberately direction-fixed (anything inside `dir="ltr"`, e.g. the brand header at
   `ChatIsland.tsx:1099`). List each kept exception in the PR.

## Requirements

Implement decisions 1–9. Additionally:

- Every new or changed message key exists in all 11 `frontend/messages/*.json` files.
- `scripts/seo-static-check.sh` gains checks for: exactly one `<h1>` source per page
  component, `robots` on the tester page, no `new Date()` in `sitemap.ts`.
- `scripts/seo-live-check.sh` prints the `<h1>` count and the meta-description length.

## Tests (minimum)

- Server render of `[locale]/page.tsx` for all 11 locales: exactly one `<h1>`, non-empty,
  not equal to the brand name.
- `generateMetadata` for the homepage in all 11 locales: description length 120–155 and
  different from the title.
- Tester page metadata has `robots.index === false`.
- Not-found page renders localized text for `ar`, `zh`, `hi`, `ru` (not the English
  string).
- `sitemap()` contains no entry whose `lastModified` equals the test's "now"; entries
  with a known file use the generated date.
- `pageMetadata` → `openGraph.locale` matches the map for all 11 locales.
- Existing `sitemap.test.ts`, `layout.test.tsx`, `page.server.test.tsx` updated, not
  deleted.

## Acceptance criteria

- [ ] Live `/en` shows one `<h1>` with descriptive text (**owner step** after deploy:
      `bash scripts/seo-live-check.sh`)
- [ ] Meta description differs from the title in all 11 locales
- [ ] `/en/tester` carries `noindex`
- [ ] `/ar/does-not-exist` shows Arabic text
- [ ] Sitemap `<lastmod>` values differ between pages
- [ ] Arabic layout checked by eye on the homepage and one sub-page; screenshots in the PR
- [ ] **Owner step:** record the Search Console indexed-page count here before merge —
      this is the baseline for BITB-301/302
- [ ] **Owner step:** submit the sitemap in Google Search Console and Bing Webmaster
      Tools if not already done (BITB-136 recorded it as pending)
- [ ] **Owner decision:** Cloudflare's managed `robots.txt` blocks AI crawlers
      (`ClaudeBot`, `GPTBot`, `Google-Extended`, …) with `ai-train=no`. Keep (default) or
      allow AI *search* bots once topic and verse pages exist. Dashboard setting, no code.

## Out of scope

- New pages (BITB-301, BITB-302, BITB-303).
- `FAQPage`/`SoftwareApplication` structured data (do it with the pages that need it).
- Splitting `ChatIsland.tsx`.

## Related

BITB-136, BITB-299, BITB-301, BITB-302.

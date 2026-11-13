---
id: BITB-301
status: todo
priority: P1
size: L
rank: 40
created: 2026-11-11
---

# BITB-301: Topic Landing Pages in 11 Languages ("Bible Verses About …")

**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) row S3.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 3. **After BITB-300.**
**Commit:** `feat(frontend): topic landing pages in 11 languages (BITB-301)`

## User story

As someone going through anxiety, grief or loneliness, I search for "Bible verses about
anxiety" in my own language. I want to land on a page that shows me relevant scripture
straight away and lets me talk about it, without knowing the site exists beforehand.

## Problem

The live sitemap has 66 URLs (6 pages × 11 locales) and none contains scripture. All of
the product's value sits behind a client-side chat that search engines cannot see. The
twelve life topics the product already models
(`scripts/migrations/004_add_topic_boosting_schema.sql:24-36`: anxiety, peace,
forgiveness, anger, loneliness, trust, fear, hope, love, grief, guidance, patience) are
exactly what people search for.

## Decisions already made

1. **Routes:** `/[locale]/topics` (index of the 12) and `/[locale]/topics/[slug]`.
   Slugs are the English topic names in every locale (`anxiety`, `grief`, …): one stable
   path per topic keeps `hreflang` trivial.
2. **Verse lists are curated and committed, not computed at request time.**
   `frontend/content/topics.json` maps each slug to 10–15 references
   (`{ "book": "Philippians", "chapter": 4, "verseStart": 6, "verseEnd": 7 }`, English
   canonical book names). The `verse_topics` table is keyword-matched and covers only 7
   languages (`docs/HOW-TO-POPULATE-VERSE-TOPICS.md`), which is not good enough for a
   public page; semantic search at request time costs an embedding call per view.
3. **Verse text comes from the API in the locale's default translation**, server-side:
   `GET {NEXT_PUBLIC_API_URL}/api/v1/scripture/verse/{book}/{chapter}/{verse}?translation=<code>`
   (or `/range/…` for multi-verse references). The locale → translation map mirrors
   `LANGUAGE_TO_TRANSLATION` in `api/utils/language.py:17` — expose it from one place
   rather than copying it (the `/scripture/translations` response or a small generated
   file; pick whichever needs no new endpoint).
4. **Never a hard-coded translation.** A test proves the Italian page shows Riveduta
   text and the English page shows the English default, for the same reference.
5. **Rendering: on-demand ISR, not build-time.** `generateStaticParams` returns `[]`,
   `dynamicParams = true`, `revalidate = 86400`. The Docker build has no API access, so
   pages must not be fetched during `next build`. On a fetch failure, throw — Next keeps
   serving the last good page.
6. **Localized copy** lives in `frontend/messages/<locale>.json` under a new `Topics`
   namespace: per topic a `name`, an `h1` ("Bible verses about anxiety"), a
   `metaDescription` (120–155 characters) and an `intro` of two or three sentences in a
   warm, plain register. All 11 locales.
7. **Each page has:** one `<h1>`; the intro; the verses as `<blockquote>` with the
   localized reference (book name from the API response, never translated by hand); the
   translation's name; a "Talk about this" button; links to the other topics.
8. **"Talk about this"** opens the chat with a prefilled, **not auto-sent**, prompt in
   the page's language. Check whether the chat already accepts a prefill parameter; if
   not, add `?prompt=` handling to the chat page (read once, then removed from the URL;
   ignored if longer than `max_message_length`).
9. **Structured data:** `BreadcrumbList` and `ItemList` (one `ListItem` per verse with
   its reference as `name`). No `FAQPage`.
10. **Sitemap:** 13 × 11 new entries with alternates, using the dated-`lastmod`
    mechanism from BITB-300.
11. **Entry points:** a "Topics" link in the footer and on the About page. The homepage
    hero stays as it is.

## Requirements

1. `frontend/content/topics.json` with 12 topics × 10–15 references. Start from
   well-known passages; every reference must be validated by requirement 2.
2. `frontend/scripts/validate-topics.mjs`: for every reference and every one of the 13
   live translations, fetch the verse and fail on a `404`. It prints a review table
   (reference, locale, text) to a file. **Versification differs between traditions** —
   the Russian Synodal text numbers many Psalms one lower than the English Bibles. For
   every Psalms reference, compare the Russian (and any other non-`200` or
   suspicious) result against the English text by meaning; if the API does not normalize
   the numbering, add a per-translation override map in `topics.json`
   (`"overrides": { "synodal": { … } }`) and say so in the PR.
3. Pages, metadata (through `pageMetadata` with the page path so canonical and hreflang
   are right), JSON-LD, sitemap entries (decisions 1, 5, 7, 9, 10).
4. `Topics` messages in all 11 locales (decision 6).
5. Chat prefill (decision 8).
6. Footer and About links, localized (decision 11).
7. Share image: reuse the BITB-299 generator if it has merged; otherwise the default
   locale image.
8. Arabic pages are `dir="rtl"` end to end; use logical Tailwind classes only.

## Tests (minimum)

- Parametrized over 11 locales × at least 2 topics: the page renders one `<h1>`, the
  localized intro, at least 10 verses, a canonical URL and 12 `hreflang` links; verse
  fetches are mocked per translation.
- Version faithfulness: same reference, `en` vs `it` vs `de` pages show different mocked
  texts from their own translations; no test passes with a hard-coded translation code.
- Every topic slug in `topics.json` has all four message keys in all 11 locales.
- Unknown slug → `notFound()`.
- API failure → the route throws (so ISR keeps the previous page) and does not render an
  empty list.
- Chat prefill: `?prompt=` fills the input, does not send, strips the parameter; an
  over-long value is ignored. Cover an Arabic and a Chinese prompt.
- Sitemap contains the 143 new URLs.
- JSON-LD parses and `ItemList.numberOfItems` equals the rendered verse count.

## Acceptance criteria

- [ ] 12 topic pages + 1 index, in 11 languages, server-rendered with scripture in the HTML
- [ ] Each page's verses are in that locale's own translation
- [ ] All references validated against all 13 translations; Psalm numbering checked
- [ ] "Talk about this" lands in the chat with the prompt prefilled, not sent
- [ ] Pages are in the sitemap with correct alternates
- [ ] **Owner step:** review the verse list for each topic (the review table from the
      validation script) before merge
- [ ] **Owner step:** have a native reader check the Arabic, Hindi, Korean, Chinese and
      Russian intros, or accept them as machine-drafted and say so here
- [ ] **Owner step:** four weeks after deploy, record Search Console impressions for
      `/topics/` here

## Out of scope

- More than the 12 seeded topics (add in follow-ups once these are indexed).
- Localized slugs.
- Android.
- Changing chat retrieval to use the curated lists.

## Related

BITB-044 (`verse_topics`), BITB-136, BITB-299, BITB-300, BITB-302, BITB-303.

# BITB-303: Verse of the Day — Page, Dated Archive and Feed

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M
**Created:** 2026-11-11
**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows S3, S9.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 4. **After BITB-301** (reuses its fetch helpers and chat prefill).
**Commit:** `feat(frontend): verse of the day page, archive and feed (BITB-303)`

## User story

As a returning visitor, I want one verse each day in my language, with an easy way to
reflect on it, so the site gives me a reason to come back that does not depend on having
a question.

## Problem

Nothing on the site changes from day to day: every sitemap entry carries the same build
timestamp, and the tagline "Get inspired daily by God's Word" is not backed by anything
daily. The Icebox has had "Daily Devotional Notifications" (`docs/BACKLOG.md:7609`) with
no web surface to point a notification at.

## Decisions already made

1. **The schedule is a committed list.** `frontend/content/votd.json`: 366 references in
   the same shape as `topics.json` (BITB-301), indexed by day of year. Same verse for
   everyone on a given date, reviewable in a PR, no model call, no cost.
2. **The day rolls over at 00:00 UTC.** One global date keeps caching and the archive
   simple. Say so on the page in small print only if a tester finds it confusing — not
   by default.
3. **Routes:**
   - `/[locale]/verse-of-the-day` — today's verse.
   - `/[locale]/verse-of-the-day/[date]` — `YYYY-MM-DD`, past dates and today only.
     A future date is `notFound()` (the schedule must not be scrapeable ahead of time
     from the routes, even though the JSON is public in the repo).
   - `/[locale]/verse-of-the-day/feed.xml` — RSS 2.0 with the last 14 days.
4. **Text is fetched server-side in the locale's default translation**, with the helper
   from BITB-301. Never hard-coded.
5. **Caching:** today's page `revalidate = 3600` (so the rollover is picked up within an
   hour); dated pages `revalidate = 604800`.
6. **Page content:** `<h1>` localized "Verse of the Day"; the date in the locale's
   format; the verse as a `<blockquote>` with its localized reference and translation
   name; "Reflect on this verse" → chat with a prefilled prompt; previous-day link;
   share button (reuse `ShareMenu`). If BITB-302 has merged and the locale's translation
   is allowed, the reference links to the chapter page anchor.
7. **Homepage:** the server-rendered hero gains one line, "Today's verse: <reference>",
   linking to the page. Reference only, no verse text, so the hero stays light.
8. **Sitemap:** today's URL per locale with `changeFrequency: "daily"`, plus the last 30
   dated pages. Older archive pages stay reachable but are not listed.
9. **Structured data:** `BreadcrumbList` only.

## Requirements

1. `frontend/content/votd.json` with 366 validated references. Reuse
   `frontend/scripts/validate-topics.mjs` from BITB-301 (generalize it to take a file
   argument) so every reference is proven to exist in all 13 translations, with the same
   Psalm-numbering check.
2. Pure date helpers in `frontend/src/lib/votd.ts`: `referenceForDate(date)`,
   `isServableDate(date, now)`, `parseDateParam(str)`. Leap years: 29 February uses
   index 60; non-leap years skip it.
3. The three routes, metadata, feed, sitemap and homepage line (decisions 3–8).
4. `VerseOfTheDay` message namespace in all 11 locales.
5. Feed: valid RSS, absolute URLs, `<language>` per locale, each item's `pubDate` at
   00:00 UTC of its date.

## Tests (minimum)

- `referenceForDate`: 1 January → index 1; 28 February and 1 March in a leap and a
  non-leap year; 31 December in both; the list has exactly 366 entries.
- `isServableDate`: yesterday and today true; tomorrow false; malformed strings and
  impossible dates (`2026-02-30`) → `notFound()`.
- Parametrized over 11 locales with mocked verse fetches: one `<h1>`, localized date,
  verse text from that locale's translation, `dir="rtl"` for `ar`.
- Version faithfulness: the same date renders different mocked text for `en` and `it`.
- Rollover: with the clock mocked at 23:59:59 and 00:00:00 UTC the page shows
  consecutive entries.
- Feed parses as XML, has 14 items, newest first.
- Homepage hero contains the reference link for today.

## Acceptance criteria

- [ ] `/en/verse-of-the-day` shows a different verse on consecutive days
- [ ] Past dates resolve; future dates are `404`
- [ ] All 366 references exist in all 13 translations
- [ ] The feed validates
- [ ] The homepage shows today's reference
- [ ] **Owner step:** review the 366-verse list before merge

## Out of scope

- Push notifications and the Android home-screen widget (file follow-ups; this story
  gives them a URL to open).
- Per-user time zones.
- An AI-written daily reflection (cost per day × 11 languages, and unreviewed
  theological text on a public page — decide separately).

## Related

BITB-301, BITB-302, Icebox "Daily Devotional Notifications".

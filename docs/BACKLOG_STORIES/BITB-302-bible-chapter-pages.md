# BITB-302: Server-Rendered Bible Chapter Pages (Verses Addressable by Anchor)

**Status:** 🎯 Todo
**Priority:** P1
**Size:** L
**Created:** 2026-11-11
**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) row S3.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 3. **After BITB-300.**
**Commit:** `feat(frontend): server-rendered Bible chapter pages (BITB-302)`

## User story

As someone who searches for "John 3" or "Salmo 23", I want to read the chapter on a
fast, clean page in my language and be able to ask a question about what I just read.

## Problem

The database holds 403,856 verses across 13 translations (live `/scripture/stats` and
`/scripture/translations`, 2026-11-11). None of that text exists at a URL a search
engine, a messaging app or another website can link to. Chapters are shown only inside a
client-side modal (`frontend/src/components/ChapterModal.tsx`).

## Decisions already made

1. **Chapter pages, not one page per verse.** 1,189 chapters per translation is a
   healthy, content-rich set; 31,000 single-verse pages per translation would be thin
   pages. Verses are addressable as `#v16` on the chapter page. Revisit per-verse pages
   only with Search Console data.
2. **Routes:**
   - `/[locale]/bible` — the 66 books, grouped Old/New Testament, localized names.
   - `/[locale]/bible/[book]` — the chapters of a book.
   - `/[locale]/bible/[book]/[chapter]` — the chapter text.

   `[book]` is a slug of the English canonical name (`john`, `1-corinthians`,
   `song-of-solomon`), generated from the book list the API returns
   (`/api/v1/scripture/books`), not typed by hand. Display names come from
   `/api/v1/scripture/book-names` for the locale.
3. **One translation per locale: its default** (same map as BITB-301 decision 3). A
   `?translation=` query may switch the text for the reader but the canonical URL has no
   query and the variant carries `noindex`.
4. **Licence gate.** The repository documents the licence of only one translation
   (`README.md:449`: "Bible text uses the KJV (public domain)"). Publishing whole
   chapters is redistribution in a way that quoting a verse in a chat answer is not.
   Chapter pages are therefore served only for translations in an allowlist,
   `INDEXABLE_TRANSLATIONS` (a constant with a comment per entry citing the licence
   basis). **It ships containing `kjv` only.** For a locale whose default translation is
   not on the list, the three routes return `404` and are left out of the sitemap and
   navigation. Adding a translation is a one-line change the owner makes after
   confirming its licence — see Owner steps.
5. **Rendering:** on-demand ISR (`generateStaticParams` → `[]`, `dynamicParams = true`),
   `revalidate = 604800`. Scripture does not change; a week keeps the cache warm without
   build-time API access.
6. **Chapter page content:** `<h1>` "John 3 — King James Version" (localized book name,
   translation name from the API); verses as an ordered list with `id="v<N>"`;
   previous/next chapter links (crossing book boundaries); a link up to the book; an
   "Ask about this chapter" button that opens the chat with a prefilled prompt (the
   mechanism from BITB-301 decision 8 — implement it here if 301 has not merged).
7. **Out-of-range input** (`/bible/john/99`, unknown book slug, non-numeric chapter) →
   `notFound()`; never a `500`.
8. **Structured data:** `BreadcrumbList` only.
9. **Sitemap:** the chapter URLs for allowed translations go into a sitemap **index**
   with chunked child sitemaps (`generateSitemaps`), so the set can grow past 50,000
   URLs as translations are allowed. The existing 66 URLs stay in the first chunk.
10. **Titles and descriptions** are generated: title `"<Book> <chapter> — <translation
    short name>"`; description = the first ~150 characters of verse 1–2 text, cut at a
    word boundary (for scripts without spaces, at a character boundary), so every page
    has a unique, real description.

## Requirements

1. The three routes with metadata through `pageMetadata` (path-aware canonical and
   hreflang). `hreflang` alternates list **only locales whose default translation is
   allowed** — an alternate must not point at a `404`.
2. `frontend/src/lib/bibleRoutes.ts`: slug ↔ book mapping, allowlist, locale →
   translation, description builder. Pure functions, unit-tested.
3. Server-side fetch helpers for `/scripture/books`, `/scripture/book-names`,
   `/scripture/chapter/{book}/{chapter}` with Next's fetch cache. Read
   `api/routes/scripture.py:94-260` for the exact response shapes before coding.
4. Sitemap index and chunks (decision 9); update `sitemap.test.ts`.
5. `Bible` message namespace in all 11 locales (headings, testament names, "previous
   chapter", "next chapter", "Ask about this chapter", the prefill prompt template).
   Locales whose translation is not yet allowed still get their strings, so enabling a
   translation later is only the allowlist change.
6. Footer link "Read the Bible" shown only in locales with an allowed translation.
7. Arabic: `dir="rtl"`, logical classes, verse numbers rendered with the locale's
   expected digits only if the rest of the site already does so (check the chapter modal
   and match it).

## Tests (minimum)

- Slug mapping round-trips for all 66 books, including numbered books and multi-word
  names; generated from a fixture of the API's book list.
- Chapter page (mocked API): one `<h1>`, N verses with ids `v1…vN`, previous/next links
  correct at book boundaries (Genesis 1 has no previous; Revelation 22 has no next;
  Malachi 4 → Matthew 1).
- Allowlist: with only `kjv` allowed, `/en/bible/john/3` renders and `/it/bible/john/3`
  is `notFound()`; with a second translation allowed in the test, the Italian page
  renders **its own** text (version faithfulness) and appears in `hreflang`.
- Parametrized over all 11 locales with every translation allowed in the test: localized
  book name in the `<h1>`, correct `lang`, `dir="rtl"` only for `ar`, description cut
  safely (CJK, Devanagari, Arabic samples — no broken character).
- Invalid book, chapter 0, chapter 999, `chapter=abc` → `notFound()`.
- `?translation=web` on `/en/bible/john/3` → `noindex`, canonical without query.
- Sitemap index lists the chunks; chunk contents respect the allowlist.

## Acceptance criteria

- [ ] `/en/bible`, `/en/bible/john`, `/en/bible/john/3` are server-rendered with the KJV
      text in the HTML
- [ ] `https://…/en/bible/john/3#v16` scrolls to verse 16
- [ ] Locales without an allowed translation return `404` for these routes and have no
      links or sitemap entries pointing at them
- [ ] "Ask about this chapter" opens the chat with a prefilled, unsent prompt
- [ ] **Owner step:** for each of the other 12 translations (`web`, `ita1927`,
      `schlachter`, `luther1912`, `valera`, `ls1910`, `almeida`, `arabicsv`, `synodal`,
      `cuv`, `hindi`, `krv`), record the edition, its copyright status and the source of
      that information in `docs/` (a new `TRANSLATION_LICENCES.md`), then add the
      cleared ones to `INDEXABLE_TRANSLATIONS`
- [ ] **Owner step:** four weeks after deploy, record indexed `/bible/` pages from
      Search Console here

## Out of scope

- Per-verse pages; parallel translations; search within the Bible pages; audio.
- Replacing the chapter modal in the chat (a follow-up can link the modal to the page).
- Android.

## Related

BITB-136, BITB-298 (keeps the verse/chapter `GET`s unguarded on purpose), BITB-300,
BITB-301, BITB-303.

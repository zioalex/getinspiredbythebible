---
id: BITB-324
status: todo
priority: P3
size: S
created: 2026-11-16
---

# BITB-324: Server-Render the Localized 404 (Not Only After Hydration)

**Follow-up of:** BITB-300.

## Problem

BITB-300 localized the 404 page with a `NotFound` message namespace and a
`src/app/[locale]/[...rest]/page.tsx` catch-all that calls `notFound()`. An unknown path
such as `/ar/does-not-exist` now returns HTTP **404** with `noindex`, and in a browser it
shows the Arabic title, body and home link.

The server HTML does not contain that content, though. The response is Next's error
shell: `<html id="__next_error__">` with no `lang`/`dir`, and `<body><div hidden></div></body>`.
The localized text, and `lang="ar" dir="rtl"`, exist only in the RSC flight payload and
appear after client rendering. The same happens for `/zh/a/b/c` and `/en/about/extra`.
Crawlers and users without JS see an empty page. This was observed on Next 16.4.5 with
next-intl, while verifying BITB-300.

The SEO impact is small because the status is 404 and the page is `noindex`. Accessibility
and no-JS users are affected.

## Tasks

- Find out why the not-found boundary under `[locale]` renders as the `__next_error__`
  shell. Candidate causes: root `app/layout.tsx` versus `[locale]/layout.tsx` html
  ownership, a dynamic catch-all on a statically generated segment, and next-intl
  `setRequestLocale` in not-found.
- Make the server HTML contain the localized title, body, link and `<html lang dir>`.

## Acceptance criteria

- [ ] `curl -s https://voxquieta.org/ar/does-not-exist` contains the Arabic `NotFound.title`
      text and `dir="rtl"`. The status is still 404.
- [ ] Regression test for the server-rendered output, at least ar, zh, hi and ru.

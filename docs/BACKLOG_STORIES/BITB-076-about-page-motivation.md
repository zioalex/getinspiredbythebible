# BITB-076: "About" Page — Why Vox Quieta Exists

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (1–2 days, mostly copywriting + 11 locales)
**Created:** 2026-07-25

## User Story

**As a** visitor who has just found Vox Quieta,
**I want** to read who built this and why,
**so that** I can decide whether to trust a chatbot with something as personal as my faith and my
grief.

## Why

Vox Quieta asks people to type the hardest thing in their life into a text box. Right now the site
gives them no reason to believe anyone is behind it. There is a privacy policy, terms, a changelog
and a Play Store link — all of which answer *"what are you doing with my data"* — and nothing that
answers *"why does this exist and who made it"*. For a spiritual-support product that second
question is the one that actually earns the message.

The motivation is already written down. The author published it as:

> **"Building Something That Matters: How Claude Code Helped Me Create a Bible Inspiration Chatbot"**
> <https://ai4you.sh/posts/Building-Something-That-Matters-How-Claude-Code-Helped-Me-Create-a-Bible-Inspiration-Chatbot/>

That post is the **foundation and the canonical reference** for this page: the About page adapts it
for a first-time visitor (short, personal, non-technical) and links out to the full post for anyone
who wants the whole story, including how it was built.

> **Note for whoever implements this:** the post could not be fetched from the CI/agent sandbox
> (the egress proxy returns 403 for `ai4you.sh`), so the copy below is a *structure* to fill, not a
> transcription. Open the post, take the author's own words, and adapt them — do not let an LLM
> invent a founder story. Anything personal (the origin moment, the "why this matters" passage)
> must come from the post or from the author directly.

## Proposed Behaviour

A new static, server-rendered, localized page at `/{locale}/about`, built exactly like the existing
`/app` page (`frontend/src/app/[locale]/app/page.tsx`): `generateStaticParams` over
`routing.locales`, `generateMetadata` via `pageMetadata` from `@/lib/seo`, copy from a new `About`
translation namespace.

**Suggested section outline** (each a key group in the `About` namespace):

1. **Hero** — one sentence on what Vox Quieta is, in plain language.
2. **Why this exists** — the personal motivation, adapted from the post. First person, short
   paragraphs.
3. **What it does / what it is not** — grounded in scripture, multilingual, free; explicitly *not*
   a pastor, not a therapist, not a replacement for a church community. This mirrors the disclaimer
   the chat already shows (`Chat.disclaimer`) and the boundaries in the system prompt
   (`api/chat/prompts.py`, "## Boundaries").
4. **How it was built** — brief, honest note that it is an open-source side project built with AI
   assistance, linking the repo and the original post.
5. **Read the full story** — prominent outbound link to the ai4you.sh post.
6. **Get in touch / support** — link to the existing contact form and, once **BITB-074** lands, the
   support link.

**Entry points:**

- `Footer.tsx` gets an "About" link (alongside Get app / Privacy / Terms / Changelog).
- The main-menu / welcome area on the chat screen links to it — this is the surface most visitors
  actually see.
- `frontend/src/app/sitemap.ts` — add `/about` to `PATHS` (line 8) so all 11 locales are indexed.

**Localization:** the `About` namespace must exist in all 11 locale files
(`frontend/messages/{en,it,de,es,fr,pt,ar,ru,zh,hi,ko}.json`, per `frontend/src/i18n/routing.ts`).
Arabic must read correctly RTL — the layout already sets `dir` at the `<html>` level
(`frontend/src/app/[locale]/layout.tsx`).

## Acceptance Criteria

- [ ] `/{locale}/about` renders for all 11 locales, server-rendered and statically generated.
- [ ] Page copy is adapted from the ai4you.sh post and links to it explicitly as the full story.
- [ ] Page states plainly what Vox Quieta is *not* (not pastoral care, not counseling, not a
      substitute for a faith community).
- [ ] `About` namespace present and complete in all 11 `frontend/messages/*.json` files.
- [ ] Reachable from the footer **and** from the chat screen (menu or welcome area).
- [ ] `/about` added to `frontend/src/app/sitemap.ts` `PATHS`, with hreflang alternates (handled
      automatically by the existing mapping).
- [ ] Unique `metaTitle` / `metaDescription` per locale via `pageMetadata` — no duplicate-title
      warning from the SEO audit (`/seo-audit`).
- [ ] Arabic renders RTL without layout breakage.

## Tests to Add

- `frontend/src/app/[locale]/about/page.test.tsx` — renders headings and the outbound post link
  (mirror the existing `/app` page tests).
- Sitemap test asserting `/about` appears once per locale.
- The repo's message-completeness check (all locales carry the same key set) must cover the new
  namespace.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/app/[locale]/about/page.tsx` | **New** — the page |
| `frontend/messages/*.json` (11) | **New** `About` namespace |
| `frontend/src/components/Footer.tsx` | "About" link |
| `frontend/src/app/[locale]/ChatIsland.tsx` / `MainMenu.tsx` | In-app entry point |
| `frontend/src/app/sitemap.ts` | Add `/about` to `PATHS` |

## Out of Scope

- Android. The Android app should eventually link to the same page from Settings → About; file as a
  follow-up rather than widening this story.
- Any re-hosting of the blog post's full text. Link to it; do not copy it wholesale.

## Related

- **BITB-077** — the first-run modal that surfaces this page's message to existing users.
- **BITB-074** — "Support us" entry points; the About page is the natural home for that ask.
- **BITB-037** — SEO follow-ups (server-rendered pages, metadata, OG image).

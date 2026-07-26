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
> — ai4you.sh, 7 February 2026
> <https://ai4you.sh/posts/Building-Something-That-Matters-How-Claude-Code-Helped-Me-Create-a-Bible-Inspiration-Chatbot/>

That post is the **foundation and the canonical reference** for this page: the About page adapts it
for a first-time visitor (short, personal, non-technical) and links out to the full post for anyone
who wants the whole story, including how it was built.

## Source Material (from the post)

The parts that belong on an About page — the *why*, not the build log:

**The origin.** "Have you ever had an idea that just wouldn't leave you alone?" The motivation is
stated plainly:

> "Depression and mental health struggles affect so many people — young and old alike. I wanted to
> create something simple, accessible, and deeply rooted in Scripture that could offer
> encouragement when someone needed it most. Not a replacement for therapy or pastoral care, but a
> gentle companion for moments of struggle."

**The scope, deliberately narrow.**

> "It's not trying to be everything. It's trying to be one thing done well: a place to find hope and
> inspiration when you need it."

**Why a human still matters** (from "The Human Element (Still Essential)" — vision, quality
control, purpose):

> "Technology is just a tool. The 'why' behind this project — the empathy for people struggling
> with mental health, the desire to offer hope — that's entirely human."

**What the author actually wanted out of it.**

> "But honestly? I'm just happy it exists. It's out there. Someone having a rough day can visit
> that URL and find encouragement. That's what matters."

**Also usable:** the project is open source (repo linked from the post), it was built with AI
assistance by someone who is "not a professional frontend developer", and the author explicitly
invites feedback ("What worked? What could be better? What would make it more helpful?") — which
pairs naturally with the existing contact form.

### ⚠️ The post is a year old — adapt, do not transcribe

The post describes **v1.0** and several of its specifics are now wrong. The About page must not
repeat them:

| The post says | Reality today |
|---|---|
| Named "Get Inspired by the Bible", at `getinspiredbythebible.ai4you.sh` | **Vox Quieta**, at `voxquieta.org` (repo name unchanged) |
| "Clean HTML/CSS/JavaScript interface", "simple API" | Next.js App Router frontend, FastAPI backend, PostgreSQL + pgvector semantic search |
| Web only | Web **and** a published Android app |
| Bible in English, German, Italian; "more to come" (listed under *What's Next*) | 11 UI locales; multiple translations per language |
| — | Content-safety pipeline, Turnstile, verse-citation grounding, church finder |

Treat the post as the **origin story**, and let the About page say plainly that the project has
grown since — the rename in particular needs one sentence of continuity, since a reader arriving
from the post will be looking for a name that no longer appears on the site. The "What's Next" list
in the post is largely *done*; do not restate it as a roadmap.

Everything personal on the page must trace back to the post above or to the author directly — do
not let an LLM extend the founder story with invented detail.

## Proposed Behaviour

A new static, server-rendered, localized page at `/{locale}/about`, built exactly like the existing
`/app` page (`frontend/src/app/[locale]/app/page.tsx`): `generateStaticParams` over
`routing.locales`, `generateMetadata` via `pageMetadata` from `@/lib/seo`, copy from a new `About`
translation namespace.

**Suggested section outline** (each a key group in the `About` namespace):

1. **Hero** — one sentence on what Vox Quieta is, in plain language. The post's own framing is the
   strongest candidate: *a place to find hope and inspiration when you need it*.
2. **Why this exists** — the mental-health motivation, first person, two or three short paragraphs
   adapted from the origin passage above. This is the section that earns the first message; it
   should read like a person, not a mission statement.
3. **What it is not** — "not a replacement for therapy or pastoral care, but a gentle companion for
   moments of struggle" is the author's own line and already the right one. Reinforce with: not a
   pastor, not a therapist, not a substitute for a faith community. Consistent with the disclaimer
   the chat already shows (`Chat.disclaimer`) and the "## Boundaries" section of the system prompt
   (`api/chat/prompts.py`).
4. **What it does now** — grounded in scripture with visible verse references, 11 languages, on the
   web and Android, free. This is the section that carries the "it has grown since the post" note,
   including the rename from *Get Inspired by the Bible* to *Vox Quieta*.
5. **Built by one person, with AI help** — short and honest: an open-source side project, built
   with Claude Code by someone who is not a frontend developer, because the idea "wouldn't leave
   me alone". Link the GitHub repo. Keep the build details to a sentence — the post covers them.
6. **Read the full story** — prominent outbound link to the ai4you.sh post.
7. **Get in touch / support** — the author explicitly asks for feedback in the post; link the
   existing contact form and, once **BITB-074** lands, the support link.

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
      substitute for a faith community) — the post's own framing.
- [ ] The page reflects the project **as it is today**, not the post's v1.0 description: no stale
      stack, no stale language list, and one sentence of continuity covering the rename from
      "Get Inspired by the Bible" to "Vox Quieta" for readers arriving from the post.
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

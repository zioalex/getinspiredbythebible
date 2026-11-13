# BITB-083: About Page — Personal Voice + Screenshots from the Origin Story

**Status:** ✅ Done (PR #947 merged 2026-07-29)
**Priority:** P2
**Size:** M (~1 day, mostly copywriting + asset sourcing, ×11 locales)
**Created:** 2026-07-27
**Source:** Maintainer feedback after BITB-076/BITB-077 shipped (#939): *"it looks like a feature
description. I want people to feel my motivation and feeling. Make it personal — add screenshots
or renderings from the original post."*

## User Story

**As a** visitor reading `/about`, **I want** to feel a real person behind Vox Quieta — not read a
spec sheet — **so that** the page does the job BITB-076 set out for it: earning enough trust to
type something personal into the chat.

**As the** maintainer, **I want** the page to carry my actual voice and show what the product
looks like, **so that** it reads like *me* telling *my* story, not a summary of what I built.

## Why

BITB-076 shipped `/about` grounded in the ai4you.sh origin post, but under time pressure some
sections drifted from "a person telling their story" toward "a list of what the app does" — and
the page has zero images, despite the origin post itself using screenshots to make the product
feel real.

**The clearest evidence: `About.todayBody`, as shipped**

> "Scripture-grounded conversation with visible verse references, in 11 languages, on the web and
> on Android — free to use."

That's a feature list — four capabilities and a price, in the same register as the `/app` page's
marketing copy (`App.feature1Body`–`feature4Body`). Nothing in it is personal, and nothing in it
couldn't be written by someone who has never used the app.

**A stronger gap: the post's own closing line never made it onto the page at all.**

BITB-076's *Source Material* section captured this quote from the post as usable, and it never
got used:

> "But honestly? I'm just happy it exists. It's out there. Someone having a rough day can visit
> that URL and find encouragement. That's what matters."

That's the single most personal sentence in the source material — the moment the post stops
explaining and starts *feeling* — and the shipped page has no equivalent closing beat. It ends on
a contact form instead.

**The opening hook survived, but got merged into a paragraph instead of standing alone.** The
post opens with:

> "Have you ever had an idea that just wouldn't leave you alone? Something you felt deeply about
> but didn't quite have the time or technical bandwidth to build?"

`About.whyBody1` keeps the first sentence but drops the second, and immediately continues into
the mental-health motivation in the same paragraph — the hook doesn't get room to land before the
page moves on.

## Screenshots available from the origin post

The post itself contains two real app screenshots — direct evidence for "add screenshots... from
the original post":

| Asset | Post's own caption |
|---|---|
| `bible-chatbot-welcome-screen.png` | "The welcome screen offers simple prompts to help users get started with their questions and concerns." |
| `bible-chatbot-response-example.png` | "The chatbot provides detailed Biblical responses with relevant scripture references, making it easy to explore related verses." |

**⚠️ These show the app as it was in the post (v1.0, "Get Inspired by the Bible" branding, the old
UI)** — exactly the staleness BITB-076 already flagged for the *text*. Using them without comment
would visually contradict the page's own "one sentence of continuity" about the rename
(`About.todayContinuity`). Two honest options, not mutually exclusive:

1. **Use them explicitly as "then"** — small, captioned, e.g. "What it looked like when I first
   shared this" — next to or inside the "Read the full story" card. This *reinforces* the personal
   narrative (it's part of the journey) rather than pretending the page is current.
2. **Pair with a fresh screenshot of Vox Quieta today** — a "then / now" contrast is a stronger
   trust signal than either alone, and gives the "What it is today" section something to show
   instead of just tell.

**No author photo exists in the post** (confirmed — only the two app screenshots plus unrelated
site furniture: a thumbnail, the site logo, and two "related articles" teasers). Do not fabricate
one; if a personal photo is wanted, it has to come from the author directly, out of scope for
whoever picks this up otherwise.

## Proposed Behaviour

1. **Rewrite `todayBody`** (and probably retitle the section) away from the feature-list register.
   Ground it in something concrete and personal rather than a capability count — e.g. what it
   actually feels like to open the app on a hard day, not that it exists in 11 languages.
2. **Give the opening hook its own beat.** Split `whyBody1`'s first sentence (and its follow-up
   question, currently dropped) from the mental-health motivation that follows — let the hook land
   before the "why" argument starts.
3. **Add a closing personal beat** before the "Get in touch" section, adapted from the post's
   "I'm just happy it exists... someone having a rough day can visit that URL and find
   encouragement" — the sentence that's been sitting unused in BITB-076's own Source Material.
4. **Add screenshots**, per the "then" (and optionally "then / now") treatment above:
   - Origin-era images fetched from `https://ai4you.sh/assets/images/bible-chatbot/bible-chatbot-welcome-screen.png`
     and `.../bible-chatbot-response-example.png` — confirm licensing/reuse with the author (it's
     the author's own post, but still verify) before committing them to `frontend/public/about/`.
   - If pursuing the "now" half: a fresh screenshot of the current Vox Quieta chat, taken the same
     way `app-hero.png` was sourced for the `/app` page.
5. **Leave `notBody` alone.** It's a safety boundary statement ("not a pastor, not a therapist, not
   a substitute for a faith community"), consistent with `Chat.disclaimer` and the system prompt's
   "## Boundaries" section (`api/chat/prompts.py`) — it needs to stay unambiguous, not warm. Don't
   soften it in the name of "personal."
6. **Cascade to the intro modal.** BITB-077's `AboutIntroModal` explicitly sources its copy from
   this same `About` namespace ("Copy comes from the `About` namespace"). If the tone/wording of
   the sections it draws from changes, `About.introBody` (and the modal's ~60-word budget) should
   be revisited for consistency — not left quoting the pre-rewrite voice.

## Acceptance Criteria

- [x] `About.todayBody` no longer reads as a feature/spec list; the capability facts (languages,
      platforms, free) can still be present but are not the sentence's whole content.
- [x] The opening hook ("Have you ever had an idea...") gets its own sentence/paragraph, including
      the follow-up question the shipped copy currently drops.
- [x] A closing personal beat, adapted from "I'm just happy it exists... that's what matters,"
      appears before the "Get in touch" section.
- [x] At least one screenshot renders on the page, explicitly labeled if it's origin-era (not
      presented as current-state UI).
- [x] `notBody`'s safety-boundary language is unchanged in meaning (wording tweaks for flow are
      fine; the boundaries themselves are not softened).
- [x] All copy changes applied across all 11 `frontend/messages/*.json` locales — not just `en`,
      and not machine-retranslated without checking the existing translations' register still
      matches the more personal English source.
- [x] `About.introBody` reviewed against the rewritten page copy; updated if it now quotes
      superseded phrasing.
- [x] Arabic (RTL) and CJK locales checked for layout with the added image(s).
- [x] Unique `metaDescription` per locale still holds if `heroLead`/`whyBody1` wording shifts (the
      SEO audit's duplicate-title check, per BITB-076's own AC).

## Tests to Add / Update

- `frontend/src/app/[locale]/about/page.test.tsx` — update the `notBody` assertion (should still
  pass unchanged), add an assertion for the new image element and its alt text.
- `frontend/src/components/AboutIntroModal.test.tsx` — update the asserted `introBody` text if it
  changes.
- Extend the repo's locale-completeness check to cover any new namespace keys this introduces
  (e.g. an image `alt` translation key), same as `src/test/translations.test.ts` already does for
  the rest of `About`.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/app/[locale]/about/page.tsx` | Add screenshot(s); restructure the hook/closing beats |
| `frontend/messages/*.json` (11) | Rewritten `About.today*`, `whyBody1` split, new closing-beat key(s), possibly `introBody` |
| `frontend/public/about/` | **New** — origin-era screenshot(s), and a current one if pursuing "then / now" |
| `frontend/src/components/AboutIntroModal.tsx` | Only if `introBody` copy changes |
| `frontend/src/app/[locale]/about/page.test.tsx` | New assertions for image + rewritten copy |

## Out of Scope

- An author photo — none exists in the source material; fabricating one is explicitly against
  BITB-076's rule that personal content must trace back to the post or the author directly.
- Re-litigating `notBody` / the safety-boundary language — that's deliberately clinical and stays
  that way.
- Sourcing a *new* origin-post-style essay. This story restyles the existing page's prose; it does
  not commission new personal writing beyond adapting quotes already captured in BITB-076.

## Related

- **BITB-076** — the About page this restyles; its *Source Material* section is the source of
  truth for what's allowed to appear here (quotes must trace back to the post or the author).
- **BITB-077** — the intro modal; its copy is sourced from this page's `About` namespace, so a
  tone change here should be checked against it.

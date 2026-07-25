# BITB-077: "Why Vox Quieta" Intro Modal — Once for Everyone Now, New Visitors Afterwards

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S (< 4 hrs, after BITB-076)
**Created:** 2026-07-25

## User Story

**As a** person opening Vox Quieta,
**I want** a short, dismissible introduction explaining who made this and why,
**so that** I know what I am talking to before I type something personal into it.

**As the** maintainer,
**I want** every current user to see it once when it ships, and only first-time visitors to see it
after that,
**so that** the announcement reaches the existing audience without nagging them forever.

## Why

**BITB-076** puts the motivation on an `/about` page — but a page nobody clicks changes nothing.
The message is new, so it warrants one deliberate interruption; after that it belongs in the
onboarding path only.

The repo already contains both halves of the mechanism, and one of them is currently dead code:

- **A "show once ever" gate**: the splash cookie in `frontend/src/app/[locale]/providers.tsx:13-24`
  (`splash_seen=1`, 1-year max-age) gating `SplashScreen` at `:88-98`. Note the deliberate
  hydration-safe pattern documented there (seed `false` on both server and client, read the cookie
  in an effect) — see **BITB-069** for what happens if that is done naively.
- **A "show once per version" gate**: `frontend/src/components/WhatsNewModal.tsx` — `localStorage`
  key `vq:lastSeenVersion`, and at `:33-40` it *silently records* the version on a first-ever visit
  so newcomers are not shown a changelog they have no context for. That component is rendered in
  `frontend/src/app/[locale]/layout.tsx:111`, but the codebase contains no other reference to it —
  it is effectively the pattern to copy, and worth confirming it is actually reachable in
  production while working here.

This story needs the *union* of those two behaviours, which is neither one exactly.

## Proposed Behaviour

A dismissible modal — `AboutIntroModal` — showing a condensed version of the About copy
(2–3 short paragraphs from the `About` namespace), with:

- a primary action → `/{locale}/about` (the full page),
- a secondary "Continue" / close action,
- an accessible dialog shell (`role="dialog"`, `aria-modal`, focus trap, Esc to close), modelled on
  `WhatsNewModal.tsx:62-90`.

**Display rule** — a single `localStorage` key, e.g. `vq:aboutIntroSeen`, holding a **version
string** (`"1"` for this rollout):

| Visitor | Key state on load | Behaviour |
|---|---|---|
| Existing user (has `splash_seen` cookie or any prior local state) | key absent | **Show once**, then write `"1"` |
| Brand-new visitor, first ever load | key absent, no prior state | Show once, then write `"1"` |
| Anyone who has already dismissed it | key `= "1"` | Never show again |
| Future rollout with materially new content | key `< "2"` | Show again (bump the constant deliberately, not on every release) |

In other words: *"all users now, new users later"* falls out of a one-time key that is written on
dismissal. The distinction the user asked for — everyone now, new visitors afterwards — is
satisfied because after the rollout window the only people without the key are new visitors.

**Sequencing with the existing splash.** The animated `SplashScreen` runs first on a cold visit.
The intro modal must appear **after** the splash completes (i.e. gate it on `splashDone` in
`providers.tsx`), never stacked on top of it. It should also not collide with `WhatsNewModal`: if
both would fire on the same load, show the intro modal and defer "what's new" to the next visit.

**Hydration safety is a hard requirement.** Read `localStorage` in a `useEffect` after mount and
seed the visible state to `false` on both server and client. See BITB-069 (`docs/DONE/`) for the
exact failure this avoids.

## Acceptance Criteria

- [ ] On first load after deploy, every visitor sees the intro modal exactly once.
- [ ] Dismissing it (button, Esc, or backdrop) persists — it never reappears for that browser.
- [ ] A returning visitor who already dismissed it never sees it again, including across sessions.
- [ ] A brand-new visitor sees it once, after the splash animation completes.
- [ ] The modal never renders simultaneously with `SplashScreen` or `WhatsNewModal`.
- [ ] Primary action navigates to the localized `/about` page.
- [ ] Copy comes from the `About` namespace — all 11 locales, no English fallback in a non-English
      UI.
- [ ] No SSR/CSR hydration mismatch (no console warning; verified in a production build).
- [ ] Keyboard accessible: focus moves into the dialog, Esc closes, focus returns to the page.
- [ ] Bumping the version constant re-shows it — proven by a test, not by hand.

## Tests to Add

- `frontend/src/components/AboutIntroModal.test.tsx` — shows when the key is absent; hidden when it
  matches the current version; shows again when the stored version is older; writes the key on
  dismiss.
- `frontend/src/app/[locale]/providers.test.tsx` — extend the existing splash test to assert the
  modal only renders after `onComplete` fires.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/components/AboutIntroModal.tsx` | **New** |
| `frontend/src/app/[locale]/providers.tsx` | Render after `splashDone`; own the display gate |
| `frontend/messages/*.json` (11) | `About.intro*` keys (condensed copy + CTA labels) |
| `frontend/src/components/WhatsNewModal.tsx` | Defer when the intro modal is showing |

## Out of Scope

- **Android.** The equivalent there is a first-run sheet; the app already has a splash
  (`android/.../presentation/screens/SplashScreen.kt`), a what's-new sheet (**BITB-058**) and a
  first-run spotlight story (**BITB-054**). Fold the About content into those rather than adding a
  fourth first-run interruption — track separately.
- Server-side per-user tracking. This is a `localStorage` gate; clearing site data re-shows it, and
  that is an acceptable trade for storing nothing about the visitor.

## Related

- **BITB-076** — the About page this modal points at (**blocks this story**).
- **BITB-069** — splash-screen hydration mismatch; the trap to avoid.
- **BITB-058** — Android "What's New" on launch; the same show-once-per-version idea.
- **BITB-054** — Android first-run feature spotlight.

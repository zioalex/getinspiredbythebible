# BITB-168: Surface the Support-Us Entry Points Without Nagging (Web + Android)

**Status:** 🚧 In Progress
**Priority:** P2
**Size:** M
**Created:** 2026-09-30
**Found by:** Product-owner feedback (2026-09-30: "the Support us link at the bottom is very
hidden in the web version") + BITB-074's own deferred fast-follow note

## User Story

**As** a user who would like to support Vox Quieta, **I want** the donation entry to appear in the
places I naturally look — the chat menu, the drawer, the About page — **so that** I can contribute
if and when I choose, without the app ever pressing me.

## Why This Exists

BITB-074 (PR #1084, v1.56.0) shipped the Support-Us entries, but every placement is effectively
invisible:

| Platform | Current placement | Problem |
| --- | --- | --- |
| Web — chat page (the site root, where users spend ~all their time) | 6th of 6 links in `ChatFooterLinks.tsx`, `text-[11px] text-gray-400` | Nearly invisible; the page-level `Footer` is not even rendered on the chat route (`FooterGate` returns `null` for `/`) |
| Web — hamburger menu (`MainMenu.tsx`) | No Support item | History / Language / Bible version / Community / About — the natural menu has no donate entry |
| Web — About page | No support section | Page has Contact / GitHub / origin-story sections — the place supportive users actually read says nothing about supporting |
| Android — Settings | "Support Vox Quieta" is the **last of 5** plain `TextButton`s at the bottom of the About section, below Clear-history / diagnostics / contact | Below the fold; visually identical to legal links |
| Android — chat drawer (`ChatScreen.kt` ModalDrawerSheet) | No Support item | BITB-074 explicitly deferred this: *"flag as a fast follow if Settings-only placement proves too low-visibility"* — the product owner has now confirmed exactly that |

Timing note: the v1.56.0 deploy (which carries the Android row) was still **pending** as of
2026-09-30, which is why nothing was visible on Android yet. This story's placements should land
on `main` before/with the **next** release train so the newly-visible entry points ship in one go.

## Design Principles — "Visible, Never Pressing"

This story is bound by the following anti-nag rules (acceptance criteria enforce them):

1. **Passive discoverability only.** Put the entry where users already look. Never interrupt.
2. **No modal, no interstitial, no banner inside the chat flow, no session-count-gated prompts,
   no repeated nudges, no urgency/goal language ("we're almost there"), no emoji.**
3. The single allowed exception: a **one-time mention in the Android What's New dialog**
   (established, dismissible, shows-once-per-release pattern, BITB-058).
4. **Invitation tone, not fundraising pressure.** "Support us" / "Keep Vox Quieta free" framing —
   donations cover hosting + LLM inference costs; optional; no perks (keeps the pure link-out
   inside Google Play's donation carve-out, per BITB-074's policy research).
5. **Recognizability, not loudness.** A small heart glyph and menu placement are the visibility
   levers — not bigger text, stronger colors, or animation.

## Where It Plugs In

### Web (Next.js frontend)

1. **`frontend/src/components/MainMenu.tsx`** — add a "Support us" item at the end of the
   hamburger menu (after About), styled identically to the existing items, with a `Heart` icon
   from `lucide-react`. External link: `target="_blank" rel="noopener noreferrer"`, closes the
   menu on click (same pattern as the other items).
2. **`frontend/src/components/Footer.tsx` / `ChatFooterLinks.tsx`** — give the Support link a
   subtle distinguishing treatment: an inline `Heart` glyph (small, muted — e.g. `w-3 h-3`) next
   to the label. **Keep the current font size (`text-sm` / `text-[11px]`) and gray tones
   unchanged** — the glyph is the lift, not loudness. `useFooterLinks()` is shared by both, so
   the cleanest shape is likely an optional `icon` field on `FooterLink` or a dedicated
   `SupportLink` component both variants render.
3. **`frontend/src/app/[locale]/about/page.tsx`** — new "Keep Vox Quieta free" section: one or
   two sentences (donations cover hosting and LLM inference; entirely optional; no perks) plus a
   single link-out, styled like the existing origin-story CTA card. Place it near the Contact
   section — people who read to the bottom of About are the likeliest supporters.

### Android

4. **`android/.../presentation/screens/ChatScreen.kt`** (drawer) — the BITB-074 fast-follow: a
   `NavigationDrawerItem` "Support Vox Quieta" with a heart icon, placed in the bottom group
   between "Search community" and Settings. Opens `BuildConfig.DONATE_URL` via the same
   `uriHandler` pattern `SettingsScreen` uses.
5. **What's New dialog** (BITB-058 pattern) — a one-time entry in the next release's What's New
   list mentioning that the app can now be supported (worded as information, not an ask).
6. **Settings reorder (optional, nice-to-have)** — move the Support row out of the tail of the
   About section, e.g. directly after "Get in Touch" with the existing `settings_support_us`
   string. Still a plain `TextButton` — no styling escalation. Decide at implementation.

### Measurement (no in-app analytics)

7. Append per-surface `ref` query params to the donate URL — `?ref=web-menu`,
   `?ref=web-footer`, `?ref=web-about`, `?ref=android-drawer`, `?ref=android-settings` — so the
   destination page's own analytics show which entry point works. Add a tiny helper per platform
   to compose base URL + `ref`; do **not** inline string concatenation at each call site.
   Ordering with BITB-157 (env wiring): either story may land first, but keep a single shared
   donate-URL helper per platform so the base URL (env-driven after 157) and the `ref` suffix
   live in exactly one place.

### i18n (all 11 languages)

- New keys (`MainMenu`/`Chat` namespace for the menu item, `About.supportTitle`/`About.supportBody`/
  `About.supportLinkLabel` or similar) in **all 11** `frontend/messages/*.json` files.
- New/adjusted strings in **all 11** `android/app/src/main/res/values-*/strings.xml`
  (`drawer_support_us`, What's New entry). CI's translation-validation job enforces Android
  parity; frontend has no such job, so the story's review checklist must verify 11/11 manually.
- Arabic (RTL) rendering of the new strings must be spot-checked (i18n-qa pass).

## Acceptance Criteria

- [x] Web hamburger menu shows "Support us" with a heart icon; opens the donate URL in a new tab
      (`noopener noreferrer`); menu closes on click
- [x] Footer + ChatFooterLinks Support link renders the heart glyph with **no** increase in font
      size, font weight, or color intensity
- [x] About page renders the "Keep Vox Quieta free" section with a working link-out
- [x] Android chat drawer shows "Support Vox Quieta" with a heart icon (bottom group), opening
      `BuildConfig.DONATE_URL`
- [x] Android What's New dialog mentions the support option once in the next release's list
- [x] (optional) Settings Support row repositioned out of the About tail
- [x] Every donate URL carries its per-surface `ref` param, composed via a single helper per
      platform
- [x] All new copy present in 11/11 frontend locales and 11/11 Android locales — no
      fallback-to-English anywhere
- [x] **No modal, banner, interstitial, timed prompt, urgency language, or gated perk anywhere
      in scope** (the anti-nag rules above are acceptance-testable)
- [x] Frontend tests: MainMenu (item renders, href/target/rel, closes menu), Footer/ChatFooterLinks
      (glyph present, link semantics unchanged), About page section
- [x] Android: Compose UI test for the drawer item (per the `*ComposeTest.kt` tier) + What's New
      content test; translation-validation CI green
- [ ] Manual QA on both platforms: entry discoverable within ≤2 taps from the chat surface;
      link opens in browser/Custom Tab in at least 2 locales

## Implementation Decisions

- **Chat-footer ref split:** `useFooterLinks({ supportRef })` defaults to `web-footer`;
  `ChatFooterLinks` passes `web-chat-footer` so the two surfaces are distinguishable. Added
  `web-chat-footer` to the ref list above.
- **What's New marker mechanism:** no prefs/state. `shouldShowSupportNote(latestBody)` is true
  while the latest changelog entry contains `BITB-168`, so the note appears once per release
  (the sheet is already shown once per update) and vanishes when a later release is latest.
  The release commit/changelog must therefore carry the `(BITB-168)` reference.
- **Settings row moved** directly after the "Get in Touch" button; still a plain `TextButton`.
- **About page uses a quiet inline link** (like the GitHub/Contact links), not a solid pill.
- **Menu label reuses `Footer.supportUs`** — no new menu key.
- Web helper: `frontend/src/lib/donateUrl.ts`; Android helper: `utils/DonateUrl.kt`.

## Out of Scope

- BITB-157's `NEXT_PUBLIC_DONATE_URL` deployment wiring (separate story — recommended to pair,
  not required)
- Any in-app analytics/telemetry for link clicks
- A Stripe-backed native `/support` page (BITB-074 Phase 2)
- Google Play Billing or anything perk-gated
- Any nag/banner/prompt mechanism — if a placement in this story proves insufficient, the
  follow-up must still respect the anti-nag rules

## Dependencies & Caveats

- **Ko-fi page is live (2026-09-30, owner-confirmed and verified by fetch):**
  `ko-fi.com/voxquieta` — page "Alessandro S.", a **$80/month "Monthly infrastructure costs"**
  goal, checkout via card (Stripe) **and** PayPal. The `https://ko-fi.com/voxquieta` hardcoded as
  the `NEXT_PUBLIC_DONATE_URL` / `BuildConfig.DONATE_URL` fallback is therefore the real URL,
  not a placeholder — donations are live *today* for anyone who finds the buried entries, which
  is exactly why this visibility story matters now. Remaining human task from BITB-074: the
  GitHub Sponsors handle (`.github/FUNDING.yml` → `github: [zioalex]`) is still a TODO.
- **Stale comments to clean up while implementing:** `Footer.tsx`'s "Placeholder Ko-fi page"
  header comment and `.github/FUNDING.yml`'s maintainer TODO both predate this confirmation —
  update them in this story's implementation PR (the web work touches `Footer.tsx` anyway).
- **Keep Ko-fi supporter perks unconfigured:** Ko-fi's checkout template advertises monthly
  "member-only benefits" upsells. As long as no actual perks/tiers are configured on the page,
  the link-out stays a pure donation inside Google Play's donation carve-out (BITB-074's policy
  research). If perks are ever added, re-check Play Developer Program Policy before shipping
  the Android entries.
- Should ride the next Android release train after the currently-pending v1.56.0 deploy.
- No backend (`api/`) changes.

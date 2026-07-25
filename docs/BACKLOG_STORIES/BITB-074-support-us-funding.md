# BITB-074: "Support Us" Funding Entry Points (Web, Android, GitHub)

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (4–8 hrs, excluding manual Ko-fi/GitHub Sponsors account setup)
**Created:** 2026-07-21

**As a** supporter of Vox Quieta, **I want** a clear, low-friction way to
financially support the project from the website, the Android app, and the
GitHub repo, **so that** I can help cover hosting/LLM inference costs and keep
the project running, without the app ever touching payment data itself.

## Research: funding-platform comparison

| Option | Platform fee | Setup effort | One-time & recurring | Branding | Google Play-safe as pure link-out? | Best for |
|---|---|---|---|---|---|---|
| **GitHub Sponsors** | 0% (Stripe processing only, sometimes absorbed) | Minutes — enable + `FUNDING.yml` | Both | GitHub-hosted "Sponsor" button on the repo | N/A (not in-app) | Devs/contributors browsing the repo |
| **Ko-fi** | 0% platform fee (free tier) + card processing | Minutes — hosted page | Both (one-off "buy a coffee" + monthly memberships) | Custom logo/banner/colors, own page URL, optional embeddable widget | Yes, if framed as no-perk support | General end users, indie/faith-based projects |
| Buy Me a Coffee | 5% platform fee + processing | Minutes | Both | BMC-branded page | Yes, if no perks | General consumer apps |
| Patreon | 8–12% + processing | Moderate — tiers/benefits to configure | Recurring-first | Patreon-branded | Riskier — commonly built around perks, which can pull in Play Billing | Ongoing content creators with tiered rewards |
| Open Collective | ~10% (host + platform fee) | Higher — needs a fiscal host or own legal entity | Both | Full public ledger of funds raised/spent | Yes | Community trust via financial transparency |
| Stripe Payment Link / Checkout (self-hosted) | ~2.9% + 30¢ only | Higher — own page/webhook (or a no-code Payment Link) | Both, fully configurable | Full control, native `voxquieta.org/support` page | Yes | Lowest fees at scale, full branding control |
| PayPal.me / donate button | ~2.9% + fixed fee | Minutes | One-time easy; recurring weaker | PayPal-branded | Yes | Users who prefer PayPal exclusively |

**Recommendation: Ko-fi as the primary, user-facing donation page, plus GitHub
Sponsors enabled on the repo for the developer audience.**

Rationale:

- **Zero platform fee** (vs. Buy Me a Coffee's 5%, Patreon's 8–12%) — more of
  each donation reaches the project.
- Supports **both one-time tips and monthly memberships** without forcing a
  subscription model, so it fits a "buy me a coffee" ask as well as a
  sustaining-supporter ask.
- **Zero backend work**: it's a hosted page we link out to. Vox Quieta's own
  frontend/API/Android app never touch card data, so there's no PCI-DSS
  surface and no webhook to build for the MVP.
- Supports both Stripe and PayPal checkout under the hood, which covers more
  of the app's 9 locales (en/it/fr/de/es/pt/ru/zh/hi/ar) than a PayPal-only or
  Stripe-only option would.
- Because no feature is unlocked or gated in exchange for the donation, this
  is a genuine "support the creator" gift with no goods/services attached —
  the pattern Google Play's policy carve-out for real-money donations is
  built around, so it can be a plain external link from the Android app
  instead of a Play Billing in-app product. **This assumption must be
  re-checked against the current Play Developer Program Policy before
  release**, since store policy changes over time.
- GitHub Sponsors costs nothing to enable (just a `FUNDING.yml` + a signup)
  and captures anyone who lands on the repo directly — a separate audience
  from the app's end users.

Deferred for a possible Phase 2 (not in this story): a native
`voxquieta.org/support` page backed by Stripe Payment Links, once donation
volume justifies shaving off Ko-fi's card-processing overhead and owning the
full page branding/analytics.

## Where it plugs in

### Web (Next.js frontend)

- `frontend/src/components/Footer.tsx:10-31` — add a "Support us" link next to
  the existing `getApp` / `navPrivacy` / `navTerms` / `changelog` links,
  opening the Ko-fi URL in a new tab (`target="_blank" rel="noopener
  noreferrer"`).
- `frontend/messages/{en,it,fr,de,es,pt,ru,zh,hi,ar}.json` — add a
  `Footer.supportUs` key (mirroring the existing `Footer.getApp` /
  `Footer.changelog` keys) in **all ten** locale files — no locale left with a
  missing key.
- Donate URL should live in one place (e.g. a constant next to `Footer.tsx` or
  an env var) rather than hard-coded inline, since Ko-fi page slugs/URLs can
  change.

### Android app

- `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/SettingsScreen.kt` —
  add a "Support Vox Quieta" row, most naturally as another item in the
  existing **About** section (alongside Privacy Policy/Terms/Changelog,
  `SettingsScreen.kt:219-278`), using
  `LocalUriHandler.current.openUri(donateUrl)` — the same idiomatic Compose
  pattern already used in `ChurchFinderBottomSheet.kt:260,296,311` and
  `ChangelogScreen.kt:116,121`, rather than the manual `Intent(ACTION_VIEW)`
  pattern used for the locale-aware legal URLs.
- No new navigation route is needed — this opens the system browser/Custom
  Tab directly, it doesn't need its own screen.
- Out of scope for this story: adding a matching entry to the `ChatScreen.kt`
  navigation drawer (`ChatScreen.kt:585-687`) — flag as a fast follow if
  Settings-only placement proves too low-visibility.

### GitHub repo

- `.github/FUNDING.yml` (new file) — add `github: [<sponsors-handle>]` and
  `ko_fi: <ko-fi-username>` so GitHub renders its native "Sponsor" button on
  the repo page.
- `README.md` — optional short "Support / Sponsor" line or badge near the top
  (repo already has a `Prod Monitor` badge to follow as a style precedent).

## Acceptance Criteria

- [ ] Ko-fi page created and configured (external manual step, tracked here
      as a checklist item, not code)
- [ ] `.github/FUNDING.yml` added, enabling GitHub's native "Sponsor" button
- [ ] `Footer.tsx` renders a "Support us" link to the Ko-fi page, opening in a
      new tab
- [ ] `Footer.supportUs` translation key present in all 10 locale files with
      no missing/fallback-to-English entries
- [ ] Android `SettingsScreen.kt` has a "Support Vox Quieta" row in the About
      section that opens the donate URL via `LocalUriHandler`
- [ ] No payment data, cardholder data, or webhook is ever handled by Vox
      Quieta's own backend/frontend/app — purely a link-out to the hosted
      Ko-fi checkout
- [ ] No feature is gated or unlocked in exchange for donating (keeps this
      out of Google Play Billing scope) — explicitly re-verified against the
      current Play Developer Program Policy before shipping
- [ ] Copy reviewed for tone consistency with the app's pastoral/spiritual
      voice (e.g. "Support Vox Quieta", not aggressive fundraising language)
- [ ] Manual QA: link opens correctly from Android (Custom Tab/browser) and
      from the web (new tab) in at least 2 of the 10 locales

## Out of scope

- In-app purchases / Google Play Billing integration
- A native Stripe-backed `/support` checkout page on voxquieta.org (Phase 2)
- Recurring-subscription management UI inside the app (handled entirely by
  Ko-fi's own account/member management)
- Any backend (`api/`) changes

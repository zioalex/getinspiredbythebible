# App Store Compliance Checklist (iOS)

Stub for BITB-088 to fill. Modelled on `docs/android/play-console-compliance.md`: Console-only items have no home in the codebase and are easy to lose — track them here, check off and archive, don't delete.

Pre-recorded BITB-085 decisions: **no Ko-fi/donate entry point on iOS v1** (Guideline 3.2.1(vi)); no accounts, no IAP, no ads, no tracking, no permissions beyond network (Android requests only `INTERNET` + `ACCESS_NETWORK_STATE`); `ITSAppUsesNonExemptEncryption = false` (HTTPS only); privacy answers derived from the settled Play Data safety position (chat text shared with OpenRouter/Azure OpenAI to generate + safety-screen; no location).

## Open items

- [ ] App Store Connect record + bundle `org.voxquieta.app` (BITB-085).
- [ ] `PrivacyInfo.xcprivacy` + App Privacy label answers (BITB-088, minimal if BITB-087 ships NoOp analytics).
- [ ] Age rating: biblical grief/violence context + LLM-generated content disclosure; review notes cite pre-generation safety (`CONTENT_SAFETY_ENABLED` on in prod), no user-to-user content.
- [ ] Guideline 4.2 review notes: native streaming chat, offline history, Dynamic Type, light/dark, 11 locales.
- [ ] Screenshots, metadata under `ios/fastlane/metadata/` (English-only v1), What's New from `CHANGELOG.md`.

## General checklist for future Apple policy announcements

1. Read the announcement in full; note effective date and deadline.
2. Triage against this app (no accounts, no location, user↔AI chat only, no UGC surface).
3. Split code vs Connect-only work; do Connect items in App Store Connect, then check boxes here with PR/commit links.

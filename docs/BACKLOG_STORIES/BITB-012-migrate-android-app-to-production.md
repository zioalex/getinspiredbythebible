---
id: BITB-012
status: todo
priority: P3
size: XL
rank: 240
---

# BITB-012: Migrate Android App to Production

**Status note:** (BITB-003 unblocked ✅)

**As a** mobile user,
**I want** to download the app from Google Play Store,
**so that** I can use it on my phone without installing from APK.

**Acceptance Criteria:**

- [x] Turnstile bot protection enabled (BITB-003 ✅)
- [x] App icon and branding finalized (`android/play_store_assets/`)
- [x] Privacy policy written (`docs/privacy-policy.md`)
- [x] Terms of service written (`docs/terms-of-service.md`)
- [x] Play Store metadata created (`android/fastlane/metadata/android/en-US/`)
- [x] Fastlane configured for Play Store uploads (`android/fastlane/`)
- [x] Release signing config added to `android/app/build.gradle.kts`
- [x] GitHub Actions publish workflow created (`.github/workflows/android-publish.yml`)
- [ ] Production keystore generated and GitHub secrets set (`KEYSTORE_FILE`, `KEYSTORE_PASSWORD`,
  `KEY_ALIAS`, `KEY_PASSWORD`, `GOOGLE_PLAY_JSON_KEY`)
- [x] Screenshots captured (9 screens) and added to `android/play_store_assets/screenshots/` and
  `android/fastlane/metadata/android/en-US/images/phoneScreenshots/`
- [ ] Google Play Console: app created, listing filled, content rating completed
- [ ] App submitted and approved by Google
- [ ] Post-launch monitoring verified (Firebase Crashlytics + Analytics)

**Tech Constraints:**

- Must meet Google Play Store policies
- Must comply with GDPR/privacy regulations
- Must have Turnstile enabled before public release

**Out of Scope:**

- iOS app (future consideration)
- In-app purchases or monetization

**Dependencies:**

- ✅ BITB-003 (Turnstile on Android) — done

**Note (2026-07-29):** the *Out of Scope* line above ("iOS app — future consideration") is now
superseded. iOS is gated Later / Platform Expansion work: BITB-084 → BITB-085 → BITB-086 →
BITB-109 → BITB-087 → BITB-088.

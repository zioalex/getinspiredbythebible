# Android Release Checklist

> **Purpose** — Track every item required before the app can be published publicly on the
> Google Play Store. Items are grouped by who owns them and ordered by blocking severity.

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Done |
| 🔧 | Code change needed (in repo) |
| 🔑 | Ops / secrets / CI configuration |
| 🎨 | Asset creation (design) |
| 📋 | Play Console task (no code) |

---

## P0 — Blockers (app cannot be published without these)

### 🔑 Firebase project setup
- [ ] Create Firebase project for `com.bibleinspiration` at console.firebase.google.com
- [ ] Download real `google-services.json` and add to CI secrets (env var `GOOGLE_SERVICES_JSON_BASE64`)
- [ ] Enable **Crashlytics** and **Google Analytics** in the Firebase console
- [ ] Verify ProGuard mapping upload is configured for Crashlytics de-obfuscation
  - CI step: `./gradlew uploadCrashlyticsMappingFileRelease` after signing

**Why blocking:** `firebase-analytics` and `firebase-crashlytics` are no-ops without a valid
`google-services.json`. The debug build intentionally has `FIREBASE_ENABLED=false`; the release
build needs a real Firebase project to collect crashes and analytics.

---

### 🔑 Android keystore / app signing
- [ ] Generate a release keystore:
  ```bash
  keytool -genkey -v -keystore release.jks -keyalg RSA -keysize 2048 \
    -validity 10000 -alias bible-release
  ```
- [ ] Add the following GitHub Actions secrets:
  - `KEYSTORE_BASE64` — base64-encoded `.jks` file
  - `KEYSTORE_PASSWORD`
  - `KEY_ALIAS`
  - `KEY_PASSWORD`
- [ ] Verify CI release build signs correctly and produces a valid AAB

**Why blocking:** Google Play requires a signed AAB. Without a keystore the release workflow
produces an unsigned artifact that Play Console will reject.

---

### 📋 Privacy policy page
- [ ] Publish a privacy policy at `https://getinspiredbythebible.com/privacy`
  (or update `PRIVACY_POLICY_URL` in `build.gradle.kts` to point to the real URL)
- [ ] Privacy policy must disclose:
  - Firebase Analytics — app interaction data collected
  - Firebase Crashlytics — crash logs and device diagnostics collected
  - No data is sold to third parties
  - Anonymous session ID stored locally (DataStore) for analytics
  - Optional email address collected if user submits a contact form

**Why blocking:** Google Play mandates a privacy policy for apps that collect or transmit user
data. Firebase Analytics and Crashlytics both qualify. The in-app link in Settings already
points to `BuildConfig.PRIVACY_POLICY_URL`.

---

### 📋 Google Play Data Safety form
- [ ] Complete the **Data Safety** section in Play Console → App Content
- [ ] Declare the following data types:
  | Category | Type | Collected | Shared | Encrypted | User can delete |
  |----------|------|-----------|--------|-----------|-----------------|
  | App activity | App interactions | ✅ | ❌ | ✅ (in transit) | ❌ |
  | App activity | In-app search history | ✅ | ❌ | ✅ (in transit) | ❌ |
  | App info & performance | Crash logs | ✅ | ❌ | ✅ (in transit) | ❌ |
  | App info & performance | Diagnostics | ✅ | ❌ | ✅ (in transit) | ❌ |
- [ ] Purpose: Analytics, App functionality

**Why blocking:** Play Console blocks publishing if Data Safety is incomplete.

---

### 🔧 Lint baseline — re-enable `abortOnError`
- [ ] In a full Android SDK environment, run:
  ```bash
  cd android
  ./gradlew lintDebug -Dlint.baselines.continue=true
  # If ERROR-severity issues still fail, run a second time:
  ./gradlew lintDebug -Dlint.baselines.continue=true
  ```
- [ ] Commit the updated `app/lint-baseline.xml`
- [ ] Set `abortOnError = true` in `app/build.gradle.kts` (lint block)
- [ ] Remove the TODO comment once done

**Why blocking:** With `abortOnError = false`, code quality regressions can silently ship.
Restoring enforcement before the first public release prevents technical debt from accumulating.

---

## P1 — High Priority (should be done before public release)

### 📋 Play Store listing content
- [ ] **Short description** (≤80 chars) — e.g.
  _"Ask the Bible a question. Get answers grounded in Scripture."_
- [ ] **Full description** (≤4000 chars) — include:
  - What the app does (AI-powered Bible chat)
  - 11 supported languages
  - Key features: verse discovery, church finder, offline-capable UI
  - Free, no ads, no sign-in required
- [ ] **Content rating questionnaire** — complete in Play Console → App Content
  - Expected rating: Everyone (no violent/mature content)
- [ ] **Target audience** — All ages (app has no age-restricted content)
- [ ] **Category** — Books & Reference (or Education)

---

### 🎨 Play Store listing assets
Current status: `play_store_assets/` contains icon and feature graphic.

- [x] Hi-res icon `ic_launcher_store_512.png` (512×512) ✅ Generated
- [x] Feature graphic `feature_graphic_1024x500.png` (1024×500) ✅ Generated
- [ ] **Phone screenshots** (minimum 2, up to 8) — see `play_store_assets/README.md`
  - `01_chat.png` — main chat screen with an AI response visible
  - `02_verses.png` — verses panel open showing related scriptures
  - `03_bible_reader.png` — chapter viewer with verse highlighted
  - `04_church_finder.png` — church finder bottom sheet with results
  - `05_settings.png` — settings screen (theme, language, About section)
  - Recommended size: 1080×1920 portrait

---

### 📋 App review — first submission review
- [ ] Complete **App Access** in Play Console if any feature requires login (N/A — app is fully
  anonymous, no login required)
- [ ] Add **reviewer notes** explaining Turnstile CAPTCHA (a WebView loads for bot protection on
  first launch — reviewers should tap "Verify" to proceed)

---

## P2 — Nice to Have (post-launch improvements)

### 🔧 In-App Review prompt (Google Play In-App Review API)
Prompt satisfied users to rate the app without leaving it.

**Suggested trigger:** After the user completes their 3rd conversation (check
`ConversationDao.getConversationCount()` in the ViewModel).

**Dependencies to add to `app/build.gradle.kts`:**
```kotlin
implementation("com.google.android.play:review-ktx:2.0.2")
```

**Implementation sketch:**
```kotlin
// In ChatViewModel, after a conversation completes:
val manager = ReviewManagerFactory.create(context)
manager.requestReviewFlow().addOnCompleteListener { task ->
    if (task.isSuccessful) {
        manager.launchReviewFlow(activity, task.result)
    }
}
```

---

### 🔧 In-App Updates (Google Play In-App Updates API)
Surface a non-intrusive banner when an app update is available.

**Dependencies:**
```kotlin
implementation("com.google.android.play:app-update-ktx:2.1.0")
```

**Recommended type:** `AppUpdateType.FLEXIBLE` (non-blocking, background download).
Check for updates in `MainActivity.onCreate()`.

---

### 🔧 Push notifications — devotional reminders
Daily/weekly optional reminders to open the app and read scripture.

**Required changes:**
- Add Firebase Cloud Messaging (FCM) to `build.gradle.kts`:
  ```kotlin
  implementation(libs.firebase.messaging)
  ```
- Request `POST_NOTIFICATIONS` permission at runtime (Android 13+, API 33)
- Add opt-in toggle to SettingsScreen
- Backend: new `/api/v1/notifications/register` endpoint to store FCM tokens
- Backend: scheduled job (cron) to send daily inspiration pushes

**Scope:** Medium-large — requires both Android and backend changes.

---

### 🔧 Deep Links / Android App Links
Allow shared Bible verse URLs to open directly in the app.

**Required changes:**
- Add `<intent-filter android:autoVerify="true">` in `AndroidManifest.xml` for
  `https://getinspiredbythebible.com/verse/*`
- Host `/.well-known/assetlinks.json` on the domain with the app's SHA-256 fingerprint
- Handle the incoming intent in `MainActivity` and navigate to the correct verse

---

### 🔧 Offline state UI
The `ACCESS_NETWORK_STATE` permission is declared. Wire up a proper "No internet" banner
instead of the current generic error message for `UnknownHostException`.

**File to update:** `ChatViewModel.kt` — add a `NoNetwork` error type to the error sealed class
and display it with a dedicated message in `ChatScreen.kt`.

---

## Quick Reference — CI / Release Build

```bash
# Build signed release AAB (requires keystore env vars)
cd android
./gradlew bundleRelease \
  -PbaseUrl=https://bible-app-backend.agreeablesea-6ee07535.northeurope.azurecontainerapps.io/

# Upload mapping to Crashlytics (run after bundleRelease)
./gradlew uploadCrashlyticsMappingFileRelease

# Run lint with baseline
./gradlew lintRelease
```

Required environment variables for CI signing:
```
KEYSTORE_BASE64         # base64 of release.jks
KEYSTORE_PASSWORD       # storePassword
KEY_ALIAS               # keyAlias
KEY_PASSWORD            # keyPassword
GOOGLE_SERVICES_JSON_BASE64  # base64 of google-services.json
```

---

## Already Completed (reference)

| Feature | Status | Notes |
|---------|--------|-------|
| Firebase Analytics (14 events) | ✅ | Enabled in release builds |
| Firebase Crashlytics | ✅ | Enabled in release builds |
| ProGuard / R8 minification | ✅ | Release build |
| Network security (no cleartext in release) | ✅ | `network_security_config.xml` |
| Session ID sent to backend for DAU/MAU | ✅ | `SessionPreferences.kt` |
| Multi-language (11 languages, RTL Arabic) | ✅ | |
| Dark / light / system theme | ✅ | |
| Native Android share sheet on messages | ✅ | `ShareCompat.IntentBuilder` |
| Verses panel (Referenced + All Related tabs) | ✅ | `VersesPanel.kt` |
| Scroll-to-bottom FAB | ✅ | `ChatScreen.kt` |
| Session limit detection + UX | ✅ | `isSessionLimitReached` |
| Settings: "Support" section (renamed from Debug) | ✅ | PR #— |
| Settings: About section with version + Privacy Policy link | ✅ | PR #— |
| Hi-res icon (512×512) | ✅ | `play_store_assets/ic_launcher_store_512.png` |
| Feature graphic (1024×500) | ✅ | `play_store_assets/feature_graphic_1024x500.png` |

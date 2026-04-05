# Android Play Store Onboarding

This guide covers the repo-specific steps to ship the Android app to the
official Google Play Store.

It is intentionally operational rather than aspirational: it documents what is
already in the repo, what is still missing, and the exact release flow to
follow.

## Current App State

- Android module path: `android/`
- Application ID: `com.bibleinspiration`
- Current version: `1.0.0` (`versionCode = 1`)
- Min SDK: 26
- Target SDK: 35
- Release artifact for Play: Android App Bundle (`.aab`)
- Release API base URL default: `https://api.getinspiredbythebible.com/`

Source of truth:

- `android/app/build.gradle.kts`
- `android/app/src/main/AndroidManifest.xml`
- `android/README.md`

## Release Blockers

These items are not optional for public launch.

### Required Before Submission

- Turnstile or equivalent bot protection must be working on Android. This is
  already tracked as a pending blocker in the product docs and should be
  treated as unresolved until verified on a release build.
- Privacy Policy must exist on a public URL.
- Terms of Service should exist on a public URL.
- Final app icon, feature graphic, and store screenshots must be prepared.
- Production signing keystore must be generated and stored securely outside the repo.
- The production backend must be stable and reachable from the app.

### Gaps Observed In This Repo

- Repo-hosted drafts now exist for Privacy Policy and Terms of Service.
- A working `android/store-assets/` folder now exists for Play listing assets.
- Public URLs for the legal documents still need to be published before release.
- Final exported screenshots and graphics still need to be created and uploaded.
- Retention periods and deletion-request handling still need final policy review
  before the public Privacy Policy is published.

## What The App Currently Declares

The manifest is minimal, which is good for Play review.

### Permissions

- `android.permission.INTERNET`
- `android.permission.ACCESS_NETWORK_STATE`

No dangerous runtime permissions were found.

### SDK / Tracking Surface

No obvious Android SDKs for ads, analytics, attribution, or crash reporting
were found in the Android Gradle dependencies at the time this document was
written.

That means the Play Console declarations should stay conservative unless the app changes before submission.

## Play Console Setup

Create the app in Google Play Console using the production package name:

- App name: Bible Inspiration
- Default language: English
- App type: App
- Free or paid: Free
- Package name: `com.bibleinspiration`

Use the same package name as the signed release build. If this changes later, Google Play will treat it as a different app.

## Store Assets Checklist

Prepare these before attempting submission:

- App name
- Short description
- Full description
- App icon: 512 x 512 PNG
- Feature graphic: 1024 x 500 PNG
- Phone screenshots for the main user flows
- Optional tablet screenshots if tablet support is claimed
- Support email
- Privacy Policy URL
- Terms of Service URL

Recommended screenshot set for this app:

- Welcome screen
- Chat conversation in English
- Verse references expanded
- Language support example
- Arabic or RTL layout example

## Legal And Policy Requirements

### Privacy Policy

You need a public Privacy Policy URL before production rollout.

The policy should describe at least:

- What user input is sent to the backend
- Whether chat content is stored, logged, or retained
- Whether IP addresses, device metadata, or session identifiers are processed
- Which third parties receive data, if any
- Contact method for privacy requests
- GDPR-related rights if serving EU users

### Terms Of Service

Terms are strongly recommended for a public AI app. They should cover:

- Acceptable use
- Service availability disclaimer
- Non-emergency / non-pastoral-care disclaimer if applicable
- Content accuracy limitations for AI-generated responses
- Contact and jurisdiction information

### App Content / Data Safety

Based on the current Android module, review these carefully in Play Console:

- Data collected: likely yes, because user chat prompts are sent to the backend for processing
- Data shared: confirm whether backend providers or infrastructure vendors receive user data
- Security practices: data in transit should be declared if HTTPS is used in production
- Delete request handling: declare only if you actually support it
- Retention: confirm exact retention periods before completing the form

Do not answer the Data safety form from memory. Validate it against the backend architecture and production telemetry.

Useful supporting docs in this repo:

- `docs/SECURITY.md`
- `docs/USAGE_TRACKING.md`
- `docs/ROADMAP.md`

## Versioning Rules

Before each Play upload:

- Increment `versionCode`
- Update `versionName` if the release is user-visible

Current location:

`android/app/build.gradle.kts`

Example:

```kotlin
defaultConfig {
    versionCode = 2
    versionName = "1.0.1"
}
```

Google Play rejects uploads that reuse an existing `versionCode`.

## Signing And Bundle Build

The Play Store artifact should be a signed release AAB.

Generate a keystore outside the repo:

```bash
keytool -genkey -v \
  -keystore ~/release.keystore \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias release
```

Export the signing variables:

```bash
export KEYSTORE_PATH=~/release.keystore
export KEYSTORE_PASSWORD=your-password
export KEY_PASSWORD=your-key-password
```

Build the Play artifact from the repo root using the documented Android module flow:

```bash
cd android
./gradlew bundleRelease
```

If needed, override the production API URL:

```bash
cd android
./gradlew bundleRelease -PbaseUrl="https://api.getinspiredbythebible.com/"
```

Expected output:

- `android/app/build/outputs/bundle/release/app-release.aab`

## Recommended Pre-Submission Verification

Run these checks before uploading:

```bash
make android-test
make android-lint
make android-build
```

Then verify the release flow manually on a real device:

- App launches cleanly
- Release build can reach `https://api.getinspiredbythebible.com/health`
- Chat requests succeed against production backend
- Verse references render correctly
- Supported locales are selectable or correctly resolved
- No cleartext-traffic issues
- No crashes on startup, send, stream, or rotate

If release-signing changes or resource shrinking affects runtime behavior,
test the signed release build specifically, not only debug.

## Internal Testing Flow

Do not start with production rollout.

Recommended path:

1. Create the app in Play Console.
2. Complete App content, Data safety, and Store listing sections.
3. Upload the signed AAB to `Internal testing`.
4. Add tester emails.
5. Validate install, update, networking, and locale behavior from the Play-distributed build.
6. Promote to `Closed testing` if needed.
7. Only then create the first `Production` release.

## Play Console Submission Checklist

### Account And Access

- Google Play Console account is active
- Organization details are correct
- Support email is configured

### App Setup

- Package name matches `com.bibleinspiration`
- Category is selected
- Contact details are filled in
- Privacy Policy URL is live

### App Content

- Data safety completed
- Ads declaration completed
- Content rating questionnaire completed
- Target audience completed
- News app declaration marked correctly

### Store Listing

- Short description added
- Full description added
- Screenshots uploaded
- Feature graphic uploaded
- App icon uploaded

### Release

- `versionCode` incremented
- Signed release AAB uploaded
- Release notes added
- Internal test validated

## Repo Files To Review During Release

- `android/app/build.gradle.kts`
- `android/app/src/main/AndroidManifest.xml`
- `android/README.md`
- `docs/BACKLOG.md`
- `docs/ROADMAP.md`
- `docs/SECURITY.md`
- `docs/USAGE_TRACKING.md`

## Suggested Next Artifacts To Add

These are the most useful follow-up docs/files if the team wants a repeatable release process:

- `docs/PRIVACY_POLICY.md`
- `docs/TERMS_OF_SERVICE.md`
- `android/store-assets/README.md`
- `android/store-assets/` with screenshots and listing copy
- GitHub Actions release workflow for signed AAB generation

Current repo drafts:

- `docs/PRIVACY_POLICY.md`
- `docs/TERMS_OF_SERVICE.md`
- `android/store-assets/README.md`
- `android/store-assets/listing-copy.md`
- `android/store-assets/release-notes-template.md`

## Release Decision

The Android app appears technically close to store onboarding, but it is not submission-ready yet.

The two most important non-code blockers are:

1. Android bot protection / Turnstile readiness
2. Public legal documents and Play listing assets

Once those are complete, the repo already has the basics needed to generate the
signed AAB for Play.

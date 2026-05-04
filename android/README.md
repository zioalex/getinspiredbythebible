# Vox Quieta — Android App

Native Android app for the [Vox Quieta](../README.md) platform.
Built with Kotlin, Jetpack Compose, and MVVM Clean Architecture.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| JDK | 17 | [Temurin](https://adoptium.net/) recommended |
| Android Studio | Hedgehog (2023.1.1+) | or Ladybug / Meerkat |
| Android SDK | API 35 (compile), API 24 (min) | installed via SDK Manager |
| Gradle | 8.9 | managed by the wrapper (`./gradlew`) |

> **No Android Studio?** You can build from the command line as long as you have
> JDK 17 and the Android SDK installed. Set `ANDROID_HOME` to your SDK path.

---

## Building locally

### 1. Open in Android Studio

```text
File → Open → select the `android/` directory (not the repo root)
```

Android Studio will sync Gradle automatically.

### 2. Run from the command line

All commands below assume you are in the `android/` directory:

```bash
cd android
```

Or use the Makefile targets from the **repo root**:

```bash
make android-test     # Unit tests only (fast, no device needed)
make android-build    # Debug APK
make android-lint     # Lint report
make android-clean    # Clean build artifacts
```

#### Common Gradle tasks

```bash
# Run unit tests (no emulator, no device)
./gradlew testDebugUnitTest

# Build a debug APK
./gradlew assembleDebug

# Install debug APK on a connected device / emulator
./gradlew installDebug

# Run lint
./gradlew lintDebug

# Build release APK (requires signing config — see below)
./gradlew assembleRelease

# Build release AAB (for Play Store)
./gradlew bundleRelease

# Clean
./gradlew clean
```

---

## Connecting to the backend

The app uses `BuildConfig.BASE_URL` to locate the API.

| Build type | Default `BASE_URL` | Notes |
|---|---|---|
| `debug` | `http://10.0.2.2:8000/` | `10.0.2.2` routes to `localhost` on Android emulator |
| `release` | `https://api.voxquieta.org/` | Override via `-PbaseUrl=...` or CI variable |

To point a debug build at a custom URL, pass it as a Gradle property:

```bash
./gradlew assembleDebug -PbaseUrl="https://staging.example.com/"
```

To run the backend locally for emulator testing:

```bash
# From repo root — starts the FastAPI backend on port 8000
make docker-up
# or
cd api && uvicorn main:app --reload
```

---

## Running on a device / emulator

1. Enable **Developer Options** on the device (tap Build Number 7× in Settings → About)
2. Enable **USB Debugging**
3. Connect via USB or start an emulator in Android Studio
4. Run:

```bash
./gradlew installDebug
adb shell am start -n org.voxquieta/.MainActivity
```

Or press the green ▶ button in Android Studio.

---

## Running tests

```bash
# Unit tests (pure JVM — fast, CI-safe)
./gradlew testDebugUnitTest

# Test report
open app/build/reports/tests/testDebugUnitTest/index.html
```

Test classes live under:

```text
android/app/src/test/kotlin/com/bibleinspiration/
├── viewmodels/ChatViewModelTest.kt   # 7 tests
└── repositories/ChatMapperTest.kt    # 4 tests
```

---

## Firebase setup

The app uses Firebase Analytics and Crashlytics in release builds. Firebase is
**disabled in debug builds** via `BuildConfig.FIREBASE_ENABLED`, so you can
develop and run tests without any Firebase configuration.

For release builds a real `google-services.json` is required. The file is
gitignored — it must be provisioned separately for both local builds and CI.

### One-time Firebase project setup

1. Go to [console.firebase.google.com](https://console.firebase.google.com).
2. Create a project (or use an existing one).
3. Add an **Android app** with package name `org.voxquieta`.
4. Download `google-services.json` and place it at `android/app/google-services.json`.
5. Register the release signing certificate's SHA-256 fingerprint in the Firebase
   app settings (needed for App Check / Dynamic Links if used later):

   ```bash
   keytool -list -v -keystore ~/path/to/release-key.jks -alias my-key-alias
   ```

   Copy the `SHA-256` line and paste it into **Firebase → Project settings →
   Your apps → Android app → Add fingerprint**.

### Local builds

Place the real `google-services.json` at `android/app/google-services.json`.
The file is listed in `.gitignore` — never commit it.

If you only have the base64-encoded version (e.g. from the CI secret):

```bash
base64 -d ~/path/to/google-services.json.b64 > android/app/google-services.json
```

Verify the file contains `"package_name": "org.voxquieta"` (not `org.voxquieta.app`).

### CI secret

The workflow decodes `GOOGLE_SERVICES_JSON` (a base64-encoded GitHub Actions
secret) into `android/app/google-services.json` before the build step.

To generate or update the secret:

```bash
base64 -w 0 android/app/google-services.json
```

Paste the output as the `GOOGLE_SERVICES_JSON` secret under
**Settings → Secrets and variables → Actions** in the repository.

---

## Signing a release build

1. Generate a keystore (keep it **outside** the repo):

```bash
keytool -genkey -v \
  -keystore ~/release.keystore \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias release
```

1. Set environment variables (or pass as Gradle properties):

```bash
export KEYSTORE_PATH=~/release.keystore
export KEYSTORE_PASSWORD=your-password
export KEY_PASSWORD=your-key-password
```

1. Build:

```bash
./gradlew assembleRelease
# or for Play Store
./gradlew bundleRelease
```

> CI uses GitHub Actions secrets — see `.github/workflows/android-ci.yml`.

---

## Releasing

`versionCode` and `versionName` are not hard-coded — they are injected as Gradle
properties so CI can set them without touching source files.  The defaults
(`versionCode = 1`, `versionName = "1.0.0"`) are only used for local debug builds.

To build a production AAB for Play Store submission, pass both properties:

```bash
# From the android/ directory
./gradlew bundleRelease -PversionCode=42 -PversionName=2.1.0
```

The resulting AAB is at `app/build/outputs/bundle/release/app-release.aab`.

---

## Publishing to the Play Store

Publishing is fully automated via GitHub Actions
(`.github/workflows/android-publish.yml`) and Fastlane.

> **Before the automated workflow can run**, you must complete the one-time
> Play Console setup described below. Fastlane can only upload builds to an
> _existing_ app — it cannot create one.

### One-time Play Console setup

These steps must be done once by a human with a Google Play developer account.

#### 1. Create the app in Play Console

1. Go to [play.google.com/console](https://play.google.com/console) and sign
   in with the developer account.
2. Click **Create app**.
3. Fill in the required fields: app name, default language, app/game type,
   free/paid status.
4. Accept the content guidelines and US export laws declarations.
5. Click **Create app**.

#### 2. Complete the Store listing

Most metadata is already prepared under
`android/fastlane/metadata/android/en-US/` and will be uploaded automatically
by Fastlane. However, Play Console requires you to fill in at least the
following before a build can be published:

- Short description and full description
- App icon (512×512 PNG)
- Feature graphic (1024×500 PNG)
- At least two phone screenshots
- Privacy policy URL

These assets are in `android/fastlane/metadata/android/en-US/images/`.

#### 3. Complete mandatory app content declarations

In Play Console, under **Policy → App content**, complete:

- **Privacy policy** — provide a URL to your privacy policy
- **Content rating** — complete the IARC questionnaire
- **Target audience** — specify target age group
- **News apps** — confirm whether the app is a news app

#### 4. Set up a Google Play service account for Fastlane

This allows Fastlane (and the CI workflow) to upload builds via the API.

1. In Play Console, go to **Setup → API access**.
2. Link your Play Console to a Google Cloud project (create one if needed).
   Note the **GCP project number** shown — you'll need it in step 4.
3. Click **Create new service account** → follow the link to Google Cloud
   Console.
4. **Enable the Google Play Android Developer API** in your GCP project. The API is _not_ enabled by default; without this, every Fastlane upload fails with `PERMISSION_DENIED: Google Play Android Developer API has not been used in project <NUMBER> before or it is disabled`. Enable it at:

   ```text
   https://console.developers.google.com/apis/api/androidpublisher.googleapis.com/overview?project=<YOUR_PROJECT_NUMBER>
   ```

   Or: GCP Console → **APIs & Services → Library →** search "Google Play Android Developer API" → **Enable**. Allow ~2–5 minutes for the change to propagate.
5. In Google Cloud Console:
   - Create a service account (e.g. `fastlane-deploy`)
   - Grant it no Cloud IAM roles (permissions are managed in Play Console)
   - Create a JSON key and download it
6. **Back in Play Console**, click **Grant access** next to the new service account.
7. Assign the **Admin (all permissions)** role for the first-time setup, or at minimum a custom role that includes:
   - **Releases:** *Create, edit and delete draft releases*
   - **Releases:** *Release apps to testing tracks*
   - **Releases:** _Release to production, exclude devices and use Play App Signing_ (only if you'll promote to production)
   - **Store presence:** _Edit store listing, pricing & distribution_ (only if Fastlane will sync metadata/screenshots)

   Without this grant, Fastlane fails with `Google Api Error: Invalid request - The caller does not have permission` even though the API is enabled and the JSON key is valid. Allow ~5 minutes for the new permissions to propagate.
8. Base64-encode the JSON key and store it as the `GOOGLE_PLAY_JSON_KEY`
   GitHub secret:

```bash
base64 -w 0 play-key.json
```

#### 5. Upload the first build manually

Google Play requires at least one build to be uploaded manually via the Play
Console UI before the API (and therefore Fastlane) can be used.

1. Build a signed AAB locally (see [Signing a release build](#signing-a-release-build)).
2. In Play Console, go to **Testing → Internal testing → Create new release**.
3. Upload the `.aab` file, add release notes, and save the release.

After this first manual upload, all subsequent releases can be fully automated
by pushing a `vX.Y.Z` tag.

#### Troubleshooting Fastlane upload errors

| Error message | Cause | Fix |
|---|---|---|
| `Could not find aab file at path 'app/build/outputs/bundle/release/app-release.aab'` | Gradle `bundleRelease` step didn't produce the AAB, or the workflow's `working-directory` is not `android/`. | Check the **Build signed AAB** step's logs. The path in `android/fastlane/Fastfile` is module-root-relative; the workflow must invoke `fastlane` from `android/`. |
| `PERMISSION_DENIED: Google Play Android Developer API has not been used in project <N> before or it is disabled` | The API is not enabled on the GCP project that owns the service account. | Step 4 above — enable the API at the URL printed in the error and wait ~5 min. |
| `Invalid request - The caller does not have permission` | The service account exists and the API is enabled, but the SA was not granted access (or insufficient permissions) in Play Console. | Step 6–7 above — grant access in **Setup → API access → Grant access**, with the **Admin** role or at minimum the _Release manager_ permissions. Wait ~5 min for propagation. |
| `Package <id> not found` | The applicationId in `build.gradle.kts` doesn't match a created app in Play Console, or step 5 (first manual upload) was skipped. | Check the app exists in Play Console with the exact same package name as `applicationId`. Upload one build manually first. |
| `Only releases with status draft may be created on draft app` | The app in Play Console has not yet been activated (no production release ever rolled out), so Play Store rejects any release whose `release_status` is not `draft`. | Handled — the `internal` lane in `android/fastlane/Fastfile` passes `release_status: "draft"` so uploads work while the app is still in its initial draft state. Once the app is activated in Play Console (after the first production rollout), this can be relaxed to `completed` if you want internal-track builds to auto-promote to internal testers without a manual click. |
| `Version code N has already been used` | Each AAB uploaded to Play Console must have a strictly greater `versionCode` than every previously uploaded one (across all tracks). | The workflow derives `versionCode` from a Unix-epoch timestamp captured at build time (`$(date +%s)`), so every run gets a strictly greater code than any previous run — including re-runs. To force a specific code (e.g. to match an external numbering scheme), pass `version_code` as a `workflow_dispatch` input. `versionName` remains human-readable (from tag, input, or `build.gradle.kts`). |

---

### Required GitHub secrets

These must be set under **Settings → Secrets and variables → Actions** in the
repository before the workflow can run:

| Secret | Description |
|---|---|
| `KEYSTORE_FILE` | Base64-encoded release keystore: `base64 -w 0 release.keystore` |
| `KEYSTORE_PASSWORD` | Password for the keystore |
| `KEY_ALIAS` | Key alias inside the keystore (e.g. `release`) |
| `KEY_PASSWORD` | Password for the key |
| `GOOGLE_PLAY_JSON_KEY` | Base64-encoded Google Play service account JSON: `base64 -w 0 play-key.json` |

> The Google Play service account needs the **Release manager** role (or at minimum
> the **Releases** permission) in Google Play Console.

### Track promotion flow

```
internal  →  beta  →  production
```

- **internal**: new AAB is uploaded and assigned to internal testers
- **beta** / **production**: the existing internal build is _promoted_ — no new
  AAB is built or uploaded

### Step 1 — Upload a new build to internal testing

Push a tag following the `vX.Y.Z` format. The workflow triggers automatically:

```bash
git tag v1.2.3
git push origin v1.2.3
```

The workflow will:

1. Build a signed AAB
2. Set `versionName=1.2.3` and `versionCode=10203` (computed as
   `MAJOR×10000 + MINOR×100 + PATCH`)
3. Upload the AAB to the **internal** track on Google Play

### Step 2 — Promote to closed beta

Once the internal build has been reviewed and approved, go to
GitHub → Actions → Android Publish → Run workflow.

Select track: `beta`, then click _Run workflow_.

Fastlane will promote the current internal build to the **beta** (closed
testing) track without re-uploading the AAB.

### Step 3 — Promote to production

When the beta build is ready for general availability, go to
GitHub → Actions → Android Publish → Run workflow.

Select track: `production`, then click _Run workflow_.

Fastlane promotes the beta build to production with an initial 10% rollout
(`rollout: "0.1"`). Full rollout can be managed from the Google Play Console.

---

## Project structure

```text
android/
├── app/
│   └── src/
│       ├── main/kotlin/com/bibleinspiration/
│       │   ├── VoxQuietaApp.kt    # @HiltAndroidApp
│       │   ├── MainActivity.kt
│       │   ├── data/
│       │   │   ├── remote/               # Retrofit + OkHttp + DTOs + mappers
│       │   │   ├── repositories/         # Repository implementations
│       │   │   └── streaming/            # SSE → Flow parser
│       │   ├── di/                       # Hilt modules
│       │   ├── domain/
│       │   │   ├── models/               # Message, Verse, ChatRequest, …
│       │   │   └── repositories/         # Repository interfaces
│       │   ├── presentation/
│       │   │   ├── components/           # Compose UI components
│       │   │   ├── screens/              # ChatScreen
│       │   │   ├── theme/                # Material 3 theme
│       │   │   └── viewmodels/           # ChatViewModel
│       │   └── utils/                    # LocaleHelper (RTL support)
│       ├── test/                         # Unit tests (JVM)
│       └── main/res/                     # Layouts, strings (7 locales)
├── gradle/
│   ├── libs.versions.toml               # Version catalog
│   └── wrapper/gradle-wrapper.properties
├── gradlew                              # Gradle wrapper (POSIX)
└── settings.gradle.kts
```

---

## CI / CD

The GitHub Actions workflow at `.github/workflows/android-ci.yml` runs on every
PR and push to `main` that touches `android/**`:

| Job | Runs | Artifact |
|-----|------|----------|
| `unit-tests` | Always | HTML test report (7 days) |
| `lint` | Always | `lint-results-debug.html` (7 days) |
| `build` | After tests + lint pass | `app-debug.apk` (14 days) |

No emulator is needed — unit tests run on the JVM.

# Bible Inspiration — Android App

Native Android app for the [Bible Inspiration Chat](../README.md) platform.
Built with Kotlin, Jetpack Compose, and MVVM Clean Architecture.

For Google Play submission and official store onboarding, see [docs/ANDROID_PLAY_STORE_ONBOARDING.md](../docs/ANDROID_PLAY_STORE_ONBOARDING.md).

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
| `release` | `https://api.getinspiredbythebible.com/` | Override via `-PbaseUrl=...` |

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
adb shell am start -n com.bibleinspiration/.MainActivity
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

## Project structure

```text
android/
├── app/
│   └── src/
│       ├── main/kotlin/com/bibleinspiration/
│       │   ├── BibleInspirationApp.kt    # @HiltAndroidApp
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

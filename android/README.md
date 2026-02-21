# Get Inspired by the Bible — Android App

A native Android app that lets users have a conversational AI chat grounded in Bible scripture.
Built with Jetpack Compose, Hilt, Retrofit, and Kotlin Coroutines.

## Architecture

```text
MVVM + Clean Architecture
├── data/
│   ├── model/           — Moshi-annotated data classes (API shapes)
│   ├── remote/          — Retrofit interface (BibleApiService)
│   └── repository/      — ChatRepository interface + ChatRepositoryImpl
├── di/
│   ├── NetworkModule    — OkHttp, Retrofit, BibleApiService bindings
│   └── RepositoryModule — ChatRepository → ChatRepositoryImpl binding
├── ui/
│   ├── chat/
│   │   ├── ChatViewModel   — UiState, user events, coroutine launch
│   │   ├── ChatScreen      — Root Composable
│   │   └── components/     — MessageBubble, VerseCard
│   └── theme/              — Material 3 color/type/theme (gold + navy)
├── BibleApp.kt             — @HiltAndroidApp Application
└── MainActivity.kt         — @AndroidEntryPoint, sets Compose content
```

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Android Studio | Hedgehog (2023.1.1) or later |
| JDK | 17 |
| Android SDK | API 35 (compile), API 26 (min) |
| Gradle | 8.9 (via wrapper) |

## First-Time Setup (Bootstrapping the Gradle Wrapper)

The `gradle-wrapper.jar` binary is intentionally not committed to version control.
You must generate it once before building:

```bash
# From the android/ directory
cd android

# Option A — if you have Gradle installed globally (8.x):
gradle wrapper --gradle-version 8.9

# Option B — use the Android Studio bundled Gradle:
#   Open the android/ folder in Android Studio.
#   It will prompt you to "Configure Gradle Wrapper" and generate the jar automatically.
```

After this step you will see `android/gradle/wrapper/gradle-wrapper.jar` appear.

## Building

```bash
# From the repo root — using Makefile targets (preferred):
make android-build        # assembles debug APK
make android-test         # runs JVM unit tests
make android-lint         # runs Android lint

# From the android/ directory directly:
./gradlew assembleDebug
./gradlew test
./gradlew lint
```

## Local Development

The app talks to the FastAPI backend. When running on the Android emulator, `10.0.2.2`
routes to your development machine's `localhost`.

1. Start the backend: `make docker-up` (from repo root)
2. The default `BuildConfig.BASE_URL` in debug builds is `http://10.0.2.2:8000/` — no config needed.
3. To point at a real device or different host, pass the property:

   ```bash
   ./gradlew assembleDebug -PBASE_URL="http://192.168.1.100:8000/"
   ```

## Running Tests

```bash
# JVM unit tests (no device needed)
./gradlew test

# Instrumented tests (requires connected device / emulator)
./gradlew connectedAndroidTest
```

## Configuration

Copy `local.properties.example` to `local.properties` and set your SDK path:

```properties
sdk.dir=/Users/yourname/Library/Android/sdk
```

`local.properties` is excluded from version control.

## Dependencies (key)

| Library | Purpose |
|---------|---------|
| Jetpack Compose BOM 2024.11.00 | UI toolkit |
| Material 3 | Design system |
| Hilt 2.52 | Dependency injection |
| Retrofit 2.11.0 | HTTP client |
| OkHttp 4.12.0 | HTTP engine + logging |
| Moshi 1.15.1 | JSON serialization |
| Kotlin Coroutines 1.9.0 | Async/flow |
| MockK 1.13.13 | Unit test mocking |
| Turbine 1.2.0 | Flow testing |

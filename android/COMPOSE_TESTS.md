# Android Compose UI Tests

> BITB-034 — Robolectric-backed Compose UI test tier

## Overview

The Android test suite has three tiers:

| Tier | Runner | What it covers | When to use |
|---|---|---|---|
| **JVM unit tests** (`*Test.kt`) | JVM / JUnit 4 | Pure logic — ViewModels, repositories, utility functions, pure helpers | Fast feedback on business logic |
| **Compose UI tests** (`*ComposeTest.kt`) | Robolectric + `createComposeRule()` | Composable rendering, default state, segment control selection, `rememberSaveable` survival | Catching Compose-layer regressions without an emulator |
| **Instrumented tests** (`androidTest/`) | Android emulator (API 29) | Happy-path E2E flows (chat, navigation) | Full-stack validation before release |

## Quick Start

```bash
# Run only Compose UI tests (Robolectric tier)
make android-test-compose

# Or directly with Gradle
cd android && ./gradlew testDebugCompose --no-daemon

# Run the standard JVM unit tests (unchanged)
make android-test
```

HTML report after a run: `android/app/build/reports/tests/testDebugCompose/index.html`

## Filename Convention

| Filename pattern | Runs in | Description |
|---|---|---|
| `*Test.kt` | `testDebugUnitTest` | Existing JVM unit tests — pure logic, no Android/Compose runtime |
| `*ComposeTest.kt` | `testDebugCompose` | Robolectric Compose UI tests — mounts composables and asserts semantics |

Both live under `android/app/src/test/kotlin/`. The Gradle `testDebugUnitTest` task explicitly
excludes `**/*ComposeTest.class`; `testDebugCompose` includes only `**/*ComposeTest.class`.

## Writing a New Compose Test

1. Create a file matching `*ComposeTest.kt` anywhere under `src/test/kotlin/`.
2. Extend `ComposeTestHarness` (from `org.voxquieta.app.testing`).
3. Mount content with `setContentThemed { YourComposable(...) }`.
4. Use `composeRule.onNodeWithText(...)`, `assertIsDisplayed()`, `performClick()`, etc.

```kotlin
class MyScreenComposeTest : ComposeTestHarness() {

    @Test
    fun `button is enabled when data is loaded`() {
        setContentThemed {
            MyScreen(isLoading = false, onAction = {})
        }
        composeRule.onNodeWithText("Submit").assertIsEnabled()
    }
}
```

Reference: `VersesPanelComposeTest.kt` is the canonical template.

## Known Limitations

- **`ModalBottomSheet`, `Dialog`, `Popup`** have known rendering quirks under Robolectric
  (window insets, animation clocks). Test the *content* composable directly instead of the
  sheet wrapper. See how `VersesPanelContent` is used instead of `VersesPanel`.
- **API level**: Robolectric 4.14.1 pins to API 34 via `@Config(sdk = [34])`.
  Behaviors that only appear on API 35 must be covered by instrumented tests.
- **Hilt is intentionally excluded**: the harness uses `android.app.Application` as the
  Robolectric application class. Future screen-level tests that need injected ViewModels
  will require a Hilt-wired application — defer until the second screen-level test is added.

## CI

The `android-compose-tests.yml` workflow runs in parallel with `android-ci.yml`:

- Triggered on PRs and pushes that touch `android/**`.
- Reports as its own check: `Compose UI Tests (Robolectric)`.
- Uses `continue-on-error: true` and is **NOT a required check** for merges while the
  tier stabilises. Once green consistently, promote it to required via branch-protection
  settings and remove `continue-on-error`.

## Suggested Future Targets

Once the tier has been green for several PR runs, add tests in this order:

1. `ChatInputFieldComposeTest` — send-button enabled/disabled state, Stop icon while loading.
2. `ChatScreenComposeTest` — top-bar policy, language picker visibility.
3. `TranslationPickerBottomSheetComposeTest` — selection and dismissal.
4. `VerseDetailBottomSheetComposeTest` — verse display and close.
5. `ConversationsScreenComposeTest` — empty and populated list states.

When the tier has multiple stable tests, file the integration follow-up story to promote it
to a required check and optionally merge it into `android-ci.yml`.

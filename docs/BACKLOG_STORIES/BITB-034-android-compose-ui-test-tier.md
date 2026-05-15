# BITB-034: Android — Add Robolectric/Compose UI Test Tier (Local-Only)

**Priority:** P2 (Medium — closes a regression gap exposed by #551, not user-blocking)
**Status:** 📋 Ready
**Size:** M (4-6 hours)
**Created:** 2026-05-14

---

## User Story

As an Android contributor, I want a Robolectric-backed Compose UI test tier
so I can write tests that actually render composables — catching default-state,
`rememberSaveable`, semantics, and layout regressions that pure JVM unit tests
cannot see. The new tier should run locally via `make` and stay out of CI
until the harness has been fine-tuned.

## Background

PR #551 fixed a one-line bug on Android: the verse panel opened with the "All"
filter selected because `mutableStateOf(false)` should have been
`mutableStateOf(true)` (`VersesPanel.kt:159`). The existing test suite did not
catch it: `VersesPanelTest.kt` only exercises the pure helper
`referencedVerses(...)` and never renders the composable. The whole Compose
layer is currently untested.

This story raises the Android test floor with two cheap defenses:

1. **Constant-default trick** — extract the `true` default into a named
   constant covered by a plain JVM unit test. Locks the specific regression
   at near-zero cost; runs in CI immediately.
2. **Robolectric + Compose UI test tier** — the infrastructure for
   composable rendering tests (segmented-control selection, `rememberSaveable`
   survival, semantics, RTL/dark theming). One first test ships as the
   reference pattern; further targets are documented but not implemented.

**Explicit non-goal:** the new tier is **not** wired into CI. We want to run
it locally first via the Makefile, fine-tune harness ergonomics, observe
flakiness, then flip CI on in a follow-up. The build is configured so the
existing `testDebugUnitTest` CI job does not know the Compose tests exist.

**Out of scope:** instrumented (emulator) test expansion, frontend changes,
modifications to `.github/workflows/android-ci.yml`.

---

## Step 1 — Constant-default defense

**File:** `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt`

- Add `internal const val DEFAULT_SHOW_REFERENCED = true` (top-level or
  companion-style holder).
- Replace line 159:
  `var showReferenced by rememberSaveable { mutableStateOf(DEFAULT_SHOW_REFERENCED) }`.

**File:** `android/app/src/test/kotlin/org/voxquieta/app/components/VersesPanelTest.kt`

- Add one `@Test` asserting `DEFAULT_SHOW_REFERENCED == true`. Runs in the
  existing JVM unit-test job, locks #551 without needing the Compose runtime.

---

## Step 2 — Add Robolectric + Compose UI test dependencies

**File:** `android/gradle/libs.versions.toml`

- `robolectric = "4.14.1"` (compatible with AGP 8.4.2 / Kotlin 2.0.21 /
  Compose BOM 2024.12.01)
- `[libraries] robolectric = { module = "org.robolectric:robolectric", version.ref = "robolectric" }`
- `androidx-ui-test-junit4` already exists in the catalog (used by
  androidTest) — reuse the same alias.
- Add `androidx-ui-test-manifest` if not already present.

**File:** `android/app/build.gradle.kts`

- In `android { testOptions { unitTests { ... } } }` set
  `isIncludeAndroidResources = true` (required for `stringResource(...)` to
  resolve under Robolectric). Keep the existing `isReturnDefaultValues = true`.

---

## Step 3 — Isolate the Compose suite via a dedicated source set

The cleanest standard AGP idiom is a separate test source set with its own
dependency configuration and its own Gradle task. Nothing in
`testDebugUnitTest` changes — no exclude patterns, no shared classpath, no
risk of the Compose suite leaking into CI.

**Source layout:**

```
android/app/src/composeTest/
  kotlin/org/voxquieta/app/...
  AndroidManifest.xml   (if needed by ui-test-manifest)
```

**File:** `android/app/build.gradle.kts`

```kotlin
android {
    sourceSets {
        getByName("test") {
            // unchanged — keeps src/test/ as the JVM-only tier
        }
        create("composeTest") {
            kotlin.srcDir("src/composeTest/kotlin")
            java.srcDir("src/composeTest/kotlin")
            resources.srcDir("src/composeTest/resources")
        }
    }
}

configurations {
    val composeTestImplementation by creating {
        extendsFrom(configurations.getByName("testImplementation"))
    }
}

dependencies {
    "composeTestImplementation"(libs.robolectric)
    "composeTestImplementation"(libs.androidx.ui.test.junit4)
    "composeTestImplementation"(libs.androidx.ui.test.manifest)
    // MockK / coroutines-test inherited via extendsFrom above.
}

tasks.register<Test>("testDebugCompose") {
    description = "Runs Robolectric/Compose UI tests in src/composeTest/. Local-only; not wired to CI yet."
    group = "verification"

    val composeTestSourceSet = android.sourceSets.getByName("composeTest")
    val unitTest = tasks.named<Test>("testDebugUnitTest").get()

    classpath = files(
        composeTestSourceSet.kotlin.classesDirectory,
        configurations.getByName("composeTestImplementation"),
        unitTest.classpath,
    )
    testClassesDirs = files(composeTestSourceSet.kotlin.classesDirectory)
    useJUnit()
    dependsOn("compileDebugUnitTestKotlin")
}
```

Exact Gradle wiring may need small adjustments — the principle is: separate
source set + separate configuration + dedicated task. `testDebugUnitTest` is
left untouched.

---

## Step 4 — Compose test harness helper

**New file:** `android/app/src/composeTest/kotlin/org/voxquieta/app/testing/ComposeTestHarness.kt`

- Wraps `createComposeRule()` and exposes `setAppContent { ... }` which
  auto-applies `AppTheme` from `presentation/theme/Theme.kt`. Avoids
  repeating the theme wrapper in every test.
- Tiny fixture builders (`fakeVerse(...)`, `fakeAssistantMessage(...)`)
  reusing the style from `VersesPanelTest.kt:13-28`.
- Default Robolectric config documented at the top:
  `@RunWith(AndroidJUnit4::class)` + `@Config(sdk = [34])` (Robolectric 4.14
  supports up to API 34; project's compileSdk=35).

`VersesPanel` takes its data as composable parameters and does not use
Hilt-injected types, so the first test does **not** need `HiltTestApplication`.
Future screen-level tests that depend on view-models will need a Hilt-wired
Robolectric Application — defer that until the second screen-level test lands.

---

## Step 5 — First Compose UI test: VersesPanel

**New file:** `android/app/src/composeTest/kotlin/org/voxquieta/app/components/VersesPanelComposeTest.kt`

Tests:

1. `panel opens with Cited segment selected by default` — renders
   `VersesPanel(...)` with two verses (one cited); asserts the "Cited" node
   has `assertIsSelected()` and "All Related" has `assertIsNotSelected()`.
2. `displayed verses default to the cited subset` — only the cited verse's
   reference is shown (`assertExists()` / `assertDoesNotExist()`).
3. `clicking All Related shows every verse` — performs click on the second
   segment, re-asserts list contents.
4. `selection survives recomposition` — `StateRestorationTester` confirms
   `rememberSaveable` works after process-death simulation.

These four tests are the canonical pattern for future screen tests.

---

## Step 6 — Makefile target

**File:** `Makefile`

Add next to the existing `android-test` target:

```make
android-test-compose: ## Run Android Compose/Robolectric UI tests (local only, not in CI)
	@echo "$(BLUE)Running Android Compose UI tests...$(NC)"
	@cd android && ./gradlew testDebugCompose --no-daemon
	@echo "$(GREEN)✓ Android Compose UI tests complete$(NC)"
	@echo "$(YELLOW)Report: android/app/build/reports/tests/testDebugCompose/index.html$(NC)"
```

Append `android-test-compose` to the `.PHONY` line at the top. Do **not**
include it in any `test`/`test-all` aggregate target — the suite is
intentionally local-only for now.

---

## Step 7 — Documentation

**New file:** `android/COMPOSE_TESTS.md`

- **Purpose.** Three tiers explained: pure JVM (fast, stateless logic —
  existing); Robolectric/Compose (composable behavior, semantics, state
  survival — new); instrumented (emulator — existing, reserve for happy-path
  E2E).
- **How to run locally.** `make android-test-compose` (or
  `cd android && ./gradlew testDebugCompose`). Note: this does **not** run
  on CI yet.
- **Layout.** Compose tests live under `android/app/src/composeTest/`,
  separate from the regular `src/test/` JVM tier.
- **Harness usage.** Pointer to `ComposeTestHarness.kt`.
- **Future targets** (suggested order, not implemented in this story):
  1. `ChatScreenComposeTest` — top-bar policy, language picker visibility,
     message rendering.
  2. `ChatInputFieldComposeTest` — send-button enabled state, character
     limit indicator.
  3. `TranslationPickerBottomSheetComposeTest` — selection and dismissal.
  4. `VerseDetailBottomSheetComposeTest` — verse display + dismiss.
  5. `ConversationsScreenComposeTest` — empty/populated list states.
- **CI flip-on checklist** (follow-up story): add
  `./gradlew :app:testDebugCompose` step to
  `.github/workflows/android-ci.yml`; verify duration; tune `shardCount` if
  needed.

**File:** `AGENTS.md` — extend the existing Android section.

- Under `## Project layout` → `android/`: add
  `app/src/composeTest/  Robolectric + Compose UI tests (local-only)` after
  the existing `app/src/test/` entry.
- Under `## Testing` → `### Android Tests`: append a third code block:

  ```
  # Compose UI tests (Robolectric — local only, not in CI yet)
  make android-test-compose
  ```

  Plus a sentence: *Compose UI tests live in
  `android/app/src/composeTest/` and use Robolectric to render composables
  on the JVM. They are deliberately not wired into CI yet — see
  `android/COMPOSE_TESTS.md` for the rollout plan.*
- Under `## CI` → `### Android CI`: leave the table unchanged and add a
  one-line note that `testDebugCompose` is intentionally not part of
  `android-ci.yml` yet.

---

## Critical files

| Path | Action |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt` | Extract default constant |
| `android/app/src/test/kotlin/org/voxquieta/app/components/VersesPanelTest.kt` | Add constant assertion |
| `android/gradle/libs.versions.toml` | Add `robolectric` version + library |
| `android/app/build.gradle.kts` | `isIncludeAndroidResources = true`; new `composeTest` source set + configuration; register `testDebugCompose` task |
| `android/app/src/composeTest/kotlin/org/voxquieta/app/testing/ComposeTestHarness.kt` (new) | Harness helper |
| `android/app/src/composeTest/kotlin/org/voxquieta/app/components/VersesPanelComposeTest.kt` (new) | First UI test |
| `android/COMPOSE_TESTS.md` (new) | Documentation |
| `Makefile` | Add `android-test-compose` target |
| `AGENTS.md` | Document the new suite under project layout, testing, CI |
| `.github/workflows/android-ci.yml` | **Do not modify.** Intentionally untouched. |

## Existing utilities to reuse

- Fixture builder pattern from `VersesPanelTest.kt:13-28` (`assistantMsg`,
  `userMsg`, `verse`).
- Theme wrapper: `presentation/theme/Theme.kt` (apply via harness).
- MockK is already on the test classpath (inherited from `testImplementation`
  via `extendsFrom`) for any future Compose test that needs to stub a callback.

## Verification / acceptance

1. `make android-test` (or `./gradlew testDebugUnitTest`) → passes, **no**
   `VersesPanelComposeTest` in the report. Confirms CI isolation.
2. `make android-test-compose` (or `./gradlew testDebugCompose`) → passes,
   runs only the four Compose tests. Confirms harness works.
3. Temporary regression check: flip the default back to `false` → both the
   JVM constant test and the Compose default-state test fail. Revert.
4. On the PR branch in CI: only `testDebugUnitTest` runs the new constant
   assertion; the Compose suite is silent and the workflow file is unchanged.
5. Open the HTML report at
   `android/app/build/reports/tests/testDebugCompose/` to confirm test
   discovery and timings — these inform the CI flip-on decision in the
   follow-up.

## Rollout decision after this story

Once the local Compose suite has run a few times without flakes and the
harness ergonomics feel right, a follow-up story wires `testDebugCompose`
into `android-ci.yml` and starts ticking through the future-targets list.

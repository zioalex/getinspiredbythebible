# BITB-034: Android — Add Robolectric/Compose UI Test Tier

**Priority:** P2 (Medium — closes a regression gap exposed by #551, not user-blocking)
**Status:** ✅ Done (android-compose-tests.yml workflow active + androidTest/ files present including MainActivityTest and HiltTestRunner; verified 2026-05-24)
**Size:** M (4-6 hours)
**Created:** 2026-05-14
**Updated:** 2026-05-15

---

## User Story

As an Android contributor, I want a Robolectric-backed Compose UI test tier
so I can write tests that actually render composables — catching default-state,
`rememberSaveable`, semantics, and layout regressions that pure JVM unit tests
cannot see. The new tier runs locally via `make` AND in a dedicated,
independent CI job that does not gate merges while it is being stabilized.
Once it has been green for several runs in a row, it will be folded into
the standard Android test workflow.

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
   at near-zero cost; runs in CI immediately via the existing
   `testDebugUnitTest` job.
2. **Robolectric + Compose UI test tier** — the infrastructure for
   composable rendering tests (segmented-control selection, `rememberSaveable`
   survival, semantics, RTL/dark theming). One first test ships as the
   reference pattern; further targets are documented but not implemented.

**Isolation principle:** the new tier must not block, slow down, or alter the
behavior of the existing `testDebugUnitTest` CI job, nor of any other build
target (`assembleDebug`, `lint`, `check`). It is delivered as:

- A **separate Gradle task** (`testDebugCompose`) with its own filename
  convention and explicit excludes from `testDebugUnitTest`.
- A **separate GitHub Actions workflow** (`android-compose-tests.yml`)
  that runs in parallel with the existing `android-ci.yml`, reports its
  own check, and is configured as **not required** for merge.

**Out of scope:** instrumented (emulator) test expansion, frontend changes,
modifying `.github/workflows/android-ci.yml`, making the new check required
for merge (that is the integration follow-up).

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

> ⚠️ **Caveat:** `isIncludeAndroidResources` is module-wide — it affects
> `testDebugUnitTest` too. Existing JVM tests that previously got default
> values for any resource lookup will now resolve real strings. Before
> declaring this story done, run `./gradlew testDebugUnitTest` and confirm
> zero regressions. If any existing test breaks, fix it (the new behavior
> is the correct one) rather than reverting the flag.
>
> 📌 **Risk note:** Robolectric 4.14 supports up to API 34 while the
> project's `compileSdk = 35`. Compose tests run on API 34; behaviors that
> only manifest on API 35 won't be caught by this tier — reserve those for
> instrumented tests.

---

## Step 3 — Isolate the Compose suite (filename convention)

The previously-considered "separate AGP source set" approach does not work
cleanly on an Android Application module: `android.sourceSets.create("composeTest")`
does not produce a matching `compileComposeTestKotlin` task, so the
`testDebugCompose` task can't find compiled classes. The standard,
definitely-working idiom is filename convention + Gradle task filters.

**Convention:** any test class file ending in `ComposeTest.kt` is part of
the new tier. Regular `*Test.kt` stays in `testDebugUnitTest`.

**File:** `android/app/build.gradle.kts` (bottom of file, after `dependencies { ... }`)

```kotlin
dependencies {
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.test.manifest)
}

tasks.named<Test>("testDebugUnitTest") {
    exclude("**/*ComposeTest.class")
}

tasks.register<Test>("testDebugCompose") {
    description = "Runs Robolectric/Compose UI tests (*ComposeTest classes)."
    group = "compose verification"

    val unitTest = tasks.named<Test>("testDebugUnitTest").get()
    classpath = unitTest.classpath
    testClassesDirs = unitTest.testClassesDirs
    include("**/*ComposeTest.class")
    useJUnit()
    dependsOn("compileDebugUnitTestKotlin")
    // Reports under android/app/build/reports/tests/testDebugCompose/
    reports.html.outputLocation.set(
        layout.buildDirectory.dir("reports/tests/testDebugCompose")
    )
    reports.junitXml.outputLocation.set(
        layout.buildDirectory.dir("test-results/testDebugCompose")
    )
}

// Explicitly DO NOT wire testDebugCompose into the standard `check`
// lifecycle task — that would pull it into any pipeline calling `check`.
```

Result: `testDebugUnitTest` runs only `*Test.kt` (existing behavior + the new
constant test from Step 1); `testDebugCompose` runs only `*ComposeTest.kt`.
No source-set surgery, no overlap.

---

## Step 4 — Compose test harness helper

**New file:** `android/app/src/test/kotlin/org/voxquieta/app/testing/ComposeTestHarness.kt`

- Wraps `createComposeRule()` and exposes `setAppContent { ... }` which
  auto-applies `AppTheme` from `presentation/theme/Theme.kt`. Avoids
  repeating the theme wrapper in every test.
- Tiny fixture builders (`fakeVerse(...)`, `fakeAssistantMessage(...)`)
  reusing the style from `VersesPanelTest.kt:13-28`.
- Default Robolectric config documented at the top:
  `@RunWith(AndroidJUnit4::class)` + `@Config(sdk = [34])`.

`VersesPanel` takes its data as composable parameters and does not use
Hilt-injected types, so the first test does **not** need `HiltTestApplication`.
Future screen-level tests that depend on view-models will need a Hilt-wired
Robolectric Application — defer that until the second screen-level test lands.

---

## Step 5 — First Compose UI test: VersesPanel

**New file:** `android/app/src/test/kotlin/org/voxquieta/app/components/VersesPanelComposeTest.kt`

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
android-test-compose: ## Run Android Compose/Robolectric UI tests (separate from android-test)
 @echo "$(BLUE)Running Android Compose UI tests...$(NC)"
 @cd android && ./gradlew testDebugCompose --no-daemon
 @echo "$(GREEN)✓ Android Compose UI tests complete$(NC)"
 @echo "$(YELLOW)Report: android/app/build/reports/tests/testDebugCompose/index.html$(NC)"
```

Append `android-test-compose` to the `.PHONY` line at the top. Do **not**
include it in any `test`/`test-all` aggregate target — it stays an
explicit opt-in until integration.

---

## Step 7 — Independent CI workflow

**New file:** `.github/workflows/android-compose-tests.yml`

Runs in parallel with `android-ci.yml`. Reports as its own check
(`android-compose-tests / compose-ui-tests`). The check is **not required
for merge** (configure via repo branch-protection settings — see Step 9
checklist below).

```yaml
name: android-compose-tests

on:
  pull_request:
    paths:
      - 'android/**'
      - '.github/workflows/android-compose-tests.yml'
  push:
    branches: [main]
    paths:
      - 'android/**'
      - '.github/workflows/android-compose-tests.yml'

# Cancel in-flight runs of this workflow when a new push lands.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  compose-ui-tests:
    name: compose-ui-tests
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Gradle
        uses: gradle/actions/setup-gradle@v3
        with:
          cache-read-only: ${{ github.ref != 'refs/heads/main' }}

      - name: Run Compose/Robolectric UI tests
        working-directory: android
        run: ./gradlew :app:testDebugCompose --no-daemon --stacktrace

      - name: Upload HTML report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: compose-ui-test-report
          path: android/app/build/reports/tests/testDebugCompose
          retention-days: 14

      - name: Upload JUnit XML
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: compose-ui-test-results
          path: android/app/build/test-results/testDebugCompose
          retention-days: 14
```

Properties of this workflow:

- **Independent.** Separate file, separate job name, separate check on the
  PR. Failures here do not block merges (once branch protection is set).
- **Cheap on noise.** `paths` filter means it doesn't run for backend-only
  or frontend-only changes. `concurrency` cancels superseded runs.
- **Debuggable.** HTML + JUnit XML uploaded as artifacts on every run,
  pass or fail, retained 14 days.
- **Does not touch `android-ci.yml`.** That workflow keeps its current
  scope; existing required checks are unaffected.

> 📝 **Branch protection (manual repo-settings change, not in this PR):**
> after the workflow lands and reports a green run, leave it as a
> non-required check on `main`. Add it to required checks only as part of
> the future integration story.

---

## Step 8 — Documentation

**New file:** `android/COMPOSE_TESTS.md`

- **Purpose.** Three tiers explained: pure JVM (fast, stateless logic —
  existing); Robolectric/Compose (composable behavior, semantics, state
  survival — new); instrumented (emulator — existing, reserve for happy-path
  E2E).
- **How to run locally.** `make android-test-compose` (or
  `cd android && ./gradlew testDebugCompose`).
- **How CI runs it.** Independent workflow `android-compose-tests.yml`;
  non-required check; HTML + JUnit XML artifacts on every run.
- **Filename convention.** `*ComposeTest.kt` → new tier;
  `*Test.kt` → existing JVM tier. Both live under `app/src/test/`.
- **Harness usage.** Pointer to `ComposeTestHarness.kt`.
- **Future targets** (suggested order, not implemented in this story):
  1. `ChatScreenComposeTest` — top-bar policy, language picker visibility,
     message rendering.
  2. `ChatInputFieldComposeTest` — send-button enabled state, character
     limit indicator.
  3. `TranslationPickerBottomSheetComposeTest` — selection and dismissal.
  4. `VerseDetailBottomSheetComposeTest` — verse display + dismiss.
  5. `ConversationsScreenComposeTest` — empty/populated list states.
- **Integration checklist** (follow-up story — see Step 9): when ready,
  fold the Compose suite into the normal test workflow.

**File:** `AGENTS.md` — extend the existing Android section.

- Under `## Testing` → `### Android Tests`: append a third code block:

  ```
  # Compose UI tests (Robolectric — separate Gradle task + independent CI workflow)
  make android-test-compose
  ```

  Plus a sentence: *Compose UI tests follow the `*ComposeTest.kt`
  filename convention, run via `./gradlew testDebugCompose`, and have a
  dedicated GitHub Actions workflow (`android-compose-tests.yml`). They
  are intentionally isolated from the standard `testDebugUnitTest` job —
  see `android/COMPOSE_TESTS.md` for the rollout plan.*
- Under `## CI` → `### Android CI`: add a row for the new workflow
  noting that it is a non-required check until the integration follow-up.

---

## Step 9 — Integration follow-up (NOT this story)

Tracked as a sibling backlog item, to be filed after this story merges and
the workflow has shown green on a few PRs:

- Promote `android-compose-tests / compose-ui-tests` to a **required** check
  in branch protection.
- Optionally merge the workflow into `android-ci.yml` as a parallel job
  (still independent in terms of pass/fail per job, but defined in one
  place).
- Tick through the future-targets list from `COMPOSE_TESTS.md`.
- Re-evaluate Robolectric SDK level when Robolectric ships API-35 support.

---

## Critical files

| Path | Action |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt` | Extract default constant |
| `android/app/src/test/kotlin/org/voxquieta/app/components/VersesPanelTest.kt` | Add constant assertion |
| `android/gradle/libs.versions.toml` | Add `robolectric` version + library |
| `android/app/build.gradle.kts` | `isIncludeAndroidResources = true`; add deps; register `testDebugCompose` with include/exclude filters; do NOT wire into `check` |
| `android/app/src/test/kotlin/org/voxquieta/app/testing/ComposeTestHarness.kt` (new) | Harness helper |
| `android/app/src/test/kotlin/org/voxquieta/app/components/VersesPanelComposeTest.kt` (new) | First UI test |
| `.github/workflows/android-compose-tests.yml` (new) | Independent CI workflow |
| `android/COMPOSE_TESTS.md` (new) | Documentation |
| `Makefile` | Add `android-test-compose` target |
| `AGENTS.md` | Document the new suite under testing + CI |
| `.github/workflows/android-ci.yml` | **Do not modify.** Existing required checks must stay untouched. |

## Existing utilities to reuse

- Fixture builder pattern from `VersesPanelTest.kt:13-28` (`assistantMsg`,
  `userMsg`, `verse`).
- Theme wrapper: `presentation/theme/Theme.kt` (apply via harness).
- MockK is already on the test classpath for any future Compose test that
  needs to stub a callback.

## Implementation notes for whoever picks this up

- **Pre-commit will run on every commit.** This repo's pre-commit config
  includes `markdownlint`, secrets detection, and trailing-whitespace
  fixers. Run `pre-commit run --files <new files>` locally before pushing
  to avoid a red CI on the first push.
- **Verify `check` isn't pulling in `testDebugCompose`.** After landing,
  run `./gradlew check --dry-run` and grep the output for `testDebugCompose` —
  it must not appear. If it does, an Android plugin auto-wired it; add an
  explicit detach.

## Verification / acceptance

1. `make android-test` (or `./gradlew testDebugUnitTest`) → passes; report
   includes the new `DEFAULT_SHOW_REFERENCED` test; report contains **no**
   `*ComposeTest` classes.
2. `make android-test-compose` (or `./gradlew testDebugCompose`) → passes;
   runs only the four Compose tests.
3. `./gradlew check --dry-run` → output does NOT include `testDebugCompose`.
4. `./gradlew assembleDebug` → unaffected (same artifact size, same build
   time within noise).
5. Temporary regression check: flip the default back to `false` → both the
   JVM constant test and the Compose default-state test fail. Revert.
6. CI on the implementation PR:
   - `android-ci.yml` jobs pass exactly as before — no new step, no new
     timing change.
   - `android-compose-tests.yml` reports its own check with the four
     Compose tests passing.
   - HTML + JUnit artifacts are downloadable from the workflow run.
7. Force a deliberate Compose-test failure in a throwaway branch →
   `android-compose-tests` goes red; PR is still mergeable (check not
   required). Revert.

## Rollout

After this story merges:

1. Watch the new workflow for a few PR runs to confirm stability and timing.
2. File the integration follow-up (Step 9) once it has been green
   consistently.

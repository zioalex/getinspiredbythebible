# BITB-278: Enable Follow-Up Chips on Android + Match Web Chip Colors

**Status:** 🚧 In Progress
**Priority:** P2
**Size:** S (Android only)
**Created:** 2026-11-08
**Parent:** BITB-080 (suggested follow-up questions), BITB-149 (Android chips), BITB-254 (echo-back fix)

## Bug Report / Round Goal

> "I want another round to enable the suggestion chip on Android. Can you verify that it works
> properly? On the Web it is okay, but when I tested on Android the colors were a bit off."

Context: web went live in prod on #1219 (`chat_follow_ups_enabled = true` and
`web_follow_ups_enabled = true` in `deployment/terraform.tfvars`) and the drop-off fix landed in
PR #1231 (BITB-254: clients echo each turn's `follow_ups` back into `conversation_history`).
Android still ships DARK behind the default-off compile-time gate `BuildConfig.CHAT_FOLLOW_UPS_ENABLED`
(`android/app/build.gradle.kts`, flippable per-build with `-PchatFollowUpsEnabled=true`). The Play
release build (`android-publish.yml` → `./gradlew bundleRelease`) passes no such property, so every
release AAB ships dark.

The user side-loaded a `-PchatFollowUpsEnabled=true` build: the gate mechanics work (chips render,
tap-to-send works), but the colors don't match web. `FollowUpChips.kt` renders a stock Material 3
`SuggestionChip` with default colors — light mode: `surfaceVariant` #EFEBE5 container,
`outlineVariant` #CAC4D0 (gray-purple) border, `onSurfaceVariant` #49454F label — while the web
chip (`frontend/src/components/FollowUpSuggestions.tsx`) is `bg-white border-primary-200
text-gray-700`: white container, warm #E6D0B8 border (primary-200), #374151 label (gray-700), with
primary-400 #C48D62 border / primary-50 #FAF5F0 background on hover.

## Decisions (2026-11-08)

- **Enablement = flip the `build.gradle.kts` default to `true`**, retaining the `gradleProp`
  override so `-PchatFollowUpsEnabled=false` still force-disables any build (killable rollout).
  Chosen over adding `-PchatFollowUpsEnabled=true` to `android-publish.yml`: the default flip keeps
  one source of truth, makes debug/CI/release builds consistent, and cannot be silently lost by a
  manual `bundleRelease` invocation. The next release-please cycle (triggered by the `feat:` commit
  subject) publishes the enabled AAB to the Play internal track via `android-publish.yml`.
- **Light mode = match the web chip exactly** (white / #E6D0B8 / #374151). Dark mode has no web
  reference (the web chip styling is light-only — `bg-white` is hardcoded), so the dark chip keeps
  the existing `DarkColorScheme`'s readable neutral treatment (surfaceVariant-family container,
  onSurfaceVariant-family label). Do NOT use the dark scheme's `primary` (#90CAF9 light blue) for
  the chip border — it breaks the warm web palette.

## Functional Requirements

- **FR1 (enable):** `android/app/build.gradle.kts` — the `CHAT_FOLLOW_UPS_ENABLED` BuildConfig
  default flips from `"false"` to `"true"`; the `gradleProp("chatFollowUpsEnabled", …)` override
  mechanism stays; the surrounding comment (and the `ShouldShowFollowUps.kt` KDoc) no longer say
  Android "stays DARK until its own later rollout".
- **FR2 (light colors):** `FollowUpChips.kt` — light-mode chips render a white (#FFFFFF) container,
  #E6D0B8 border (web `primary-200`), #374151 label (web `text-gray-700`), via
  `SuggestionChipDefaults.suggestionChipColors(...)` + the chip border parameter (see
  `VerseDetailBottomSheet.kt` for the established custom-chip-colors pattern in this codebase).
  Palette constants get named `Color` vals documented with the web-token comment convention used in
  `presentation/theme/Theme.kt`.
- **FR3 (dark colors):** dark-mode chips stay readable using the existing `DarkColorScheme`'s
  neutral tokens (container/label/border in the surfaceVariant/onSurfaceVariant/outlineVariant
  family — not the blue `primary`).
- **FR4 (stale docs/comments):** every "Android stays dark" / default-off claim is refreshed, at
  minimum: `android/app/build.gradle.kts`, `ShouldShowFollowUps.kt` KDoc,
  `deployment/variables.tf` (`web_follow_ups_enabled` description),
  `scripts/env-manifest.yaml` (CHAT_FOLLOW_UPS_ENABLED / web-only-enablement notes), plus any
  other repo grep hit for the stale claim. `api/config.py` defaults and the flag plumbing tests
  are NOT changed (the backend flag already streams to all clients).
- **FR5 (tests):** the chip palette is JVM-testable (pure function or `@VisibleForTesting` vals)
  and pinned by unit tests for BOTH modes, so the "colors off" regression cannot silently return.
  Existing `FollowUpChipsComposeTest` (render, a11y group label, empty-degrade, first-tap send,
  gate on/off) passes unchanged. `api/tests/test_follow_ups_flag_plumbing.py` still passes after
  FR4 (it pins the plumbing regexes that the comment edits come near).

## Non-Functional Requirements

- Accessibility: label contrast ≥ 4.5:1 against its container in both modes (#374151 on white
  ≈ 10:1 ✓). Group `contentDescription` and first-tap send behavior unchanged.
- No gate-logic behavior change: `shouldShowFollowUps` / `ChatViewModel` / BITB-254 echo-back are
  untouched except for stale comments.
- Rollout stays killable: `-PchatFollowUpsEnabled=false` reproduces the old dark behavior.

## Acceptance Criteria

- [ ] A `bundleRelease` built with no -P properties ships chips enabled (BuildConfig default
      `true`; proven by the flag-definition source + CI compile).
- [ ] Light-mode chips render white container / #E6D0B8 border / #374151 label — pinned by test.
- [ ] Dark-mode chips render readable neutral colors (not the blue `primary`) — pinned by test.
- [ ] Existing render/a11y/tap/gate Compose tests pass unchanged.
- [ ] `api/tests/test_follow_ups_flag_plumbing.py` passes after the stale-comment refresh.
- [ ] Android CI green on the PR (unit-tests, lint, compile-check, translation-validation,
      instrumented-tests, secrets/dependency/apk-security checks, build).
- [ ] Owner: after the next release-please cycle publishes the AAB to the Play internal track,
      spot-check chips on a real device in light + dark mode.

## Out of Scope

- BITB-242's server-driven per-platform flag registry — the compile-time flag remains the
  enablement mechanism until that story lands; this round adds no remote kill-switch.
- Web chip styling (already correct), backend flag behavior, prompts.
- Dark-mode chip *design* beyond scheme-parity readability (no web reference exists).
- Room persistence of `followUps` (BITB-254 known limitation, unchanged).
- BITB-254's owner-side App Insights check (suppressed-rate by `history_turns` bucket).

## Plan (per file)

| File | Change |
|------|--------|
| `android/app/build.gradle.kts` | `CHAT_FOLLOW_UPS_ENABLED` default → `true`; comment refresh |
| `android/.../presentation/components/FollowUpChips.kt` | Custom chip colors + border matching the web light palette; dark stays scheme-neutral |
| `android/.../presentation/theme/Theme.kt` or a small palette object next to the component | Named `Color` constants with web-token comments |
| `android/.../FollowUpChipsComposeTest.kt` + new JVM unit test | Palette pinned for both modes; existing tests unchanged |
| `android/.../presentation/screens/ShouldShowFollowUps.kt` | KDoc: gate now default-on (killable per-build) |
| `deployment/variables.tf`, `scripts/env-manifest.yaml` | Refresh "Android stays dark" claims |
| `docs/BACKLOG.md` + this story | Entry + changelog line |

# BITB-054: First-Run Feature Spotlight / Coach-Marks (Android)

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — discoverability of core features
**Size:** M (1-2 days incl. localization)
**Created:** 2026-06-17
**Source:** Product request — "introduce main features on first launch, especially the left
sliding panel, which seems undiscovered/unused"

## User Story

**As a** first-time Android user,
**I want** a short guided highlight of the main features on first launch — *especially the
left history/menu drawer*,
**so that** I discover what the app can do instead of missing the sliding panel entirely.

## Problem

First launch currently shows only the animated `SplashScreen` + `WelcomeBanner`; nothing points
to the `ModalNavigationDrawer`, which is opened by the Menu icon in `ChatScreen.kt`
(`navigationIcon`, ~line 273). As a result the left panel — chat history, settings, new chat —
goes unnoticed. There is **no coach-mark / spotlight system** in the app today.

## Approach — Spotlight Coach-Marks

After the first chat screen renders, show a dimmed overlay that highlights **real UI targets**
one at a time, each with a short caption and Next / Skip / Done controls. Highlight order:

1. **Menu / drawer icon** — `ChatScreen.kt` `navigationIcon` (`Icons.Default.Menu`, ~line 276):
   "Your chat history, settings & new chats live here." Optionally **auto-open the drawer** to
   reveal it, then close on Next.
2. **Bible translation chip** — top-bar `SuggestionChip` (~line 283): switch Bible versions.
3. **Language picker** — `IconButton` with `Icons.Default.Language` (~line 314).
4. **Message input / example prompts** — `WelcomeBanner` suggestions.

### First-run gating

Reuse the established SharedPreferences pattern in `MainActivity.kt`
(`app_prefs` / `hasSplashBeenSeen()` / `markSplashSeen()`, lines 45-51). Add a **parallel flag**
`tour_seen`, set once the tour is completed or skipped. Keep it **independent** of `splash_seen`
so the tour can also be re-triggered from a Settings "Show app tour" action (optional AC).

### Compatibility with BITB-049

The tour must run on the fresh chat shown at launch and must **not** interfere with the
`resume → chat/new` navigation. Trigger it from within `ChatScreen` once the first chat is on
screen — **not** from the nav resolver in `MainActivity`.

## Acceptance Criteria

- [ ] On first launch (after splash), the tour appears once and highlights, in order: the
      **drawer/menu icon**, the **translation chip**, the **language picker**, and the
      **input / example prompts**.
- [ ] **Skip** and **Done** dismiss the tour and set `tour_seen = true`; it never reappears.
- [ ] All caption text is **localized in all 11 languages** and **RTL-correct for Arabic**.
- [ ] Tour does **not** break BITB-049 fresh-chat-on-launch behaviour.
- [ ] (Optional) A Settings entry can re-run the tour by clearing `tour_seen`.

## Files / Config

| Item | Location | Change |
|---|---|---|
| Spotlight overlay | `android/.../presentation/components/FeatureSpotlight.kt` (new) | Compose overlay: scrim + highlight cutout + caption + Next/Skip/Done |
| First-run flag | `android/.../MainActivity.kt` | add `hasTourBeenSeen()` / `markTourSeen()` mirroring the splash helpers (`app_prefs`, key `tour_seen`) |
| Tour trigger + targets | `android/.../presentation/screens/ChatScreen.kt` | report target bounds via `onGloballyPositioned`; show tour when `tour_seen == false` once first chat is rendered |
| Strings | `android/app/src/main/res/values*/strings.xml` | add caption strings for all 11 locales |

## Implementation Notes

- Prefer a **small self-contained Compose overlay** (`Box` + `Popup` / `Canvas` cutout +
  `MaterialTheme` scrim) over a third-party coach-mark library — consistent with the all-Compose,
  no-XML, dependency-light codebase. Expose each target's bounds via `onGloballyPositioned` and
  draw the highlight around it.
- All caption strings go through `stringResource` (no hardcoded English).
- Keep the tour interruptible: tapping the scrim advances/skips; back press = skip.

## Testing

- Compose UI test: overlay is shown when `tour_seen == false`, and absent after completion
  (`tour_seen == true`).
- Manual first-run walkthrough: fresh install → splash → tour → drawer auto-open/close →
  reaches input; relaunch shows no tour.
- Verify RTL layout for `ar` and correct highlight positioning across screen sizes.

## Out of Scope

- A full interactive product tour beyond the four highlighted targets.
- Re-running the tour after app updates (only first install / manual re-trigger).
- iOS / web equivalents (separate follow-ups if desired).

## Related

- **BITB-049** (fresh chat on launch) — tour must coexist with `resume → chat/new`.
- `MainActivity.kt` splash first-run pattern (`app_prefs` / `splash_seen`).
- `ChatScreen.kt` (`ModalNavigationDrawer`, top bar) and `WelcomeBanner.kt`.

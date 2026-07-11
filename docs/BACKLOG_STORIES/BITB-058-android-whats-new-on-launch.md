# BITB-058: Android — "What's New" Bottom Sheet on First Launch After Update

**Status:** 🎯 Todo
**Priority:** P1 (High) — users miss new features after silent auto-updates
**Size:** S (< 1 day)
**Created:** 2026-07-01
**Source:** BITB-031 deferred out-of-scope item; product initiative

## User Story

**As an** Android user,
**I want** to see a brief "What's New" summary the first time I open the app after an update,
**so that** I notice new features without having to dig into Settings manually.

## Problem

The app updates silently via auto-update or when the user taps "Update" in the Play Store. After launch, there is no signal that anything changed. BITB-031 added a changelog screen in Settings > About, but users must actively navigate there. BITB-031 explicitly deferred "a What's New modal on app start after an upgrade" as a separate story.

## Approach

1. Persist `last_seen_version_code: Int` (default `-1`) in the existing `app_prefs` SharedPreferences alongside `splash_seen`.
2. On cold start in `MainActivity`, compare stored value to `BuildConfig.VERSION_CODE`.
3. If `stored != -1 && stored < BuildConfig.VERSION_CODE` → set a flag; show `WhatsNewBottomSheet` after navigation settles.
4. Fresh install (`stored == -1`): skip the modal, write current versionCode.
5. `WhatsNewBottomSheet` loads the first (most recent) `ChangelogEntry` from the existing `assets/changelog.json` asset using the already-available `ChangelogEntry` model. Renders body with `MarkdownText` (already a dependency from BITB-031).
6. "Dismiss" closes the sheet. "See All" navigates to the existing `changelog` route. Either action writes the current versionCode.

## Acceptance Criteria

- [ ] `last_seen_version_code` key stored in `app_prefs` SharedPreferences; helpers `lastSeenVersionCode()` / `markVersionSeen(code)` added alongside `hasSplashBeenSeen()` pattern
- [ ] Modal NOT shown on fresh install (first ever launch where stored == -1)
- [ ] Modal shown exactly once per app update (not on subsequent relaunches of the same version)
- [ ] `WhatsNewBottomSheet.kt` renders the top `ChangelogEntry` from `changelog.json` using `MarkdownText`; graceful empty state if asset missing
- [ ] "Dismiss" closes the sheet and marks version as seen
- [ ] "See All" navigates to the existing `changelog` screen and marks version as seen
- [ ] String resources added in all 11 locales: `whats_new_title`, `whats_new_dismiss`, `whats_new_see_all`
- [ ] Unit tests: (a) stored==-1 → showWhatsNew==false; (b) stored==current → false; (c) stored==current-1 → true

## Files / Config

| Item | Location | Change |
|---|---|---|
| SharedPreferences helpers | `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | Add `lastSeenVersionCode()` + `markVersionSeen(code: Int)` alongside `hasSplashBeenSeen()` |
| Bottom sheet | `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/WhatsNewBottomSheet.kt` | New — loads top `ChangelogEntry`, renders with `MarkdownText`, Dismiss + See All actions |
| Main Activity wiring | `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | Compute `showWhatsNew` in `onCreate`; pass `showWhatsNew` + `onWhatsNewDismissed` / `onWhatsNewSeeAll` into composable content |
| String resources | `android/app/src/main/res/values/strings.xml` + 10 locale `strings.xml` | `whats_new_title`, `whats_new_dismiss`, `whats_new_see_all` |
| Test | `android/app/src/test/kotlin/org/voxquieta/app/screens/WhatsNewTest.kt` | Unit tests for version-tracking logic |

## Implementation Notes

```kotlin
// MainActivity.kt — alongside hasSplashBeenSeen() / markSplashSeen()
private fun Context.lastSeenVersionCode(): Int =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getInt("last_seen_version_code", -1)

private fun Context.markVersionSeen(code: Int) =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putInt("last_seen_version_code", code).apply()

// In onCreate:
val storedVersion = lastSeenVersionCode()
val showWhatsNew = storedVersion != -1 && storedVersion < BuildConfig.VERSION_CODE
if (storedVersion != BuildConfig.VERSION_CODE) markVersionSeen(BuildConfig.VERSION_CODE)
```

```kotlin
// WhatsNewBottomSheet.kt (sketch)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WhatsNewBottomSheet(onDismiss: () -> Unit, onSeeAll: () -> Unit) {
    val context = LocalContext.current
    var entry by remember { mutableStateOf<ChangelogEntry?>(null) }
    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) {
            entry = context.assets.open("changelog.json").use { stream ->
                Json.decodeFromString<List<ChangelogEntry>>(
                    stream.bufferedReader().readText()
                ).firstOrNull()
            }
        }
    }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            text = stringResource(R.string.whats_new_title),
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(horizontal = 16.dp)
        )
        entry?.let { e ->
            MarkdownText(markdown = e.body, modifier = Modifier.padding(16.dp))
        }
        Row(modifier = Modifier.padding(8.dp)) {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.whats_new_dismiss)) }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onSeeAll) { Text(stringResource(R.string.whats_new_see_all)) }
        }
    }
}
```

Reuses `ChangelogEntry` model and `MarkdownText` dependency already on the classpath — no new library needed.

## Testing

- Unit: `storedVersion = -1` → `showWhatsNew = false` (fresh install, no modal)
- Unit: `storedVersion = BuildConfig.VERSION_CODE` → `showWhatsNew = false` (same version, no repeat)
- Unit: `storedVersion = BuildConfig.VERSION_CODE - 1` → `showWhatsNew = true` (updated)
- Compose test (optional): `WhatsNewBottomSheet` renders; Dismiss calls `onDismiss`; See All calls `onSeeAll`
- Manual: install older build → update → relaunch → modal appears with latest release notes; relaunch again → no modal

## Out of Scope

- iOS
- Per-language changelog bodies (body stays English, per BITB-031 decision)
- User setting to disable the modal
- Showing multiple release notes entries (only the latest entry is shown)

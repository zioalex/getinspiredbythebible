package org.voxquieta.app

import android.content.Context

/**
 * SharedPreferences-backed flags for first-run UI modals.
 * Internal so they're accessible across the app module but not exposed publicly.
 */
internal fun Context.hasSplashBeenSeen(): Boolean =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getBoolean("splash_seen", false)

internal fun Context.markSplashSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("splash_seen", true).apply()

internal fun Context.lastSeenVersionCode(): Int =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getInt("last_seen_version_code", -1)

internal fun Context.markVersionSeen(code: Int) =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putInt("last_seen_version_code", code).apply()

/** BITB-082: "seen once ever" flag for the About intro sheet. */
internal fun Context.hasAboutIntroBeenSeen(): Boolean =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getBoolean("about_intro_seen", false)

internal fun Context.markAboutIntroSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("about_intro_seen", true).apply()

/** BITB-054: First-run feature spotlight / coach marks. */
internal fun Context.hasTourBeenSeen(): Boolean =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getBoolean("tour_seen", false)

internal fun Context.markTourSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("tour_seen", true).apply()

internal fun Context.clearTourSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("tour_seen", false).apply()

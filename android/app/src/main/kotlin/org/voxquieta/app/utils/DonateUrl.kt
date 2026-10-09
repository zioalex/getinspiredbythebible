package org.voxquieta.app.utils

import org.voxquieta.app.BuildConfig

/** Per-surface `ref` values appended to the donate URL (BITB-168). */
enum class DonateRef(val value: String) {
    DRAWER("android-drawer"),
    SETTINGS("android-settings"),
}

/**
 * Donate URL with the per-surface `ref` query param. The only place the base URL and the
 * `ref` suffix are composed on Android. Plain string composition (no android.net.Uri) so it
 * is JVM-unit-testable.
 */
fun donateUrl(ref: DonateRef, base: String = BuildConfig.DONATE_URL): String {
    val separator = if ('?' in base) '&' else '?'
    return "$base${separator}ref=${ref.value}"
}

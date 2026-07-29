package org.voxquieta.app.utils

import org.voxquieta.app.BuildConfig

/**
 * Supported web locales for the voxquieta.org frontend.
 * Sourced from frontend/src/i18n/routing.ts.
 */
private val SUPPORTED_WEB_LOCALES =
    setOf("en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko")

/**
 * Maps an Android BCP-47 language tag to the corresponding web locale segment.
 *
 * - Region tags are dropped (e.g. "en-US" → "en").
 * - Chinese variants zh-Hans / zh-Hant both map to "zh".
 * - Any code not in [SUPPORTED_WEB_LOCALES] falls back to "en".
 */
fun webLocaleFor(languageCode: String): String {
    val base = languageCode.lowercase().split("-", "_").first()
    return if (base in SUPPORTED_WEB_LOCALES) base else "en"
}

private fun frontendBase(base: String): String = base.trimEnd('/')

/** Locale-aware Privacy Policy URL for the voxquieta.org web app. */
fun privacyUrl(languageCode: String, base: String = BuildConfig.FRONTEND_URL): String =
    "${frontendBase(base)}/${webLocaleFor(languageCode)}/privacy"

/** Locale-aware Terms of Service URL for the voxquieta.org web app. */
fun termsUrl(languageCode: String, base: String = BuildConfig.FRONTEND_URL): String =
    "${frontendBase(base)}/${webLocaleFor(languageCode)}/terms"

/** Locale-aware About page URL for the voxquieta.org web app (BITB-082). */
fun aboutUrl(languageCode: String, base: String = BuildConfig.FRONTEND_URL): String =
    "${frontendBase(base)}/${webLocaleFor(languageCode)}/about"

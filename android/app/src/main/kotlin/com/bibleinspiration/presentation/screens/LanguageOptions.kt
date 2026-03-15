package com.bibleinspiration.presentation.screens

/** Language option used by the language picker in screens. */
internal data class LanguageOption(val code: String, val displayName: String)

internal val LANGUAGE_OPTIONS = listOf(
    LanguageOption("en", "🇬🇧 English"),
    LanguageOption("it", "🇮🇹 Italiano"),
    LanguageOption("de", "🇩🇪 Deutsch"),
    LanguageOption("es", "🇪🇸 Español"),
    LanguageOption("fr", "🇫🇷 Français"),
    LanguageOption("ar", "🇸🇦 العربية"),
    LanguageOption("pt", "🇧🇷 Português"),
    LanguageOption("ru", "🇷🇺 Русский"),
    LanguageOption("zh", "🇨🇳 中文"),
    LanguageOption("hi", "🇮🇳 हिन्दी"),
    LanguageOption("ko", "🇰🇷 한국어"),
)

package com.bibleinspiration.utils

import androidx.compose.ui.unit.LayoutDirection

object LocaleHelper {
    /** Returns true if the given BCP-47 language tag requires RTL layout. */
    fun isRtl(languageCode: String): Boolean = languageCode.lowercase().startsWith("ar")

    /** Maps a BCP-47 language code to the Compose [LayoutDirection]. */
    fun layoutDirectionFor(languageCode: String): LayoutDirection =
        if (isRtl(languageCode)) LayoutDirection.Rtl else LayoutDirection.Ltr
}

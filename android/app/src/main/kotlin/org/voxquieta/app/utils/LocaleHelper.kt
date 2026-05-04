package org.voxquieta.app.utils

import android.content.res.Configuration
import androidx.compose.ui.unit.LayoutDirection
import java.util.Locale

object LocaleHelper {
    /** Returns true if the given BCP-47 language tag requires RTL layout. */
    fun isRtl(languageCode: String): Boolean = languageCode.lowercase().startsWith("ar")

    /** Maps a BCP-47 language code to the Compose [LayoutDirection]. */
    fun layoutDirectionFor(languageCode: String): LayoutDirection =
        if (isRtl(languageCode)) LayoutDirection.Rtl else LayoutDirection.Ltr

    /** Wraps [base] with a configuration context for [code], updating the default locale. */
    fun wrapContext(base: android.content.Context, code: String): android.content.Context {
        val locale = Locale(code)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        Locale.setDefault(locale)
        return base.createConfigurationContext(config)
    }
}

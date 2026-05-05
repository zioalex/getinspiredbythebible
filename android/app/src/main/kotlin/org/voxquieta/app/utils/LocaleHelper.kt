package org.voxquieta.app.utils

import android.content.Context
import android.content.res.Configuration
import androidx.compose.ui.unit.LayoutDirection
import java.util.Locale

object LocaleHelper {
    /** Returns true if the given BCP-47 language tag requires RTL layout. */
    fun isRtl(languageCode: String): Boolean = languageCode.lowercase().startsWith("ar")

    /** Maps a BCP-47 language code to the Compose [LayoutDirection]. */
    fun layoutDirectionFor(languageCode: String): LayoutDirection =
        if (isRtl(languageCode)) LayoutDirection.Rtl else LayoutDirection.Ltr

    /**
     * Returns a [Context] whose [android.content.res.Resources] resolves strings against
     * [languageCode]. Used from [android.app.Activity.attachBaseContext] so every resource
     * lookup — including those that bypass Compose's CompositionLocals — picks up the
     * user's chosen locale.
     */
    fun wrapContext(base: Context, languageCode: String): Context {
        val locale = Locale(languageCode)
        Locale.setDefault(locale)
        val config = Configuration(base.resources.configuration).apply { setLocale(locale) }
        return base.createConfigurationContext(config)
    }
}

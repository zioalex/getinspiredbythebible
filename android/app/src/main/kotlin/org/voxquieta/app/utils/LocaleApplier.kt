package org.voxquieta.app.utils

import android.annotation.SuppressLint
import android.app.LocaleManager
import android.content.Context
import android.os.Build
import android.os.LocaleList
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

interface LocaleApplier {
    fun apply(languageTag: String)
}

@Singleton
class AppCompatLocaleApplier @Inject constructor(
    @ApplicationContext private val context: Context,
) : LocaleApplier {
    @SuppressLint("NewApi")
    override fun apply(languageTag: String) {
        Timber.tag("VoxLocale").i(
            "LocaleApplier.apply(%s) entering; SDK_INT=%d",
            languageTag,
            Build.VERSION.SDK_INT,
        )
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                // Call the platform LocaleManager directly. AppCompatDelegate's
                // setApplicationLocales requires AppCompatActivity to have initialized
                // its internal app-context reference; we use ComponentActivity, so the
                // AppCompat path silently no-ops and never reaches LocaleManager.
                val localeManager = context.getSystemService(LocaleManager::class.java)
                localeManager.applicationLocales = LocaleList.forLanguageTags(languageTag)
                val applied = localeManager.applicationLocales.toLanguageTags()
                Timber.tag("VoxLocale").i("LocaleManager.applicationLocales set; readback=%s", applied)
            } else {
                AppCompatDelegate.setApplicationLocales(
                    LocaleListCompat.forLanguageTags(languageTag)
                )
                val applied = AppCompatDelegate.getApplicationLocales().toLanguageTags()
                Timber.tag("VoxLocale").i("AppCompatDelegate path; getApplicationLocales=%s", applied)
            }
        } catch (t: Throwable) {
            Timber.tag("VoxLocale").e(t, "LocaleApplier.apply threw")
        }
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class LocaleApplierModule {
    @Binds
    abstract fun bindLocaleApplier(impl: AppCompatLocaleApplier): LocaleApplier
}

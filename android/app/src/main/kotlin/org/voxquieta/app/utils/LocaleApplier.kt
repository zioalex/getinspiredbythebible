package org.voxquieta.app.utils

import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import android.os.Build
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

interface LocaleApplier {
    fun apply(languageTag: String)
}

@Singleton
class AppCompatLocaleApplier @Inject constructor() : LocaleApplier {
    override fun apply(languageTag: String) {
        Timber.tag("VoxLocale").i(
            "AppCompatLocaleApplier.apply(%s) entering; SDK_INT=%d",
            languageTag,
            Build.VERSION.SDK_INT,
        )
        try {
            AppCompatDelegate.setApplicationLocales(
                LocaleListCompat.forLanguageTags(languageTag)
            )
            val applied = AppCompatDelegate.getApplicationLocales().toLanguageTags()
            Timber.tag("VoxLocale").i("AppCompatLocaleApplier.apply done; getApplicationLocales=%s", applied)
        } catch (t: Throwable) {
            Timber.tag("VoxLocale").e(t, "AppCompatLocaleApplier.apply threw")
        }
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class LocaleApplierModule {
    @Binds
    abstract fun bindLocaleApplier(impl: AppCompatLocaleApplier): LocaleApplier
}

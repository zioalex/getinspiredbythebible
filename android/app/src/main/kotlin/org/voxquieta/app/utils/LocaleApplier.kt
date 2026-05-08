package org.voxquieta.app.utils

import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Applies a per-app locale at the system level. The implementation uses
 * AppCompatDelegate.setApplicationLocales which:
 *   - Triggers a single Activity recreate so every stringResource() reflects the choice.
 *   - Persists the choice via the platform LocaleManager (API 33+) or AndroidX backport (API 21–32).
 *   - Surfaces the app in the system Settings -> App languages screen.
 *
 * Abstracted behind an interface so unit tests can substitute a no-op implementation
 * (AppCompatDelegate is part of the Android runtime and not present on the JVM test classpath).
 */
interface LocaleApplier {
    fun apply(languageTag: String)
}

@Singleton
class AppCompatLocaleApplier @Inject constructor() : LocaleApplier {
    override fun apply(languageTag: String) {
        AppCompatDelegate.setApplicationLocales(
            LocaleListCompat.forLanguageTags(languageTag)
        )
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class LocaleApplierModule {
    @Binds
    abstract fun bindLocaleApplier(impl: AppCompatLocaleApplier): LocaleApplier
}

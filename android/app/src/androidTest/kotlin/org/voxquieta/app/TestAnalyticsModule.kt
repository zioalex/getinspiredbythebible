package org.voxquieta.app

import org.voxquieta.app.analytics.AnalyticsHelper
import org.voxquieta.app.analytics.NoOpAnalyticsHelper
import org.voxquieta.app.di.AnalyticsModule
import dagger.Module
import dagger.Provides
import dagger.hilt.components.SingletonComponent
import dagger.hilt.testing.TestInstallIn
import javax.inject.Singleton

/**
 * Replaces [AnalyticsModule] during instrumented tests with a pure [NoOpAnalyticsHelper].
 *
 * **Why this is necessary:**
 * [AnalyticsModule] imports [com.google.firebase.analytics.FirebaseAnalytics] and
 * [com.google.firebase.crashlytics.FirebaseCrashlytics] at the class level.  When ART loads
 * the module class during Hilt component initialisation, it also loads those Firebase classes
 * and triggers their static initialisers.  The static initialisers call
 * `FirebaseApp.getInstance()` which requires a properly initialised Firebase project.
 * In CI, only a placeholder `google-services.json` is present (fake project-number / app-id),
 * so the call throws `IllegalStateException: Default FirebaseApp is not initialized` — crashing
 * the test process before a single test runs.
 *
 * By replacing the entire module here we ensure **no Firebase class is loaded at all**
 * during instrumented tests, making the test suite completely independent of Firebase.
 */
@Module
@TestInstallIn(
    components = [SingletonComponent::class],
    replaces = [AnalyticsModule::class],
)
object TestAnalyticsModule {

    @Provides
    @Singleton
    fun provideAnalyticsHelper(): AnalyticsHelper = NoOpAnalyticsHelper()
}

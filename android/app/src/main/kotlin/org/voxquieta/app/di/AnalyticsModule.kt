package org.voxquieta.app.di

import android.content.Context
import org.voxquieta.app.BuildConfig
import org.voxquieta.app.analytics.AnalyticsHelper
import org.voxquieta.app.analytics.FirebaseAnalyticsHelper
import org.voxquieta.app.analytics.NoOpAnalyticsHelper
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt module that binds the correct [AnalyticsHelper] implementation:
 * - [NoOpAnalyticsHelper] for debug builds (no data sent to Firebase)
 * - [FirebaseAnalyticsHelper] for release builds (full Firebase reporting)
 *
 * The decision is made at **compile time** via [BuildConfig.FIREBASE_ENABLED] so
 * ProGuard/R8 can strip the Firebase code paths from debug builds entirely.
 */
@Module
@InstallIn(SingletonComponent::class)
object AnalyticsModule {

    @Provides
    @Singleton
    fun provideAnalyticsHelper(
        @ApplicationContext context: Context,
    ): AnalyticsHelper {
        return if (BuildConfig.FIREBASE_ENABLED) {
            val firebaseAnalytics = FirebaseAnalytics.getInstance(context)
            val crashlytics = FirebaseCrashlytics.getInstance()
            FirebaseAnalyticsHelper(firebaseAnalytics, crashlytics)
        } else {
            NoOpAnalyticsHelper()
        }
    }
}

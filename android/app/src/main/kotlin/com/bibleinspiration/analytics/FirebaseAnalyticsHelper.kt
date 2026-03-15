package com.bibleinspiration.analytics

import android.os.Bundle
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics
import timber.log.Timber

/**
 * Production [AnalyticsHelper] backed by Firebase Analytics and Firebase Crashlytics.
 *
 * Used in **release** builds only (injected via [com.bibleinspiration.di.AnalyticsModule]).
 * Never instantiated in debug builds, ensuring no data is sent during development.
 */
class FirebaseAnalyticsHelper(
    private val firebaseAnalytics: FirebaseAnalytics,
    private val crashlytics: FirebaseCrashlytics,
) : AnalyticsHelper {

    override fun logEvent(name: String, params: Map<String, String>) {
        val bundle = Bundle().apply {
            params.forEach { (key, value) -> putString(key, value) }
        }
        firebaseAnalytics.logEvent(name, bundle)
        Timber.v("[Analytics] event=%s params=%s", name, params)
    }

    override fun setCurrentScreen(screenName: String) {
        val bundle = Bundle().apply {
            putString(FirebaseAnalytics.Param.SCREEN_NAME, screenName)
        }
        firebaseAnalytics.logEvent(FirebaseAnalytics.Event.SCREEN_VIEW, bundle)
        Timber.v("[Analytics] screen=%s", screenName)
    }

    override fun recordNonFatalException(throwable: Throwable, message: String?) {
        if (message != null) {
            crashlytics.log(message)
        }
        crashlytics.recordException(throwable)
        Timber.w(throwable, "[Crashlytics] non-fatal recorded: %s", message)
    }
}

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
 *
 * The [logEventFn], [recordExceptionFn], and [logMessageFn] parameters are injected so that
 * unit tests can pass simple lambdas instead of the final Firebase SDK classes (which cannot
 * be mocked with MockK in JVM unit tests without the Java agent).
 */
class FirebaseAnalyticsHelper(
    private val logEventFn: (name: String, params: Bundle) -> Unit,
    private val recordExceptionFn: (Throwable) -> Unit,
    private val logMessageFn: (String) -> Unit,
) : AnalyticsHelper {

    /**
     * Convenience constructor for production use — wraps real Firebase instances.
     */
    constructor(
        firebaseAnalytics: FirebaseAnalytics,
        crashlytics: FirebaseCrashlytics,
    ) : this(
        logEventFn = { name, bundle -> firebaseAnalytics.logEvent(name, bundle) },
        recordExceptionFn = { throwable -> crashlytics.recordException(throwable) },
        logMessageFn = { message -> crashlytics.log(message) },
    )

    override fun logEvent(name: String, params: Map<String, String>) {
        val bundle = Bundle().apply {
            params.forEach { (key, value) -> putString(key, value) }
        }
        logEventFn(name, bundle)
        Timber.v("[Analytics] event=%s params=%s", name, params)
    }

    override fun setCurrentScreen(screenName: String) {
        val bundle = Bundle().apply {
            putString(FirebaseAnalytics.Param.SCREEN_NAME, screenName)
        }
        logEventFn(FirebaseAnalytics.Event.SCREEN_VIEW, bundle)
        Timber.v("[Analytics] screen=%s", screenName)
    }

    override fun recordNonFatalException(throwable: Throwable, message: String?) {
        if (message != null) {
            logMessageFn(message)
        }
        recordExceptionFn(throwable)
        Timber.w(throwable, "[Crashlytics] non-fatal recorded: %s", message)
    }
}

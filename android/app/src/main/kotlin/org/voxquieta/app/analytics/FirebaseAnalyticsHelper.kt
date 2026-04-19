package org.voxquieta.app.analytics

import android.os.Bundle
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics
import timber.log.Timber

/**
 * Production [AnalyticsHelper] backed by Firebase Analytics and Firebase Crashlytics.
 *
 * Used in **release** builds only (injected via [org.voxquieta.app.di.AnalyticsModule]).
 * Never instantiated in debug builds, ensuring no data is sent during development.
 *
 * The [logEventFn], [recordExceptionFn], and [logMessageFn] parameters are injected so that
 * unit tests can pass simple lambdas instead of the final Firebase SDK classes.  The lambda
 * for analytics events receives the event name and a plain [Map] so that tests never touch
 * [android.os.Bundle] (whose constructor throws RuntimeException("Stub!") in JVM unit tests).
 */
class FirebaseAnalyticsHelper(
    private val logEventFn: (name: String, params: Map<String, String>) -> Unit,
    private val recordExceptionFn: (Throwable) -> Unit,
    private val logMessageFn: (String) -> Unit,
) : AnalyticsHelper {

    /**
     * Convenience constructor for production use — wraps real Firebase instances.
     * Bundle construction happens inside this lambda, not in the class body, so it
     * is never executed in JVM unit tests.
     */
    constructor(
        firebaseAnalytics: FirebaseAnalytics,
        crashlytics: FirebaseCrashlytics,
    ) : this(
        logEventFn = { name, params ->
            val bundle = Bundle().apply {
                params.forEach { (key, value) -> putString(key, value) }
            }
            firebaseAnalytics.logEvent(name, bundle)
        },
        recordExceptionFn = { throwable -> crashlytics.recordException(throwable) },
        logMessageFn = { message -> crashlytics.log(message) },
    )

    override fun logEvent(name: String, params: Map<String, String>) {
        logEventFn(name, params)
        Timber.v("[Analytics] event=%s params=%s", name, params)
    }

    override fun setCurrentScreen(screenName: String) {
        logEventFn(
            FirebaseAnalytics.Event.SCREEN_VIEW,
            mapOf(FirebaseAnalytics.Param.SCREEN_NAME to screenName),
        )
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

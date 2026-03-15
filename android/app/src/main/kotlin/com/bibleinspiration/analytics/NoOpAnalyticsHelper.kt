package com.bibleinspiration.analytics

import timber.log.Timber

/**
 * No-op [AnalyticsHelper] used in **debug** builds.
 *
 * Every call is forwarded to Timber so developers can still observe analytics events
 * in Logcat without sending any data to Firebase.
 */
class NoOpAnalyticsHelper : AnalyticsHelper {

    override fun logEvent(name: String, params: Map<String, String>) {
        Timber.d("[Analytics/NoOp] event=%s params=%s", name, params)
    }

    override fun setCurrentScreen(screenName: String) {
        Timber.d("[Analytics/NoOp] screen=%s", screenName)
    }

    override fun recordNonFatalException(throwable: Throwable, message: String?) {
        Timber.d(throwable, "[Analytics/NoOp] non-fatal: %s", message)
    }
}

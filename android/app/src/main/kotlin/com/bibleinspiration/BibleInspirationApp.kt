package com.bibleinspiration

import android.app.Application
import com.bibleinspiration.utils.LogCollector
import com.google.firebase.FirebaseApp
import com.google.firebase.crashlytics.FirebaseCrashlytics
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber

@HiltAndroidApp
class BibleInspirationApp : Application() {
    override fun onCreate() {
        super.onCreate()

        // Initialize Firebase early so Crashlytics can capture exceptions from app startup.
        // FirebaseApp.initializeApp is idempotent and safe to call in all build variants;
        // data collection is disabled at runtime for debug builds below.
        FirebaseApp.initializeApp(this)

        // Crashlytics: disable data collection in debug builds so no crash reports
        // or analytics events are sent during development or on CI.
        FirebaseCrashlytics.getInstance().setCrashlyticsCollectionEnabled(BuildConfig.FIREBASE_ENABLED)

        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }
        // Plant an in-memory collector in all builds so bug reports have logs even in release.
        Timber.plant(object : Timber.Tree() {
            override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
                LogCollector.log(priority, tag, message, t)
            }
        })
    }
}

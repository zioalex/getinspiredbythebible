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

        // Initialize Firebase only in builds where it is enabled (i.e. release).
        // In debug / CI builds FIREBASE_ENABLED=false, so we skip initialization
        // entirely — no Firebase SDK calls are made, no data is sent, and the
        // placeholder google-services.json never causes a crash.
        if (BuildConfig.FIREBASE_ENABLED) {
            FirebaseApp.initializeApp(this)
            FirebaseCrashlytics.getInstance().setCrashlyticsCollectionEnabled(true)
        }

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

package com.bibleinspiration

import android.app.Application
import com.bibleinspiration.utils.LogCollector
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber

@HiltAndroidApp
class BibleInspirationApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }
        // Plant LogCollector in all builds so bug reports have logs even in release.
        Timber.plant(LogCollector)
    }
}

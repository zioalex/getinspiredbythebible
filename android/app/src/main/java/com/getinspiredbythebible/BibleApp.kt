package com.getinspiredbythebible

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Application class that triggers Hilt's code generation and component initialization.
 *
 * Referenced in AndroidManifest.xml via android:name=".BibleApp".
 */
@HiltAndroidApp
class BibleApp : Application()

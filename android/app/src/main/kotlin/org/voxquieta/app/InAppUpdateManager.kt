package org.voxquieta.app

import android.app.Activity
import com.google.android.play.core.appupdate.AppUpdateManager
import com.google.android.play.core.install.InstallStateUpdatedListener
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.InstallStatus
import com.google.android.play.core.install.model.UpdateAvailability
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Wraps Google Play's In-App Update API (flexible flow). Deliberately has no
 * [org.voxquieta.app.BuildConfig] reference — the debug/release gate lives at the
 * [MainActivity] call sites so this class stays trivially unit-testable with
 * `FakeAppUpdateManager`.
 */
@Singleton
class InAppUpdateManager @Inject constructor(
    private val appUpdateManager: AppUpdateManager,
) {

    companion object {
        private const val UPDATE_REQUEST_CODE = 1001
    }

    private val _installReady = MutableSharedFlow<Unit>(replay = 0, extraBufferCapacity = Channel.UNLIMITED)
    val installReady: SharedFlow<Unit> = _installReady.asSharedFlow()

    private var installListener: InstallStateUpdatedListener? = null

    /** Call once per cold start (after `super.onCreate()`). */
    fun checkForUpdate(activity: Activity) {
        appUpdateManager.appUpdateInfo
            .addOnSuccessListener { info ->
                when {
                    info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE &&
                        info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE) -> {
                        registerInstallListener()
                        appUpdateManager.startUpdateFlowForResult(
                            info,
                            AppUpdateType.FLEXIBLE,
                            activity,
                            UPDATE_REQUEST_CODE,
                        )
                    }
                    info.installStatus() == InstallStatus.DOWNLOADED -> _installReady.tryEmit(Unit)
                }
            }
            .addOnFailureListener { e ->
                // No Play Store on this device (sideload, emulator without Play Services) — fail silent.
                Timber.w(e, "[InAppUpdate] appUpdateInfo lookup failed")
            }
    }

    /** Call from `onResume` to catch an update that finished downloading while backgrounded. */
    fun checkForPendingInstall() {
        appUpdateManager.appUpdateInfo
            .addOnSuccessListener { info ->
                if (info.installStatus() == InstallStatus.DOWNLOADED) _installReady.tryEmit(Unit)
            }
            .addOnFailureListener { e ->
                Timber.w(e, "[InAppUpdate] appUpdateInfo lookup failed")
            }
    }

    fun completeUpdate() {
        appUpdateManager.completeUpdate()
    }

    /** Call from `onDestroy` to avoid leaking the listener. */
    fun unregisterListener() {
        installListener?.let { appUpdateManager.unregisterListener(it) }
        installListener = null
    }

    private fun registerInstallListener() {
        if (installListener != null) return
        val listener = InstallStateUpdatedListener { state ->
            if (state.installStatus() == InstallStatus.DOWNLOADED) _installReady.tryEmit(Unit)
        }
        installListener = listener
        appUpdateManager.registerListener(listener)
    }
}

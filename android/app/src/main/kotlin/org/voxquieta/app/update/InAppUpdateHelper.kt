package org.voxquieta.app.update

import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.IntentSenderRequest
import androidx.annotation.VisibleForTesting
import com.google.android.play.core.appupdate.AppUpdateManager
import com.google.android.play.core.appupdate.AppUpdateOptions
import com.google.android.play.core.install.InstallStateUpdatedListener
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.InstallStatus
import com.google.android.play.core.install.model.UpdateAvailability
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber

class InAppUpdateHelper(private val appUpdateManager: AppUpdateManager) {

    private val _updateDownloaded = MutableStateFlow(false)
    val updateDownloaded: StateFlow<Boolean> = _updateDownloaded.asStateFlow()

    private val installStateListener = InstallStateUpdatedListener { state ->
        handleInstallState(state.installStatus())
    }

    init {
        appUpdateManager.registerListener(installStateListener)
    }

    @VisibleForTesting
    internal fun handleInstallState(status: Int) {
        if (status == InstallStatus.DOWNLOADED) {
            _updateDownloaded.value = true
        }
    }

    fun checkForUpdate(launcher: ActivityResultLauncher<IntentSenderRequest>) {
        appUpdateManager.appUpdateInfo
            .addOnSuccessListener { info ->
                when {
                    info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
                        && info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE) -> {
                        appUpdateManager.startUpdateFlow(
                            info,
                            launcher,
                            AppUpdateOptions.newBuilder(AppUpdateType.FLEXIBLE).build(),
                        )
                    }
                    info.installStatus() == InstallStatus.DOWNLOADED -> {
                        _updateDownloaded.value = true
                    }
                }
            }
            .addOnFailureListener { e ->
                Timber.d(e, "In-app update check skipped (Play Store unavailable or no network)")
            }
    }

    fun completeUpdate() {
        appUpdateManager.completeUpdate()
        _updateDownloaded.value = false
    }

    fun release() {
        appUpdateManager.unregisterListener(installStateListener)
    }
}

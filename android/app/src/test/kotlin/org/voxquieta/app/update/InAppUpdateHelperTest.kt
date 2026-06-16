package org.voxquieta.app.update

import com.google.android.play.core.appupdate.AppUpdateManager
import com.google.android.play.core.install.InstallStateUpdatedListener
import com.google.android.play.core.install.model.InstallStatus
import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import io.mockk.verify
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class InAppUpdateHelperTest {

    private val listenerSlot = slot<InstallStateUpdatedListener>()
    private val mockManager = mockk<AppUpdateManager>(relaxed = true) {
        every { registerListener(capture(listenerSlot)) } returns Unit
    }
    private lateinit var helper: InAppUpdateHelper

    @Before
    fun setUp() {
        helper = InAppUpdateHelper(mockManager)
    }

    @Test
    fun `updateDownloaded is false initially`() {
        assertFalse(helper.updateDownloaded.value)
    }

    @Test
    fun `handleInstallState DOWNLOADED sets updateDownloaded to true`() {
        helper.handleInstallState(InstallStatus.DOWNLOADED)
        assertTrue(helper.updateDownloaded.value)
    }

    @Test
    fun `handleInstallState DOWNLOADING does not set updateDownloaded`() {
        helper.handleInstallState(InstallStatus.DOWNLOADING)
        assertFalse(helper.updateDownloaded.value)
    }

    @Test
    fun `handleInstallState INSTALLED does not set updateDownloaded`() {
        helper.handleInstallState(InstallStatus.INSTALLED)
        assertFalse(helper.updateDownloaded.value)
    }

    @Test
    fun `completeUpdate resets updateDownloaded to false`() {
        helper.handleInstallState(InstallStatus.DOWNLOADED)
        assertTrue(helper.updateDownloaded.value)
        helper.completeUpdate()
        assertFalse(helper.updateDownloaded.value)
    }

    @Test
    fun `release unregisters the install state listener`() {
        helper.release()
        verify { mockManager.unregisterListener(any()) }
    }

    @Test
    fun `installStateListener fires handleInstallState on state change`() {
        // The listener is captured in the slot during init
        val listener = listenerSlot.captured
        val mockState = mockk<com.google.android.play.core.install.InstallState> {
            every { installStatus() } returns InstallStatus.DOWNLOADED
        }
        listener.onStateUpdate(mockState)
        assertTrue(helper.updateDownloaded.value)
    }
}

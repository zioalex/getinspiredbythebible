package org.voxquieta.app

import android.app.Activity
import android.os.Looper
import androidx.test.core.app.ApplicationProvider
import com.google.android.play.core.appupdate.testing.FakeAppUpdateManager
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config

/**
 * Robolectric-backed (not plain JUnit) because [FakeAppUpdateManager] needs a real
 * [android.content.Context] and dispatches its `appUpdateInfo` `Task` callbacks on the
 * main looper, which only Robolectric can pump in a JVM unit test.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)
class InAppUpdateManagerTest {

    private lateinit var fakeAppUpdateManager: FakeAppUpdateManager
    private lateinit var manager: InAppUpdateManager
    private lateinit var activity: Activity

    @Before
    fun setUp() {
        fakeAppUpdateManager = FakeAppUpdateManager(ApplicationProvider.getApplicationContext())
        manager = InAppUpdateManager(fakeAppUpdateManager)
        activity = Robolectric.buildActivity(Activity::class.java).setup().get()
    }

    private fun idleMainLooper() {
        Shadows.shadowOf(Looper.getMainLooper()).idle()
    }

    @Test
    fun `checkForUpdate starts the flexible flow when an update is available`() {
        fakeAppUpdateManager.setUpdateAvailable(2)
        idleMainLooper()

        manager.checkForUpdate(activity)
        idleMainLooper()

        // isConfirmationDialogVisible flips true once startUpdateFlowForResult has been
        // invoked on the fake — the documented signal (developer.android.com/guide/
        // playcore/in-app-updates/test) that an update flow was actually requested.
        assertTrue(fakeAppUpdateManager.isConfirmationDialogVisible)
    }

    @Test
    fun `checkForUpdate prompts even for a freshly published release (staleness 0)`() {
        fakeAppUpdateManager.setUpdateAvailable(2)
        fakeAppUpdateManager.setClientVersionStalenessDays(0)
        idleMainLooper()

        manager.checkForUpdate(activity)
        idleMainLooper()

        assertTrue(fakeAppUpdateManager.isConfirmationDialogVisible)
    }

    @Test
    fun `checkForUpdate is a no-op and does not throw when no update is available`() = runTest {
        var emissionCount = 0
        val job = launch { manager.installReady.collect { emissionCount++ } }
        testScheduler.advanceUntilIdle()

        manager.checkForUpdate(activity)
        idleMainLooper()
        testScheduler.advanceUntilIdle()

        assertFalse(fakeAppUpdateManager.isConfirmationDialogVisible)
        assertEquals(0, emissionCount)
        job.cancel()
    }

    @Test
    fun `installReady emits once the flexible update finishes downloading`() = runTest {
        var emissionCount = 0
        val job = launch { manager.installReady.collect { emissionCount++ } }
        testScheduler.advanceUntilIdle()

        fakeAppUpdateManager.setUpdateAvailable(2)
        idleMainLooper()
        manager.checkForUpdate(activity)
        idleMainLooper()

        fakeAppUpdateManager.userAcceptsUpdate()
        fakeAppUpdateManager.downloadStarts()
        fakeAppUpdateManager.downloadCompletes()
        idleMainLooper()
        testScheduler.advanceUntilIdle()

        assertEquals(1, emissionCount)
        job.cancel()
    }

    @Test
    fun `checkForPendingInstall emits when a download already completed while backgrounded`() = runTest {
        // Drive a download to completion first (as if it happened while backgrounded),
        // then only start collecting installReady afterward — checkForPendingInstall
        // must independently discover the already-DOWNLOADED status via a fresh
        // appUpdateInfo lookup, not rely on the listener registered by checkForUpdate.
        fakeAppUpdateManager.setUpdateAvailable(2)
        idleMainLooper()
        manager.checkForUpdate(activity)
        idleMainLooper()
        fakeAppUpdateManager.userAcceptsUpdate()
        fakeAppUpdateManager.downloadStarts()
        fakeAppUpdateManager.downloadCompletes()
        idleMainLooper()

        var emissionCount = 0
        val job = launch { manager.installReady.collect { emissionCount++ } }
        testScheduler.advanceUntilIdle()

        manager.checkForPendingInstall()
        idleMainLooper()
        testScheduler.advanceUntilIdle()

        assertEquals(1, emissionCount)
        job.cancel()
    }
}

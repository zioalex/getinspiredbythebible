package com.bibleinspiration.analytics

import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for [FirebaseAnalyticsHelper].
 *
 * Firebase SDK objects ([FirebaseAnalytics] and [FirebaseCrashlytics]) are mocked with MockK
 * (relaxed = true) so that no real Firebase calls are made during tests.
 *
 * Note: [android.os.Bundle] is an Android framework stub in JVM unit tests and its methods
 * throw [RuntimeException] ("Stub!").  We therefore verify behaviour at the Firebase call-site
 * boundary (did the correct method get called with the right event name?) rather than
 * inspecting Bundle contents.  Bundle construction is an implementation detail of
 * [FirebaseAnalyticsHelper] tested indirectly through the Firebase mock invocations.
 */
class FirebaseAnalyticsHelperTest {

    private val firebaseAnalytics: FirebaseAnalytics = mockk(relaxed = true)
    private val crashlytics: FirebaseCrashlytics = mockk(relaxed = true)

    private lateinit var helper: FirebaseAnalyticsHelper

    @Before
    fun setUp() {
        helper = FirebaseAnalyticsHelper(firebaseAnalytics, crashlytics)
    }

    // -------------------------------------------------------------------------
    // logEvent
    // -------------------------------------------------------------------------

    @Test
    fun `logEvent calls firebaseAnalytics logEvent with correct event name`() {
        helper.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT)

        verify { firebaseAnalytics.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT, any()) }
    }

    @Test
    fun `logEvent with params calls Firebase exactly once`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_LANGUAGE_CHANGED,
            mapOf(AnalyticsHelper.PARAM_LANGUAGE to "fr"),
        )

        verify(exactly = 1) { firebaseAnalytics.logEvent(AnalyticsHelper.EVENT_LANGUAGE_CHANGED, any()) }
    }

    @Test
    fun `logEvent with empty params calls Firebase exactly once`() {
        helper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)

        verify(exactly = 1) { firebaseAnalytics.logEvent(AnalyticsHelper.EVENT_APP_OPEN, any()) }
    }

    @Test
    fun `logEvent with multiple params calls Firebase exactly once`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_CHAPTER_OPENED,
            mapOf(
                AnalyticsHelper.PARAM_BOOK to "Genesis",
                AnalyticsHelper.PARAM_CHAPTER to "1",
            ),
        )

        verify(exactly = 1) {
            firebaseAnalytics.logEvent(AnalyticsHelper.EVENT_CHAPTER_OPENED, any())
        }
    }

    @Test
    fun `logEvent does not call crashlytics`() {
        helper.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT)

        verify(exactly = 0) { crashlytics.recordException(any()) }
        verify(exactly = 0) { crashlytics.log(any()) }
    }

    // -------------------------------------------------------------------------
    // setCurrentScreen
    // -------------------------------------------------------------------------

    @Test
    fun `setCurrentScreen logs SCREEN_VIEW event with Firebase`() {
        helper.setCurrentScreen("ConversationsScreen")

        verify { firebaseAnalytics.logEvent(FirebaseAnalytics.Event.SCREEN_VIEW, any()) }
    }

    @Test
    fun `setCurrentScreen calls Firebase exactly once`() {
        helper.setCurrentScreen("SettingsScreen")

        verify(exactly = 1) { firebaseAnalytics.logEvent(FirebaseAnalytics.Event.SCREEN_VIEW, any()) }
    }

    @Test
    fun `setCurrentScreen does not touch crashlytics`() {
        helper.setCurrentScreen("ChatScreen")

        verify(exactly = 0) { crashlytics.recordException(any()) }
    }

    // -------------------------------------------------------------------------
    // recordNonFatalException
    // -------------------------------------------------------------------------

    @Test
    fun `recordNonFatalException calls crashlytics recordException`() {
        val ex = RuntimeException("test")

        helper.recordNonFatalException(ex)

        verify { crashlytics.recordException(ex) }
    }

    @Test
    fun `recordNonFatalException logs message to crashlytics when provided`() {
        val ex = IllegalStateException("illegal state")
        val message = "context for this error"

        helper.recordNonFatalException(ex, message)

        verify { crashlytics.log(message) }
        verify { crashlytics.recordException(ex) }
    }

    @Test
    fun `recordNonFatalException does not call crashlytics log when message is null`() {
        val ex = RuntimeException("no message")

        helper.recordNonFatalException(ex, null)

        verify(exactly = 0) { crashlytics.log(any()) }
        verify { crashlytics.recordException(ex) }
    }

    @Test
    fun `recordNonFatalException logs message before recording exception`() {
        val callOrder = mutableListOf<String>()
        every { crashlytics.log(any()) } answers { callOrder.add("log") }
        every { crashlytics.recordException(any()) } answers { callOrder.add("record") }

        helper.recordNonFatalException(RuntimeException("err"), "msg")

        assertEquals(listOf("log", "record"), callOrder)
    }

    @Test
    fun `recordNonFatalException does not call firebaseAnalytics`() {
        helper.recordNonFatalException(RuntimeException("oops"))

        verify(exactly = 0) { firebaseAnalytics.logEvent(any(), any()) }
    }
}

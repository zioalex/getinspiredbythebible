package com.bibleinspiration.analytics

import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics
import io.mockk.every
import io.mockk.just
import io.mockk.mockk
import io.mockk.runs
import io.mockk.slot
import io.mockk.verify
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import android.os.Bundle

/**
 * Unit tests for [FirebaseAnalyticsHelper].
 *
 * Firebase SDK objects ([FirebaseAnalytics] and [FirebaseCrashlytics]) are mocked with MockK
 * so that no real Firebase calls are made during tests.
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
    fun `logEvent calls firebaseAnalytics logEvent with correct name`() {
        helper.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT)

        verify { firebaseAnalytics.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT, any()) }
    }

    @Test
    fun `logEvent forwards params as bundle entries`() {
        val bundleSlot = slot<Bundle>()
        every { firebaseAnalytics.logEvent(any(), capture(bundleSlot)) } just runs

        helper.logEvent(
            AnalyticsHelper.EVENT_LANGUAGE_CHANGED,
            mapOf(AnalyticsHelper.PARAM_LANGUAGE to "fr"),
        )

        assertEquals("fr", bundleSlot.captured.getString(AnalyticsHelper.PARAM_LANGUAGE))
    }

    @Test
    fun `logEvent with empty params still calls Firebase with an empty bundle`() {
        val bundleSlot = slot<Bundle>()
        every { firebaseAnalytics.logEvent(any(), capture(bundleSlot)) } just runs

        helper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)

        verify { firebaseAnalytics.logEvent(AnalyticsHelper.EVENT_APP_OPEN, any()) }
        assertEquals(0, bundleSlot.captured.size())
    }

    @Test
    fun `logEvent with multiple params puts all entries in the bundle`() {
        val bundleSlot = slot<Bundle>()
        every { firebaseAnalytics.logEvent(any(), capture(bundleSlot)) } just runs

        helper.logEvent(
            AnalyticsHelper.EVENT_CHAPTER_OPENED,
            mapOf(
                AnalyticsHelper.PARAM_BOOK to "Genesis",
                AnalyticsHelper.PARAM_CHAPTER to "1",
            ),
        )

        val bundle = bundleSlot.captured
        assertEquals("Genesis", bundle.getString(AnalyticsHelper.PARAM_BOOK))
        assertEquals("1", bundle.getString(AnalyticsHelper.PARAM_CHAPTER))
    }

    // -------------------------------------------------------------------------
    // setCurrentScreen
    // -------------------------------------------------------------------------

    @Test
    fun `setCurrentScreen logs SCREEN_VIEW event`() {
        helper.setCurrentScreen("ConversationsScreen")

        verify { firebaseAnalytics.logEvent(FirebaseAnalytics.Event.SCREEN_VIEW, any()) }
    }

    @Test
    fun `setCurrentScreen puts screen name in bundle`() {
        val bundleSlot = slot<Bundle>()
        every { firebaseAnalytics.logEvent(any(), capture(bundleSlot)) } just runs

        helper.setCurrentScreen("SettingsScreen")

        assertEquals("SettingsScreen", bundleSlot.captured.getString(FirebaseAnalytics.Param.SCREEN_NAME))
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
}

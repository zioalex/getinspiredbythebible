package org.voxquieta.app.analytics

import com.google.firebase.analytics.FirebaseAnalytics
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for [FirebaseAnalyticsHelper].
 *
 * We construct [FirebaseAnalyticsHelper] via its lambda constructor so that no real
 * Firebase SDK classes are involved and [android.os.Bundle] is never instantiated
 * (Bundle's constructor throws RuntimeException("Stub!") in JVM unit tests without
 * Robolectric).  Bundle construction is delegated entirely to the production lambda
 * inside the secondary constructor, which is never called during tests.
 */
class FirebaseAnalyticsHelperTest {

    private data class LogEventCall(val name: String, val params: Map<String, String>)

    private val loggedEvents = mutableListOf<LogEventCall>()
    private val recordedExceptions = mutableListOf<Throwable>()
    private val loggedMessages = mutableListOf<String>()

    private lateinit var helper: FirebaseAnalyticsHelper

    @Before
    fun setUp() {
        loggedEvents.clear()
        recordedExceptions.clear()
        loggedMessages.clear()

        helper = FirebaseAnalyticsHelper(
            logEventFn = { name, params -> loggedEvents.add(LogEventCall(name, params)) },
            recordExceptionFn = { throwable -> recordedExceptions.add(throwable) },
            logMessageFn = { message -> loggedMessages.add(message) },
        )
    }

    // -------------------------------------------------------------------------
    // logEvent
    // -------------------------------------------------------------------------

    @Test
    fun `logEvent fires with correct event name`() {
        helper.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT)

        assertEquals(1, loggedEvents.size)
        assertEquals(AnalyticsHelper.EVENT_MESSAGE_SENT, loggedEvents[0].name)
    }

    @Test
    fun `logEvent with params includes param in map`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_LANGUAGE_CHANGED,
            mapOf(AnalyticsHelper.PARAM_LANGUAGE to "fr"),
        )

        assertEquals(1, loggedEvents.size)
        assertEquals(AnalyticsHelper.EVENT_LANGUAGE_CHANGED, loggedEvents[0].name)
        assertEquals("fr", loggedEvents[0].params[AnalyticsHelper.PARAM_LANGUAGE])
    }

    @Test
    fun `logEvent with empty params fires once with empty map`() {
        helper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)

        assertEquals(1, loggedEvents.size)
        assertEquals(0, loggedEvents[0].params.size)
    }

    @Test
    fun `logEvent with multiple params puts all entries in map`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_CHAPTER_OPENED,
            mapOf(
                AnalyticsHelper.PARAM_BOOK to "Genesis",
                AnalyticsHelper.PARAM_CHAPTER to "1",
            ),
        )

        assertEquals(1, loggedEvents.size)
        assertEquals("Genesis", loggedEvents[0].params[AnalyticsHelper.PARAM_BOOK])
        assertEquals("1", loggedEvents[0].params[AnalyticsHelper.PARAM_CHAPTER])
    }

    @Test
    fun `logEvent does not touch crashlytics`() {
        helper.logEvent(AnalyticsHelper.EVENT_MESSAGE_SENT)

        assertEquals(0, recordedExceptions.size)
        assertEquals(0, loggedMessages.size)
    }

    // -------------------------------------------------------------------------
    // setCurrentScreen
    // -------------------------------------------------------------------------

    @Test
    fun `setCurrentScreen logs SCREEN_VIEW event`() {
        helper.setCurrentScreen("ConversationsScreen")

        assertEquals(1, loggedEvents.size)
        assertEquals(FirebaseAnalytics.Event.SCREEN_VIEW, loggedEvents[0].name)
    }

    @Test
    fun `setCurrentScreen passes screen name as param`() {
        helper.setCurrentScreen("SettingsScreen")

        assertEquals(
            "SettingsScreen",
            loggedEvents[0].params[FirebaseAnalytics.Param.SCREEN_NAME],
        )
    }

    @Test
    fun `setCurrentScreen does not touch crashlytics`() {
        helper.setCurrentScreen("ChatScreen")

        assertEquals(0, recordedExceptions.size)
        assertEquals(0, loggedMessages.size)
    }

    // -------------------------------------------------------------------------
    // recordNonFatalException
    // -------------------------------------------------------------------------

    @Test
    fun `recordNonFatalException calls recordException`() {
        val ex = RuntimeException("test")

        helper.recordNonFatalException(ex)

        assertEquals(1, recordedExceptions.size)
        assertEquals(ex, recordedExceptions[0])
    }

    @Test
    fun `recordNonFatalException logs message when provided`() {
        val ex = IllegalStateException("illegal state")
        val message = "context for this error"

        helper.recordNonFatalException(ex, message)

        assertEquals(1, loggedMessages.size)
        assertEquals(message, loggedMessages[0])
        assertEquals(1, recordedExceptions.size)
        assertEquals(ex, recordedExceptions[0])
    }

    @Test
    fun `recordNonFatalException does not log message when null`() {
        helper.recordNonFatalException(RuntimeException("no message"), null)

        assertEquals(0, loggedMessages.size)
        assertEquals(1, recordedExceptions.size)
    }

    @Test
    fun `recordNonFatalException logs message before recording exception`() {
        val callOrder = mutableListOf<String>()
        val ordered = FirebaseAnalyticsHelper(
            logEventFn = { _, _ -> },
            recordExceptionFn = { callOrder.add("record") },
            logMessageFn = { callOrder.add("log") },
        )

        ordered.recordNonFatalException(RuntimeException("err"), "msg")

        assertEquals(listOf("log", "record"), callOrder)
    }

    @Test
    fun `recordNonFatalException does not call logEventFn`() {
        helper.recordNonFatalException(RuntimeException("oops"))

        assertEquals(0, loggedEvents.size)
    }
}

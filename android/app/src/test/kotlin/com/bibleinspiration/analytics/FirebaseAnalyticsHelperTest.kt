package com.bibleinspiration.analytics

import android.os.Bundle
import com.google.firebase.analytics.FirebaseAnalytics
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for [FirebaseAnalyticsHelper].
 *
 * Rather than mocking the final Firebase SDK classes (which throws in JVM unit tests without
 * the MockK Java agent), we construct [FirebaseAnalyticsHelper] via its lambda constructor.
 * This lets us capture calls at the boundary without any mocking framework limitations.
 */
class FirebaseAnalyticsHelperTest {

    // Captured call records
    private data class LogEventCall(val name: String, val bundle: Bundle)
    private data class RecordExceptionCall(val throwable: Throwable)
    private data class LogMessageCall(val message: String)

    private val loggedEvents = mutableListOf<LogEventCall>()
    private val recordedExceptions = mutableListOf<RecordExceptionCall>()
    private val loggedMessages = mutableListOf<LogMessageCall>()

    private lateinit var helper: FirebaseAnalyticsHelper

    @Before
    fun setUp() {
        loggedEvents.clear()
        recordedExceptions.clear()
        loggedMessages.clear()

        helper = FirebaseAnalyticsHelper(
            logEventFn = { name, bundle -> loggedEvents.add(LogEventCall(name, bundle)) },
            recordExceptionFn = { throwable -> recordedExceptions.add(RecordExceptionCall(throwable)) },
            logMessageFn = { message -> loggedMessages.add(LogMessageCall(message)) },
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
    fun `logEvent with params includes param in bundle`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_LANGUAGE_CHANGED,
            mapOf(AnalyticsHelper.PARAM_LANGUAGE to "fr"),
        )

        assertEquals(1, loggedEvents.size)
        assertEquals(AnalyticsHelper.EVENT_LANGUAGE_CHANGED, loggedEvents[0].name)
        assertEquals("fr", loggedEvents[0].bundle.getString(AnalyticsHelper.PARAM_LANGUAGE))
    }

    @Test
    fun `logEvent with empty params fires once with empty bundle`() {
        helper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)

        assertEquals(1, loggedEvents.size)
        assertEquals(0, loggedEvents[0].bundle.size())
    }

    @Test
    fun `logEvent with multiple params puts all entries in bundle`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_CHAPTER_OPENED,
            mapOf(
                AnalyticsHelper.PARAM_BOOK to "Genesis",
                AnalyticsHelper.PARAM_CHAPTER to "1",
            ),
        )

        assertEquals(1, loggedEvents.size)
        val bundle = loggedEvents[0].bundle
        assertEquals("Genesis", bundle.getString(AnalyticsHelper.PARAM_BOOK))
        assertEquals("1", bundle.getString(AnalyticsHelper.PARAM_CHAPTER))
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
    fun `setCurrentScreen puts screen name in bundle`() {
        helper.setCurrentScreen("SettingsScreen")

        assertEquals(
            "SettingsScreen",
            loggedEvents[0].bundle.getString(FirebaseAnalytics.Param.SCREEN_NAME),
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
        assertEquals(ex, recordedExceptions[0].throwable)
    }

    @Test
    fun `recordNonFatalException logs message when provided`() {
        val ex = IllegalStateException("illegal state")
        val message = "context for this error"

        helper.recordNonFatalException(ex, message)

        assertEquals(1, loggedMessages.size)
        assertEquals(message, loggedMessages[0].message)
        assertEquals(1, recordedExceptions.size)
        assertEquals(ex, recordedExceptions[0].throwable)
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

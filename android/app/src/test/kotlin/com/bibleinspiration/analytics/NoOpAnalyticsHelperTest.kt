package com.bibleinspiration.analytics

import io.mockk.mockk
import io.mockk.verify
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Unit tests for [NoOpAnalyticsHelper].
 *
 * The no-op implementation must never throw, must silently accept any input,
 * and is used exclusively in debug builds to prevent any Firebase traffic.
 */
class NoOpAnalyticsHelperTest {

    private val helper = NoOpAnalyticsHelper()

    @Test
    fun `logEvent does not throw for empty params`() {
        helper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)
    }

    @Test
    fun `logEvent does not throw with params`() {
        helper.logEvent(
            AnalyticsHelper.EVENT_SCREEN_VIEW,
            mapOf(AnalyticsHelper.PARAM_SCREEN_NAME to "ConversationsScreen"),
        )
    }

    @Test
    fun `logEvent does not throw for all defined event constants`() {
        val events = listOf(
            AnalyticsHelper.EVENT_APP_OPEN,
            AnalyticsHelper.EVENT_SCREEN_VIEW,
            AnalyticsHelper.EVENT_MESSAGE_SENT,
            AnalyticsHelper.EVENT_RESPONSE_RECEIVED,
            AnalyticsHelper.EVENT_NEW_CONVERSATION,
            AnalyticsHelper.EVENT_CONVERSATION_OPENED,
            AnalyticsHelper.EVENT_LANGUAGE_CHANGED,
            AnalyticsHelper.EVENT_TRANSLATION_CHANGED,
            AnalyticsHelper.EVENT_VERSE_TAPPED,
            AnalyticsHelper.EVENT_CHAPTER_OPENED,
            AnalyticsHelper.EVENT_FEEDBACK_SUBMITTED,
            AnalyticsHelper.EVENT_CHURCH_FINDER_OPENED,
            AnalyticsHelper.EVENT_CHURCH_SEARCH_COMPLETED,
            AnalyticsHelper.EVENT_CONTACT_SUBMITTED,
        )
        events.forEach { event -> helper.logEvent(event) }
    }

    @Test
    fun `setCurrentScreen does not throw`() {
        helper.setCurrentScreen("SettingsScreen")
    }

    @Test
    fun `recordNonFatalException does not throw`() {
        val ex = RuntimeException("test exception")
        helper.recordNonFatalException(ex, "context message")
    }

    @Test
    fun `recordNonFatalException accepts null message`() {
        val ex = IllegalStateException("state error")
        helper.recordNonFatalException(ex, null)
    }

    @Test
    fun `logEvent accepts empty string event name without throwing`() {
        // Edge case: should never crash even with degenerate inputs.
        helper.logEvent("")
    }

    @Test
    fun `logEvent accepts params with empty values`() {
        helper.logEvent(AnalyticsHelper.EVENT_LANGUAGE_CHANGED, mapOf(AnalyticsHelper.PARAM_LANGUAGE to ""))
    }
}

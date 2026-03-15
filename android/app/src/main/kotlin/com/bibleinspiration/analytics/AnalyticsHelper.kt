package com.bibleinspiration.analytics

/**
 * Abstraction over Firebase Analytics so that:
 * - Debug builds use a no-op implementation (no data sent to Firebase)
 * - Release builds use the real Firebase Analytics implementation
 *
 * All event name constants live here to avoid magic strings scattered across the codebase.
 */
interface AnalyticsHelper {

    // -------------------------------------------------------------------------
    // Event name constants
    // -------------------------------------------------------------------------

    companion object {
        /** App opened / brought to foreground. Maps to Firebase's `app_open`. */
        const val EVENT_APP_OPEN = "app_open"

        /** User navigated to a named screen. */
        const val EVENT_SCREEN_VIEW = "screen_view"

        /** User sent a chat message to the AI assistant. */
        const val EVENT_MESSAGE_SENT = "message_sent"

        /** AI assistant response finished streaming successfully. */
        const val EVENT_RESPONSE_RECEIVED = "response_received"

        /** User tapped "New Conversation". */
        const val EVENT_NEW_CONVERSATION = "new_conversation"

        /** User opened a saved conversation from the history list. */
        const val EVENT_CONVERSATION_OPENED = "conversation_opened"

        /** User changed the UI language. */
        const val EVENT_LANGUAGE_CHANGED = "language_changed"

        /** User changed the Bible translation preference. */
        const val EVENT_TRANSLATION_CHANGED = "translation_changed"

        /** User tapped a Bible verse chip to expand it. */
        const val EVENT_VERSE_TAPPED = "verse_tapped"

        /** User opened the chapter reader from a verse chip. */
        const val EVENT_CHAPTER_OPENED = "chapter_opened"

        /** User submitted a thumbs-up or thumbs-down rating. */
        const val EVENT_FEEDBACK_SUBMITTED = "feedback_submitted"

        /** User opened the church-finder bottom sheet. */
        const val EVENT_CHURCH_FINDER_OPENED = "church_finder_opened"

        /** Church search completed (success path). */
        const val EVENT_CHURCH_SEARCH_COMPLETED = "church_search_completed"

        /** User submitted the contact form. */
        const val EVENT_CONTACT_SUBMITTED = "contact_submitted"

        // -------------------------------------------------------------------------
        // Parameter name constants
        // -------------------------------------------------------------------------

        const val PARAM_SCREEN_NAME = "screen_name"
        const val PARAM_LANGUAGE = "language"
        const val PARAM_TRANSLATION = "translation"
        const val PARAM_RATING = "rating"
        const val PARAM_BOOK = "book"
        const val PARAM_CHAPTER = "chapter"
        const val PARAM_LOCATION = "location"
        const val PARAM_RESULT_COUNT = "result_count"
    }

    /**
     * Records a named analytics event with optional key/value parameters.
     *
     * @param name   Event name — use the constants defined in [AnalyticsHelper].
     * @param params Optional map of parameter name → String value.
     */
    fun logEvent(name: String, params: Map<String, String> = emptyMap())

    /**
     * Sets the current screen name so subsequent events are attributed to it.
     *
     * @param screenName Human-readable screen name (e.g. "ConversationsScreen").
     */
    fun setCurrentScreen(screenName: String)

    /**
     * Records a non-fatal exception to Crashlytics so it appears in the dashboard
     * without crashing the app. No-op in debug builds.
     *
     * @param throwable The exception to report.
     * @param message   Optional context message logged alongside the exception.
     */
    fun recordNonFatalException(throwable: Throwable, message: String? = null)
}

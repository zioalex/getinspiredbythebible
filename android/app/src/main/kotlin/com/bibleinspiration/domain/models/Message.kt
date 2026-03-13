package com.bibleinspiration.domain.models

/**
 * Represents a single chat message in the conversation.
 *
 * @param id Locally-generated UUID for list keys and Room primary key.
 * @param role Either "user" or "assistant".
 * @param content Full text content.
 * @param verses Scripture verses referenced in this message (assistant only).
 * @param isStreaming True while the assistant is still generating this message.
 * @param isError True when the message represents a failed streaming attempt.
 * @param messageId Backend-assigned UUID for the assistant response. In-memory only
 *   (not persisted to Room). Populated when the SSE metadata event is received.
 * @param feedbackRating In-memory only (not persisted to Room). Set after the user
 *   taps 👍 or 👎. Null means no feedback has been given yet.
 */
data class Message(
    val id: String,
    val role: Role,
    val content: String,
    val verses: List<Verse> = emptyList(),
    val isStreaming: Boolean = false,
    val isError: Boolean = false,
    val messageId: String = "",
    val feedbackRating: FeedbackRating? = null,
) {
    enum class Role { USER, ASSISTANT }
}


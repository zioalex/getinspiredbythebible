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
 * @param messageId Backend-assigned message ID received in the SSE metadata chunk.
 * @param model LLM model name used to generate this message (from SSE metadata chunk).
 * @param scriptureContext Full scripture context from the SSE metadata chunk.
 */
data class Message(
    val id: String,
    val role: Role,
    val content: String,
    val verses: List<Verse> = emptyList(),
    val isStreaming: Boolean = false,
    val isError: Boolean = false,
    val messageId: String? = null,
    val model: String? = null,
    val scriptureContext: ScriptureContext? = null,
) {
    enum class Role { USER, ASSISTANT }
}

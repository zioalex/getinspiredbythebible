package org.voxquieta.app.domain.models

/**
 * Represents a conversation session in the app.
 *
 * @param id Unique identifier (UUID).
 * @param title First user message, truncated to 60 characters.
 * @param createdAt Unix epoch millis when the conversation was created.
 * @param updatedAt Unix epoch millis when the conversation was last modified.
 */
data class Conversation(
    val id: String,
    val title: String,
    val createdAt: Long,
    val updatedAt: Long,
)

package com.bibleinspiration.domain.models

/**
 * Parameters for a chat request to the backend.
 *
 * @param message User's message text.
 * @param conversationHistory Previous messages for multi-turn context.
 * @param preferredTranslation Optional Bible translation ID (e.g. "KJV"). Null = backend default.
 */
data class ChatRequest(
    val message: String,
    val conversationHistory: List<Message> = emptyList(),
    val preferredTranslation: String? = null,
)

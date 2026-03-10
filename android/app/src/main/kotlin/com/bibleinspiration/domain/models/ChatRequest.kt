package com.bibleinspiration.domain.models

/**
 * Parameters for a chat request to the backend.
 *
 * @param message User's message text.
 * @param conversationHistory Previous messages for multi-turn context.
 */
data class ChatRequest(
    val message: String,
    val conversationHistory: List<Message> = emptyList(),
)

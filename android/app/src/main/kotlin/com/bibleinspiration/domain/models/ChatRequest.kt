package com.bibleinspiration.domain.models

/**
 * Parameters for a chat request to the backend.
 *
 * @param message User's message text.
 * @param language BCP-47 language tag sent to the backend (e.g. "en", "ar").
 * @param conversationHistory Previous messages for multi-turn context.
 */
data class ChatRequest(
    val message: String,
    val language: String = "en",
    val conversationHistory: List<Message> = emptyList(),
)

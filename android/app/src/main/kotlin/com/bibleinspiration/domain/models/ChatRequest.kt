package com.bibleinspiration.domain.models

/**
 * Parameters for a chat request to the backend.
 *
 * @param message User's message text.
 * @param conversationHistory Previous messages for multi-turn context.
 * @param preferredTranslation Optional Bible translation ID (e.g. "KJV"). Null = backend default.
 * @param includeSearch Whether the backend should run a semantic Bible verse search before
 *   answering. Defaults to true.
 * @param sessionId Groups messages into a conversation for context continuity on the backend.
 *   A new UUID should be generated per conversation and reset when starting a new one.
 */
data class ChatRequest(
    val message: String,
    val conversationHistory: List<Message> = emptyList(),
    val preferredTranslation: String? = null,
    val includeSearch: Boolean = true,
    val sessionId: String? = null,
)

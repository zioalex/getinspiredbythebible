package com.bibleinspiration.domain.models

/**
 * A completed (non-streaming) chat response from the backend.
 */
data class ChatResponse(
    val message: String,
    val verses: List<Verse> = emptyList(),
)

/**
 * A single chunk emitted during SSE streaming.
 *
 * @param content Incremental text fragment. Empty string on the final [done] chunk.
 * @param done True on the terminal event (backend sends `[DONE]`).
 * @param verses Populated on the final chunk with referenced verses.
 * @param messageId Backend-assigned UUID for this response. Populated from metadata event.
 * @param model The LLM model used for generation. Populated from metadata event.
 */
data class StreamChunk(
    val content: String,
    val done: Boolean = false,
    val verses: List<Verse> = emptyList(),
    val messageId: String = "",
    val model: String = "",
)

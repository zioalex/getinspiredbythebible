package org.voxquieta.app.domain.models

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
 * @param type Event type: "metadata", "content", "completion", or "" for legacy chunks.
 * @param versesCited Server-extracted verse citations from the completion event.
 * @param resolvedVerses Backend-resolved cited verses (with text) from the completion event.
 * @param correctedMessage Authoritative message body when grounding rewrote a fabricated/
 *   mismatched inline verse quote; null when nothing was corrected.
 * @param languageSuggestion ISO 639-1 code suggested for UI locale switch (null when no mismatch).
 */
data class StreamChunk(
    val content: String = "",
    val done: Boolean = false,
    val verses: List<Verse> = emptyList(),
    val messageId: String = "",
    val model: String = "",
    val detectedTranslation: String = "",
    val type: String = "",
    val versesCited: List<String> = emptyList(),
    val resolvedVerses: List<Verse> = emptyList(),
    val correctedMessage: String? = null,
    val languageSuggestion: String? = null,
)

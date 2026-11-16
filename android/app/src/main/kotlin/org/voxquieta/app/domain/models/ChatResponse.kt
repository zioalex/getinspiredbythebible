package org.voxquieta.app.domain.models

/**
 * A completed (non-streaming) chat response from the backend.
 */
data class ChatResponse(
    val message: String,
    val verses: List<Verse> = emptyList(),
    val crisisResources: CrisisResources? = null,
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
 * @param followUps Suggested follow-up questions from the completion event (BITB-149).
 * @param crisisResources Emergency/crisis contacts; set only on a `crisis_resources` event (BITB-255).
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
    val followUps: List<String> = emptyList(),
    val languageSuggestion: String? = null,
    val crisisResources: CrisisResources? = null,
    /** BITB-320: text of a `type="error"` event; empty otherwise. */
    val errorMessage: String = "",
    /** BITB-320: true on an `error` event sent after content was already streamed. */
    val partial: Boolean = false,
)

/** BITB-320: what to send to `chat/finalize` after a stream ended without `completion`. */
data class FinalizeRequest(
    val message: String,
    val assistantText: String,
    val conversationHistory: List<Message> = emptyList(),
    val preferredTranslation: String? = null,
    val language: String? = null,
    val sessionId: String,
    val messageId: String? = null,
    /** "eof" | "error_event" | "network_error" | "timeout". */
    val reason: String,
)

/** BITB-320: the recovered completion fields plus whether the reply looks cut off. */
data class FinalizeResult(
    val versesCited: List<String> = emptyList(),
    val resolvedVerses: List<Verse> = emptyList(),
    val correctedMessage: String? = null,
    val followUps: List<String> = emptyList(),
    val truncated: Boolean = false,
)

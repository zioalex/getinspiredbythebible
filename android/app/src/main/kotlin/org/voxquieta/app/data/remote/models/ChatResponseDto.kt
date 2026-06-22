package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Non-streaming response from `POST /api/v1/chat`. */
@Serializable
data class ChatResponseDto(
    @SerialName("message") val message: String,
    @SerialName("verses") val verses: List<VerseDto> = emptyList(),
)

/** A single verse as returned by the backend. */
@Serializable
data class VerseDto(
    @SerialName("book") val book: String,
    @SerialName("chapter") val chapter: Int,
    @SerialName("verse") val verse: Int,
    @SerialName("text") val text: String,
    @SerialName("translation") val translation: String = "kjv",
    @SerialName("relevance_score") val relevanceScore: Float = 0f,
    @SerialName("localized_book") val localizedBook: String? = null,
)

/** Single SSE chunk from `POST /api/v1/chat/stream`. */
@Serializable
data class StreamChunkDto(
    @SerialName("type") val type: String = "",
    @SerialName("content") val content: String = "",
    @SerialName("done") val done: Boolean = false,
    @SerialName("verses") val verses: List<VerseDto> = emptyList(),
    @SerialName("message_id") val messageId: String = "",
    @SerialName("model") val model: String = "",
    @SerialName("detected_translation") val detectedTranslation: String = "",
    /** Server-extracted verse citations (from completion event). */
    @SerialName("verses_cited") val versesCited: List<String> = emptyList(),
    /** Backend-resolved cited verses (with text) from the completion event. */
    @SerialName("resolved_verses") val resolvedVerses: List<VerseDto> = emptyList(),
    /**
     * Authoritative message body, set only when post-generation grounding rewrote a
     * fabricated/mismatched inline verse quote to the canonical scripture text.
     * When present it replaces the streamed content. Null when nothing was corrected.
     */
    @SerialName("corrected_message") val correctedMessage: String? = null,
    /** References that were corrected, with the reason (completion event). */
    @SerialName("corrections") val corrections: List<CorrectionDto> = emptyList(),
    /**
     * Suggested language switch when the user typed in a language different from their
     * selected UI language. Populated in the metadata event. Null when no mismatch.
     */
    @SerialName("language_suggestion") val languageSuggestion: String? = null,
)

/** A single scripture-fidelity correction reported in the completion event. */
@Serializable
data class CorrectionDto(
    @SerialName("reference") val reference: String = "",
    @SerialName("reason") val reason: String = "",
)

/**
 * Metadata event emitted by the SSE stream before any content chunks.
 * Contains message_id, provider, model, and detected translation.
 */
@Serializable
data class MetadataChunkDto(
    @SerialName("type") val type: String = "",
    @SerialName("message_id") val messageId: String = "",
    @SerialName("provider") val provider: String = "",
    @SerialName("model") val model: String = "",
    @SerialName("detected_translation") val detectedTranslation: String? = null,
)

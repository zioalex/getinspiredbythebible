package com.bibleinspiration.data.remote.models

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
)

/** Single SSE chunk from `POST /api/v1/chat/stream`.
 *
 * Handles all chunk types emitted by the backend:
 * - content chunk: `{"type": "content", "content": "..."}`
 * - metadata chunk: `{"type": "metadata", "message_id": "...", "scripture_context": {...}, "model": "..."}`
 * - legacy content chunk (no type): `{"content": "...", "done": false}`
 * - error chunk: `{"type": "error", "error": "...", "error_code": "..."}`
 */
@Serializable
data class StreamChunkDto(
    // Legacy fields (kept for backwards compatibility)
    @SerialName("content") val content: String = "",
    @SerialName("done") val done: Boolean = false,
    @SerialName("verses") val verses: List<VerseDto> = emptyList(),
    // New fields
    @SerialName("type") val type: String? = null,
    @SerialName("message_id") val messageId: String? = null,
    @SerialName("model") val model: String? = null,
    @SerialName("provider") val provider: String? = null,
    @SerialName("detected_translation") val detectedTranslation: String? = null,
    @SerialName("translation_info") val translationInfo: TranslationInfoDto? = null,
    @SerialName("scripture_context") val scriptureContext: ScriptureContextDto? = null,
    // Error chunk fields
    @SerialName("error") val error: String? = null,
    @SerialName("error_code") val errorCode: String? = null,
)

/**
 * Translation info returned inside a metadata SSE chunk.
 */
@Serializable
data class TranslationInfoDto(
    @SerialName("id") val id: String = "",
    @SerialName("name") val name: String = "",
    @SerialName("language") val language: String = "",
)

/**
 * Scripture context returned inside a metadata SSE chunk.
 *
 * Mirrors the backend `SearchResults` model:
 * `{"query": "...", "verses": [...], "passages": [...]}`
 */
@Serializable
data class ScriptureContextDto(
    @SerialName("query") val query: String? = null,
    @SerialName("verses") val verses: List<ScriptureVerseDto> = emptyList(),
    @SerialName("passages") val passages: List<PassageDto> = emptyList(),
)

/**
 * A Bible passage (multi-verse block) inside [ScriptureContextDto].
 * Passages are not yet displayed in the Android UI; reserved for future use.
 */
@Serializable
data class PassageDto(
    @SerialName("book") val book: String = "",
    @SerialName("chapter") val chapter: Int = 0,
    @SerialName("text") val text: String = "",
    @SerialName("translation") val translation: String = "kjv",
)

/**
 * A single verse result inside [ScriptureContextDto].
 *
 * Mirrors the backend `VerseResult` pydantic model.
 */
@Serializable
data class ScriptureVerseDto(
    @SerialName("book") val book: String,
    @SerialName("chapter") val chapter: Int,
    @SerialName("verse") val verse: Int,
    @SerialName("text") val text: String,
    @SerialName("translation") val translation: String? = null,
    @SerialName("reference") val reference: String? = null,
    @SerialName("localized_book") val localizedBook: String? = null,
    @SerialName("similarity") val similarity: Float? = null,
)

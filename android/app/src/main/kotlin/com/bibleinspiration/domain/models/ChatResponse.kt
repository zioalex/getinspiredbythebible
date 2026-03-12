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
 * @param content Incremental text fragment. Empty string for non-content chunks.
 * @param done True on the terminal event (backend sends `[DONE]`).
 * @param verses Populated on the final chunk with referenced verses (legacy support).
 * @param type Chunk type discriminator: `"content"`, `"metadata"`, `"error"`, or null (legacy).
 * @param messageId Unique ID for the assistant message — populated on metadata chunks.
 * @param model Model name used to generate the response — populated on metadata chunks.
 * @param scriptureContext Scripture search results — populated on metadata chunks.
 */
data class StreamChunk(
    val content: String = "",
    val done: Boolean = false,
    val verses: List<Verse> = emptyList(),
    val type: String? = null,
    val messageId: String? = null,
    val model: String? = null,
    val scriptureContext: ScriptureContext? = null,
)

/**
 * Scripture search context returned in a metadata SSE chunk.
 *
 * @param verses List of relevant Bible verses found by the semantic search.
 * @param query The original query used for the scripture search.
 */
data class ScriptureContext(
    val verses: List<ScriptureVerse> = emptyList(),
    val query: String? = null,
)

/**
 * A single scripture verse result within [ScriptureContext].
 *
 * @param book Book name (e.g. "John").
 * @param chapter Chapter number.
 * @param verse Verse number.
 * @param text Verse text content.
 * @param translation Translation code (e.g. "kjv", "NIV").
 * @param reference Human-readable reference string (e.g. "John 3:16").
 * @param similarity Semantic similarity score from the vector search (0..1).
 */
data class ScriptureVerse(
    val book: String,
    val chapter: Int,
    val verse: Int,
    val text: String,
    val translation: String? = null,
    val reference: String? = null,
    val similarity: Float? = null,
)

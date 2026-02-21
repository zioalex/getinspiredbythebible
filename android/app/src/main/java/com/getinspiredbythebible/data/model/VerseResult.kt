package com.getinspiredbythebible.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Represents a single Bible verse returned by the backend, including semantic similarity score.
 * Used both in chat responses and standalone scripture search results.
 */
@JsonClass(generateAdapter = true)
data class VerseResult(
    @Json(name = "book") val book: String,
    @Json(name = "chapter") val chapter: Int,
    @Json(name = "verse") val verse: Int,
    @Json(name = "text") val text: String,
    @Json(name = "similarity") val similarity: Double,
)

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

/** Single SSE chunk from `POST /api/v1/chat/stream`. */
@Serializable
data class StreamChunkDto(
    @SerialName("content") val content: String = "",
    @SerialName("done") val done: Boolean = false,
    @SerialName("verses") val verses: List<VerseDto> = emptyList(),
)

package com.getinspiredbythebible.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Response body from POST /api/v1/chat.
 *
 * @param response The AI-generated, Bible-grounded encouragement text.
 * @param verses List of relevant Bible verses with similarity scores.
 * @param sessionId UUID that can be sent in subsequent requests to maintain context.
 */
@JsonClass(generateAdapter = true)
data class ChatResponse(
    @Json(name = "response") val response: String,
    @Json(name = "verses") val verses: List<VerseResult> = emptyList(),
    @Json(name = "session_id") val sessionId: String,
)

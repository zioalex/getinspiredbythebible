package com.getinspiredbythebible.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Request body for POST /api/v1/chat.
 *
 * @param message The user's message / prayer request.
 * @param sessionId Optional UUID to maintain conversation context across requests.
 */
@JsonClass(generateAdapter = true)
data class ChatRequest(
    @Json(name = "message") val message: String,
    @Json(name = "session_id") val sessionId: String? = null,
)

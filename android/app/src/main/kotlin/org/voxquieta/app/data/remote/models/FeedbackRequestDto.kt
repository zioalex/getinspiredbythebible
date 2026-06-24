package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Request body for POST /api/v1/feedback.
 *
 * The backend expects at minimum [messageId] and [rating]; the remaining
 * fields provide extra context for quality-improvement analysis.
 */
@Serializable
data class FeedbackRequestDto(
    @SerialName("message_id") val messageId: String,
    @SerialName("rating") val rating: String,          // "positive" or "negative"
    @SerialName("user_message") val userMessage: String = "",
    @SerialName("assistant_response") val assistantResponse: String = "",
    @SerialName("comment") val comment: String? = null,
    @SerialName("reason") val reason: String? = null,
)

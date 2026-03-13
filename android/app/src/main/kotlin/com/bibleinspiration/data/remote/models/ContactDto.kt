package com.bibleinspiration.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Subject categories that match the backend's Literal enum.
 * Sent as a plain string value in the JSON body.
 */
object ContactSubject {
    const val SPIRITUAL = "spiritual"
    const val BUG = "bug"
    const val FEATURE = "feature"
    const val FEEDBACK = "feedback"
    const val OTHER = "other"
}

@Serializable
data class ContactRequestDto(
    /** Optional reply-to email address. */
    @SerialName("email") val email: String? = null,
    /** Subject category — one of ContactSubject constants. */
    @SerialName("subject") val subject: String,
    /** The user's message text. */
    @SerialName("message") val message: String,
    /** Optional session identifier for analytics. */
    @SerialName("session_id") val sessionId: String? = null,
    /** Device / OS info — useful for bug reports. */
    @SerialName("user_agent") val userAgent: String? = null,
)

@Serializable
data class ContactResponseDto(
    @SerialName("id") val id: Int,
    @SerialName("subject") val subject: String,
    @SerialName("created_at") val createdAt: String,
)

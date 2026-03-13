package com.bibleinspiration.domain.models

/** Result of a feedback submission. */
data class FeedbackResult(
    val id: Int,
    val messageId: String,
    val rating: String,
)

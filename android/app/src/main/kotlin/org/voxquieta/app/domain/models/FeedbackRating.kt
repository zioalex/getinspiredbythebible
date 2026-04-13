package org.voxquieta.app.domain.models

/**
 * Rating for a message feedback submission.
 * Maps to the backend's "positive" / "negative" string values.
 */
enum class FeedbackRating {
    POSITIVE,
    NEGATIVE,
}

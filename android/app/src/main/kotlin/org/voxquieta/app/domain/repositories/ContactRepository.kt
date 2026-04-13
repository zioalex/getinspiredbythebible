package org.voxquieta.app.domain.repositories

/**
 * Repository interface for submitting contact form messages to the backend.
 */
interface ContactRepository {
    /**
     * Submits a contact form message.
     *
     * @param subject One of: "spiritual", "bug", "feature", "feedback", "other"
     * @param message The user's free-text message (non-blank).
     * @param email   Optional reply-to email address.
     * @param userAgent Optional device/OS string (useful for bug reports).
     * @return The server-assigned ID of the saved contact record.
     * @throws Exception on network or server error.
     */
    suspend fun submitContact(
        subject: String,
        message: String,
        email: String? = null,
        userAgent: String? = null,
    ): Int
}

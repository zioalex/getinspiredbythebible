package org.voxquieta.app.domain.models

/**
 * A Bible verse returned by the backend alongside a chat response.
 */
data class Verse(
    val book: String,
    val chapter: Int,
    val verse: Int,
    val text: String,
    val translation: String = "kjv",
    val relevanceScore: Float = 0f,
    val localizedBook: String? = null,
) {
    /** Human-readable reference, e.g. "John 3:16" (uses localized book name when available). */
    val reference: String get() = "${localizedBook ?: book} $chapter:$verse"
}

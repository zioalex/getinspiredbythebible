package org.voxquieta.app.data.local.mappers

import org.voxquieta.app.domain.models.Verse
import kotlinx.serialization.Serializable

/**
 * Data-layer DTO for JSON-serialising a [Verse].
 *
 * Kept separate from the domain model so the domain layer remains free of
 * kotlinx.serialization annotations.
 */
@Serializable
data class SerializableVerse(
    val book: String,
    val chapter: Int,
    val verse: Int,
    val text: String,
    val translation: String,
    val relevanceScore: Float,
    val localizedBook: String? = null,
)

fun Verse.toSerializable() = SerializableVerse(
    book = book,
    chapter = chapter,
    verse = verse,
    text = text,
    translation = translation,
    relevanceScore = relevanceScore,
    localizedBook = localizedBook,
)

fun SerializableVerse.toDomain() = Verse(
    book = book,
    chapter = chapter,
    verse = verse,
    text = text,
    translation = translation,
    relevanceScore = relevanceScore,
    localizedBook = localizedBook,
)

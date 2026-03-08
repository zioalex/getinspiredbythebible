package com.bibleinspiration.data.local.mappers

import com.bibleinspiration.domain.models.Verse
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
)

fun Verse.toSerializable() = SerializableVerse(
    book = book,
    chapter = chapter,
    verse = verse,
    text = text,
    translation = translation,
    relevanceScore = relevanceScore,
)

fun SerializableVerse.toDomain() = Verse(
    book = book,
    chapter = chapter,
    verse = verse,
    text = text,
    translation = translation,
    relevanceScore = relevanceScore,
)

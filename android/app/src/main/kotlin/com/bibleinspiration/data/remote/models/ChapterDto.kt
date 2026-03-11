package com.bibleinspiration.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ChapterVerseDto(
    @SerialName("verse_number") val verseNumber: Int,
    @SerialName("text") val text: String,
)

@Serializable
data class ChapterResponseDto(
    @SerialName("book") val book: String,
    @SerialName("chapter") val chapter: Int,
    @SerialName("verses") val verses: List<ChapterVerseDto>,
    @SerialName("translation") val translation: String? = null,
)

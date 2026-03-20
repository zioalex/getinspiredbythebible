package com.bibleinspiration.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ChapterVerseDto(
    @SerialName("verse") val verseNumber: Int,
    @SerialName("text") val text: String,
    @SerialName("reference") val reference: String? = null,
    @SerialName("book") val book: String? = null,
    @SerialName("localized_book") val localizedBook: String? = null,
    @SerialName("chapter") val chapter: Int? = null,
    @SerialName("translation") val translation: String? = null,
)

@Serializable
data class ChapterResponseDto(
    @SerialName("book") val book: String,
    @SerialName("chapter") val chapter: Int,
    @SerialName("verses") val verses: List<ChapterVerseDto>,
    @SerialName("translation") val translation: String? = null,
    @SerialName("localized_book") val localizedBook: String? = null,
    @SerialName("translation_name") val translationName: String? = null,
)

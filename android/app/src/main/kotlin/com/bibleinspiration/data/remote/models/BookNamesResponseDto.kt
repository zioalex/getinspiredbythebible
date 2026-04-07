package com.bibleinspiration.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class BookNamesResponseDto(
    @SerialName("localized_to_english") val localizedToEnglish: Map<String, String>,
    @SerialName("multi_word_names") val multiWordNames: List<String>,
)

package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** A single Bible translation returned by `GET /api/v1/scripture/translations`. */
@Serializable
data class TranslationDto(
    @SerialName("code") val id: String,
    @SerialName("name") val name: String,
    @SerialName("language") val language: String,
)

/** Wrapper for the translations list endpoint response. */
@Serializable
data class TranslationsResponseDto(
    @SerialName("translations") val translations: List<TranslationDto>,
)

package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ChurchSearchRequestDto(
    @SerialName("location") val location: String,
)

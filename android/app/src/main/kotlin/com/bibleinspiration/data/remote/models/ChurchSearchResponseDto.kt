package com.bibleinspiration.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ChurchDto(
    @SerialName("name") val name: String,
    @SerialName("address") val address: String? = null,
    @SerialName("city") val city: String? = null,
    @SerialName("state") val state: String? = null,
    @SerialName("country") val country: String? = null,
    @SerialName("website") val website: String? = null,
    @SerialName("phone") val phone: String? = null,
    @SerialName("email") val email: String? = null,
)

@Serializable
data class ChurchSearchResponseDto(
    @SerialName("churches") val churches: List<ChurchDto>,
    @SerialName("total") val total: Int,
    @SerialName("location") val location: String,
)

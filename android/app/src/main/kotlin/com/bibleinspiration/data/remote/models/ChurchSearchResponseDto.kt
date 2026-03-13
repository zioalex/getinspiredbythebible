package com.bibleinspiration.data.remote.models

import com.google.gson.annotations.SerializedName

data class ChurchDto(
    @SerializedName("name") val name: String,
    @SerializedName("address") val address: String?,
    @SerializedName("city") val city: String?,
    @SerializedName("state") val state: String?,
    @SerializedName("country") val country: String?,
    @SerializedName("website") val website: String?,
    @SerializedName("phone") val phone: String?,
    @SerializedName("email") val email: String?,
)

data class ChurchSearchResponseDto(
    @SerializedName("churches") val churches: List<ChurchDto>,
    @SerializedName("total") val total: Int,
    @SerializedName("location") val location: String,
)

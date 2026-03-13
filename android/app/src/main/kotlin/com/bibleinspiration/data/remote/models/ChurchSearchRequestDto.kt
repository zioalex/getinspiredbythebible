package com.bibleinspiration.data.remote.models

import com.google.gson.annotations.SerializedName

data class ChurchSearchRequestDto(
    @SerializedName("location") val location: String,
)

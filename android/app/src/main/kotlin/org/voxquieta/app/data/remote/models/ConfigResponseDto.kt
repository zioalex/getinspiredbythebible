package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// BITB-075: mirrors the `chat` block of the backend's GET /config response.
// Nullable + defaulted fields so an older/different backend payload still
// deserializes fine (the shared Json config already has
// ignoreUnknownKeys = true).
@Serializable
data class ConfigResponseDto(
    val chat: ConfigChatDto? = null,
)

@Serializable
data class ConfigChatDto(
    @SerialName("max_message_length") val maxMessageLength: Int? = null,
)

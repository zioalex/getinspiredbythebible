package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// BITB-075/BITB-156: mirrors the `chat` block of the backend's GET /config response.
// Nullable + defaulted fields so an older/different backend payload still
// deserializes fine (the shared Json config already has
// ignoreUnknownKeys = true).
@Serializable
data class ConfigResponseDto(
    val chat: ConfigChatDto? = null,
    // BITB-119: server-published feature flags. Absent (older backend) => treated as enabled.
    val features: ConfigFeaturesDto? = null,
)

@Serializable
data class ConfigFeaturesDto(
    // Fail open: only an explicit `false` hides the Listen button.
    @SerialName("tts_enabled") val ttsEnabled: Boolean? = null,
)

@Serializable
data class ConfigChatDto(
    @SerialName("max_message_length") val maxMessageLength: Int? = null,
    // BITB-156: server-published per-session message cap (settings.rate_limit_session_max_requests).
    @SerialName("session_max_requests") val sessionMaxRequests: Int? = null,
)

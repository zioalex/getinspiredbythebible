package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Request body for POST /api/v1/client-events (BITB-119, BITB-247): a read-aloud telemetry event.
 *
 * Carries only the event name, the language and three coarse enums; never message text, voice
 * names, a user-agent string or any identifier. The backend normalizes unknown enum values.
 */
@Serializable
data class ClientEventRequestDto(
    @SerialName("event") val event: String,
    @SerialName("locale") val locale: String,
    @SerialName("platform") val platform: String = PLATFORM_ANDROID,
    @SerialName("browser") val browser: String = BROWSER_APP,
    @SerialName("os") val os: String = OS_ANDROID,
) {
    companion object {
        const val PLATFORM_ANDROID = "android"
        const val BROWSER_APP = "app"
        const val OS_ANDROID = "android"
    }
}

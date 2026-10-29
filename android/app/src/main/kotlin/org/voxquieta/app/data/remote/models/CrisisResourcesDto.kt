package org.voxquieta.app.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Wire shape of the `crisis_resources` payload (BITB-251). Every field has a default so a
 * partially-populated payload still renders instead of being dropped. The same shape is
 * stored in Room (`MessageEntity.crisisJson`).
 */
@Serializable
data class CrisisResourcesDto(
    @SerialName("kind") val kind: String = "self_harm",
    @SerialName("country") val country: String? = null,
    @SerialName("country_source") val countrySource: String = "none",
    @SerialName("emergency") val emergency: CrisisEmergencyDto? = null,
    @SerialName("lines") val lines: List<CrisisLineDto> = emptyList(),
    @SerialName("international_url") val internationalUrl: String = "https://findahelpline.com",
    @SerialName("available_countries") val availableCountries: List<String> = emptyList(),
)

@Serializable
data class CrisisEmergencyDto(
    @SerialName("number") val number: String,
)

@Serializable
data class CrisisLineDto(
    @SerialName("name") val name: String,
    @SerialName("phone") val phone: String? = null,
    @SerialName("sms") val sms: String? = null,
    @SerialName("hours") val hours: String? = null,
    @SerialName("url") val url: String? = null,
    // Ops-only flag; ignored by the UI but tolerated on the wire.
    @SerialName("verified") val verified: Boolean = false,
)

package org.voxquieta.app.domain.models

/**
 * One crisis line shown in the [CrisisResources] card (BITB-251). [name] and [hours] are
 * already localized by the server; [phone] / [sms] are display strings (dialable form is
 * derived at tap time).
 */
data class CrisisLine(
    val name: String,
    val phone: String? = null,
    val sms: String? = null,
    val hours: String? = null,
    val url: String? = null,
)

/**
 * Emergency + crisis-line contacts the backend sends as the first event of a self-harm or
 * threat-to-others turn (BITB-251). Mirrors the web `CrisisResources` type.
 *
 * @param kind "self_harm" or "threat_to_others".
 * @param country ISO 3166-1 alpha-2 the contacts were picked for; null when international only.
 * @param countrySource "override" | "ip" | "locale" | "language_default" | "none".
 * @param emergencyNumber Local emergency number, null when unknown.
 * @param availableCountries Countries the "Not in X?" picker offers.
 */
data class CrisisResources(
    val kind: String,
    val country: String? = null,
    val countrySource: String = "none",
    val emergencyNumber: String? = null,
    val lines: List<CrisisLine> = emptyList(),
    val internationalUrl: String = DEFAULT_INTERNATIONAL_URL,
    val availableCountries: List<String> = emptyList(),
) {
    companion object {
        const val DEFAULT_INTERNATIONAL_URL = "https://findahelpline.com"
    }
}

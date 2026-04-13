package org.voxquieta.app.domain.models

/**
 * Domain model representing a church returned by the church-search endpoint.
 *
 * All optional fields may be null when the backend lacks data for a particular
 * directory entry.
 */
data class Church(
    val name: String,
    val address: String?,
    val city: String?,
    val state: String?,
    val country: String?,
    val website: String?,
    val phone: String?,
    val email: String?,
) {
    /** Human-readable location line, e.g. "Rome, Italy" or just "Rome". */
    val locationLine: String
        get() = listOfNotNull(city, state, country)
            .filter { it.isNotBlank() }
            .joinToString(", ")
}

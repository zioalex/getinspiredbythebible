package org.voxquieta.app.domain.models

/**
 * Parameters for a chat request to the backend.
 *
 * @param message User's message text.
 * @param conversationHistory Previous messages for multi-turn context.
 * @param preferredTranslation Optional Bible translation ID (e.g. "KJV"). Null = backend default.
 * @param includeSearch Whether to enable semantic search for relevant scripture. Defaults to true.
 * @param sessionId Stable UUID identifying this install for DAU/MAU analytics. Generated once
 *   on first launch and persisted in DataStore for the lifetime of the app installation.
 * @param language BCP-47 language code selected by the user (e.g. "it", "de"). When provided
 *   the backend uses this instead of auto-detecting the language from the message text, so
 *   responses are always in the user's chosen language regardless of what language they type in.
 * @param region ISO 3166-1 alpha-2 country used only to pick local emergency/crisis contacts
 *   (BITB-255). Never stored server-side.
 * @param regionOverride True only when the user corrected the country in the crisis card picker.
 */
data class ChatRequest(
    val message: String,
    val conversationHistory: List<Message> = emptyList(),
    val preferredTranslation: String? = null,
    val includeSearch: Boolean = true,
    val sessionId: String,
    val language: String? = null,
    /** BITB-255: ISO 3166-1 alpha-2 region (device locale, or the user's picker choice). */
    val region: String? = null,
    /** BITB-255: true when [region] is the user's explicit crisis-card picker choice. */
    val regionOverride: Boolean = false,
)

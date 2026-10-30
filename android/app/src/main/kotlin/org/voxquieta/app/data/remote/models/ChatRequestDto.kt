package org.voxquieta.app.data.remote.models

import kotlinx.serialization.EncodeDefault
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@OptIn(ExperimentalSerializationApi::class)
@Serializable
data class ChatRequestDto(
    @SerialName("message") val message: String,
    @SerialName("conversation_history") val conversationHistory: List<ConversationMessageDto> = emptyList(),
    @SerialName("preferred_translation") val preferredTranslation: String? = null,
    @SerialName("include_search") val includeSearch: Boolean = true,
    @SerialName("session_id") val sessionId: String,
    @SerialName("language") val language: String? = null,
    /** BITB-255: ISO 3166-1 alpha-2 used to pick local crisis contacts. Omitted when unknown. */
    @SerialName("region") val region: String? = null,
    /**
     * BITB-255: true only when the user picked a country in the crisis card's picker; then
     * [region] is that pick. `@EncodeDefault` because the app's Json uses encodeDefaults=false.
     */
    @EncodeDefault @SerialName("region_override") val regionOverride: Boolean = false,
    /** BITB-255: this client renders the structured crisis card. Always true. */
    @EncodeDefault @SerialName("supports_crisis_card") val supportsCrisisCard: Boolean = true,
)

@Serializable
data class ConversationMessageDto(
    @SerialName("role") val role: String,
    @SerialName("content") val content: String,
)

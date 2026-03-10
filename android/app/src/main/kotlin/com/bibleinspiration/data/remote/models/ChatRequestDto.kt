package com.bibleinspiration.data.remote.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ChatRequestDto(
    @SerialName("message") val message: String,
    @SerialName("conversation_history") val conversationHistory: List<ConversationMessageDto> = emptyList(),
    @SerialName("preferred_translation") val preferredTranslation: String? = null,
)

@Serializable
data class ConversationMessageDto(
    @SerialName("role") val role: String,
    @SerialName("content") val content: String,
)

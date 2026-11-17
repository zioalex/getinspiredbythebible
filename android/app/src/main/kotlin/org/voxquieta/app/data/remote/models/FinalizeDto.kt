package org.voxquieta.app.data.remote.models

import kotlinx.serialization.EncodeDefault
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Body of `POST /api/v1/chat/finalize` (BITB-320): the text the client actually received when a
 * stream ended without a `completion` event. The server returns the completion-event fields.
 */
@OptIn(ExperimentalSerializationApi::class)
@Serializable
data class FinalizeRequestDto(
    @SerialName("message") val message: String,
    @SerialName("assistant_text") val assistantText: String,
    @SerialName("conversation_history") val conversationHistory: List<ConversationMessageDto> = emptyList(),
    @SerialName("preferred_translation") val preferredTranslation: String? = null,
    @SerialName("language") val language: String? = null,
    @SerialName("session_id") val sessionId: String,
    /** From the stream's `metadata` event; the server ignores it when malformed or absent. */
    @SerialName("message_id") val messageId: String? = null,
    /** "eof" | "error_event" | "network_error" | "timeout" (telemetry). */
    @SerialName("reason") val reason: String,
    /** `@EncodeDefault`: the app's Json uses encodeDefaults=false, the server default is "web". */
    @EncodeDefault @SerialName("platform") val platform: String = "android",
)

/** Response of `POST /api/v1/chat/finalize`: the same fields as a `completion` SSE event. */
@Serializable
data class FinalizeResponseDto(
    @SerialName("verses_cited") val versesCited: List<String> = emptyList(),
    @SerialName("resolved_verses") val resolvedVerses: List<VerseDto> = emptyList(),
    @SerialName("corrected_message") val correctedMessage: String? = null,
    @SerialName("corrections") val corrections: List<CorrectionDto> = emptyList(),
    @SerialName("follow_ups") val followUps: List<String> = emptyList(),
    /** True when the reply looks cut off (no trailer and no sentence-final punctuation). */
    @SerialName("truncated") val truncated: Boolean = false,
)

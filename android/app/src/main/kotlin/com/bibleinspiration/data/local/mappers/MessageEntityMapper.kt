package com.bibleinspiration.data.local.mappers

import com.bibleinspiration.data.local.MessageEntity
import com.bibleinspiration.domain.models.Message
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import timber.log.Timber

private val json = Json { ignoreUnknownKeys = true }

/**
 * Maps a domain [Message] to a [MessageEntity] for Room storage.
 *
 * @param conversationId The owning conversation's ID.
 * @param createdAt Timestamp to attach; defaults to the current time.
 */
fun Message.toEntity(
    conversationId: String,
    createdAt: Long = System.currentTimeMillis(),
): MessageEntity = MessageEntity(
    id = id,
    conversationId = conversationId,
    role = role.name.lowercase(),
    content = content,
    versesJson = json.encodeToString(verses.map { it.toSerializable() }),
    createdAt = createdAt,
)

/**
 * Maps a [MessageEntity] back to the domain [Message].
 *
 * [versesJson] may be empty or malformed if a message was persisted by an older
 * version of the app or if the DB row is somehow corrupted. Rather than crashing
 * with a [kotlinx.serialization.SerializationException], we log the problem and
 * fall back to an empty verse list so the rest of the conversation still loads.
 */
fun MessageEntity.toDomain(): Message = Message(
    id = id,
    role = if (role == "user") Message.Role.USER else Message.Role.ASSISTANT,
    content = content,
    verses = try {
        json.decodeFromString<List<SerializableVerse>>(versesJson).map { it.toDomain() }
    } catch (e: Exception) {
        Timber.w(e, "Failed to deserialize versesJson for message %s; defaulting to empty list", id)
        emptyList()
    },
    isStreaming = false,
)

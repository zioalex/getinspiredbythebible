package com.bibleinspiration.data.local.mappers

import com.bibleinspiration.data.local.MessageEntity
import com.bibleinspiration.domain.models.Message
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

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
 */
fun MessageEntity.toDomain(): Message = Message(
    id = id,
    role = if (role == "user") Message.Role.USER else Message.Role.ASSISTANT,
    content = content,
    verses = json.decodeFromString<List<SerializableVerse>>(versesJson).map { it.toDomain() },
    isStreaming = false,
)

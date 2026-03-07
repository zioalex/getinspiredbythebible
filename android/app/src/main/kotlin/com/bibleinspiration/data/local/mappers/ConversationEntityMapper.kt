package com.bibleinspiration.data.local.mappers

import com.bibleinspiration.data.local.ConversationEntity
import com.bibleinspiration.domain.models.Conversation

/**
 * Maps a [ConversationEntity] to the domain [Conversation] model.
 */
fun ConversationEntity.toDomain(): Conversation = Conversation(
    id = id,
    title = title,
    createdAt = createdAt,
    updatedAt = updatedAt,
)

/**
 * Maps a domain [Conversation] to a [ConversationEntity] for Room storage.
 */
fun Conversation.toEntity(): ConversationEntity = ConversationEntity(
    id = id,
    title = title,
    createdAt = createdAt,
    updatedAt = updatedAt,
)

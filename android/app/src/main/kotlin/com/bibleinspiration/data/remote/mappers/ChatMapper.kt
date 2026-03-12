package com.bibleinspiration.data.remote.mappers

import com.bibleinspiration.data.remote.models.ChatRequestDto
import com.bibleinspiration.data.remote.models.ChatResponseDto
import com.bibleinspiration.data.remote.models.ConversationMessageDto
import com.bibleinspiration.data.remote.models.StreamChunkDto
import com.bibleinspiration.data.remote.models.VerseDto
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.ChatResponse
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.StreamChunk
import com.bibleinspiration.domain.models.Verse

fun ChatRequest.toDto(): ChatRequestDto = ChatRequestDto(
    message = message,
    conversationHistory = conversationHistory.map { it.toConversationMessageDto() },
    preferredTranslation = preferredTranslation?.ifBlank { null },
    includeSearch = includeSearch,
    sessionId = sessionId,
)

fun Message.toConversationMessageDto(): ConversationMessageDto = ConversationMessageDto(
    role = when (role) {
        Message.Role.USER -> "user"
        Message.Role.ASSISTANT -> "assistant"
    },
    content = content,
)

fun ChatResponseDto.toDomain(): ChatResponse = ChatResponse(
    message = message,
    verses = verses.map { it.toDomain() },
)

fun VerseDto.toDomain(): Verse = Verse(
    book = book,
    chapter = chapter,
    verse = verse,
    text = text,
    translation = translation,
    relevanceScore = relevanceScore,
)

fun StreamChunkDto.toDomain(): StreamChunk = StreamChunk(
    content = content,
    done = done,
    verses = verses.map { it.toDomain() },
    messageId = messageId,
    model = model,
)

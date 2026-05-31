package org.voxquieta.app.data.remote.mappers

import org.voxquieta.app.data.remote.models.ChatRequestDto
import org.voxquieta.app.data.remote.models.ChatResponseDto
import org.voxquieta.app.data.remote.models.ConversationMessageDto
import org.voxquieta.app.data.remote.models.StreamChunkDto
import org.voxquieta.app.data.remote.models.VerseDto
import org.voxquieta.app.domain.models.ChatRequest
import org.voxquieta.app.domain.models.ChatResponse
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.StreamChunk
import org.voxquieta.app.domain.models.Verse

fun ChatRequest.toDto(): ChatRequestDto = ChatRequestDto(
    message = message,
    conversationHistory = conversationHistory.map { it.toConversationMessageDto() },
    preferredTranslation = preferredTranslation?.ifBlank { null },
    includeSearch = includeSearch,
    sessionId = sessionId,
    language = language,
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
    localizedBook = localizedBook,
)

fun StreamChunkDto.toDomain(): StreamChunk = StreamChunk(
    content = content,
    done = done,
    verses = verses.map { it.toDomain() },
    messageId = messageId,
    model = model,
    detectedTranslation = detectedTranslation,
    type = type,
    versesCited = versesCited,
    resolvedVerses = resolvedVerses.map { it.toDomain() },
)

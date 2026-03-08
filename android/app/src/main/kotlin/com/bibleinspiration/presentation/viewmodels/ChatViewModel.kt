package com.bibleinspiration.presentation.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.domain.repositories.ChatRepository
import com.bibleinspiration.security.TurnstileManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import timber.log.Timber
import java.util.UUID
import javax.inject.Inject

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val currentLocale: String = "en",
    val isTurnstileReady: Boolean = false,
    /** ID of the currently active conversation; null when no conversation has started. */
    val currentConversationId: String? = null,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository,
    val turnstileManager: TurnstileManager,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            turnstileManager.tokenFlow.collect { token ->
                _uiState.update { it.copy(isTurnstileReady = token != null) }
            }
        }
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isBlank() || _uiState.value.isLoading) return

        val userMessage = Message(
            id = UUID.randomUUID().toString(),
            role = Message.Role.USER,
            content = trimmed,
        )
        val assistantId = UUID.randomUUID().toString()
        val assistantPlaceholder = Message(
            id = assistantId,
            role = Message.Role.ASSISTANT,
            content = "",
            isStreaming = true,
        )

        _uiState.update {
            it.copy(
                messages = it.messages + userMessage + assistantPlaceholder,
                isLoading = true,
                error = null,
            )
        }

        viewModelScope.launch {
            // Ensure a conversation row exists before persisting messages.
            val conversationId = ensureConversation(trimmed)

            // Persist the user message immediately.
            repository.saveMessage(conversationId, userMessage)

            val history = _uiState.value.messages
                .filter { !it.isStreaming }
                .dropLast(1) // exclude placeholder
                .takeLast(20) // cap history

            val request = ChatRequest(
                message = trimmed,
                language = _uiState.value.currentLocale,
                conversationHistory = history,
            )

            var accumulatedContent = ""
            var finalVerses: List<Verse> = emptyList()

            repository
                .chatStream(request)
                .catch { e ->
                    Timber.e(e, "chatStream error")
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages.map { msg ->
                                if (msg.id == assistantId) {
                                    msg.copy(
                                        content = accumulatedContent.ifBlank { "An error occurred. Please try again." },
                                        isStreaming = false,
                                    )
                                } else msg
                            },
                            isLoading = false,
                            error = e.message,
                        )
                    }
                }
                .onCompletion {
                    val finalAssistant = Message(
                        id = assistantId,
                        role = Message.Role.ASSISTANT,
                        content = accumulatedContent,
                        verses = finalVerses,
                        isStreaming = false,
                    )
                    // Persist finished assistant message and bump conversation timestamp.
                    repository.saveMessage(conversationId, finalAssistant)
                    repository.touchConversation(conversationId)

                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages.map { msg ->
                                if (msg.id == assistantId) finalAssistant else msg
                            },
                            isLoading = false,
                        )
                    }
                }
                .collect { chunk ->
                    accumulatedContent += chunk.content
                    if (chunk.done) finalVerses = chunk.verses

                    // Update the streaming message in-place on every chunk.
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages.map { msg ->
                                if (msg.id == assistantId) {
                                    msg.copy(content = accumulatedContent)
                                } else msg
                            },
                        )
                    }
                }
        }
    }

    /**
     * Returns the current conversation ID, creating a new conversation in Room
     * if one doesn't exist yet. Should be called on the first message of a session.
     */
    private suspend fun ensureConversation(firstMessageText: String): String {
        val existing = _uiState.value.currentConversationId
        if (existing != null) return existing

        val newId = UUID.randomUUID().toString()
        val conversation = repository.createConversation(id = newId, title = firstMessageText)
        _uiState.update { it.copy(currentConversationId = conversation.id) }
        return conversation.id
    }

    /** Load a previously saved conversation by ID and replace in-memory messages. */
    fun loadConversation(conversationId: String) {
        viewModelScope.launch {
            repository.observeMessages(conversationId).collect { messages ->
                _uiState.update { it.copy(messages = messages, currentConversationId = conversationId) }
            }
        }
    }

    /** Reset in-memory state and clear the active conversation ID (starts a new session). */
    fun startNewConversation() {
        _uiState.update {
            it.copy(
                messages = emptyList(),
                error = null,
                isLoading = false,
                currentConversationId = null,
            )
        }
    }

    fun setLocale(locale: String) {
        _uiState.update { it.copy(currentLocale = locale) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    /** Deletes the active conversation from DB and resets in-memory state. */
    fun clearConversation() {
        val conversationId = _uiState.value.currentConversationId
        _uiState.update { it.copy(messages = emptyList(), error = null, currentConversationId = null) }
        if (conversationId != null) {
            viewModelScope.launch {
                repository.deleteConversation(conversationId)
            }
        }
    }
}

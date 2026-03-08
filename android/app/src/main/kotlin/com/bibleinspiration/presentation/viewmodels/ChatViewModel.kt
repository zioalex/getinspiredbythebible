package com.bibleinspiration.presentation.viewmodels

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.bibleinspiration.R
import com.bibleinspiration.data.preferences.LanguagePreferences
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.domain.repositories.ChatRepository
import com.bibleinspiration.security.TurnstileManager
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
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
    private val languagePreferences: LanguagePreferences,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            turnstileManager.tokenFlow.collect { token ->
                _uiState.update { it.copy(isTurnstileReady = token != null) }
            }
        }
        // Restore persisted locale on startup.
        viewModelScope.launch {
            languagePreferences.languageFlow.collect { code ->
                _uiState.update { it.copy(currentLocale = code) }
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
            var didError = false

            repository
                .chatStream(request)
                .catch { e ->
                    Timber.e(e, "chatStream error")
                    didError = true
                    val errorMessage = mapExceptionToMessage(e)
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages.map { msg ->
                                if (msg.id == assistantId) {
                                    msg.copy(
                                        content = "",
                                        isStreaming = false,
                                        isError = true,
                                    )
                                } else msg
                            },
                            isLoading = false,
                            error = errorMessage,
                        )
                    }
                }
                .onCompletion {
                    if (!didError) {
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

    /**
     * Re-sends the last user message, discarding the empty/error assistant placeholder.
     * No-op if there is no prior user message or if the app is currently loading.
     */
    fun retryLastMessage() {
        if (_uiState.value.isLoading) return

        val messages = _uiState.value.messages
        val lastUserMessage = messages.lastOrNull { it.role == Message.Role.USER } ?: return

        // Remove the trailing assistant placeholder (error or blank) if present
        val trimmedMessages = messages.dropLastWhile { it.role == Message.Role.ASSISTANT }

        _uiState.update { it.copy(messages = trimmedMessages, error = null) }
        sendMessage(lastUserMessage.content)
    }

    /**
     * Updates the language locale in-memory and persists it via DataStore.
     */
    fun setLocale(locale: String) {
        _uiState.update { it.copy(currentLocale = locale) }
        viewModelScope.launch {
            languagePreferences.setLanguage(locale)
        }
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

    // ---------------------------------------------------------------------------
    // Private helpers
    // ---------------------------------------------------------------------------

    private fun mapExceptionToMessage(e: Throwable): String = when {
        e is UnknownHostException || e is ConnectException ->
            context.getString(R.string.error_network)
        e is SocketTimeoutException ->
            context.getString(R.string.error_timeout)
        e is HttpException ->
            context.getString(R.string.error_server)
        e is IOException ->
            context.getString(R.string.error_network)
        else ->
            context.getString(R.string.error_generic)
    }
}

package com.getinspiredbythebible.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.getinspiredbythebible.data.model.VerseResult
import com.getinspiredbythebible.data.repository.ChatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

// ── Domain model for UI ───────────────────────────────────────────────────────

/**
 * Represents a single item in the chat message list.
 */
sealed class ChatMessage {
    abstract val id: Long

    data class User(
        override val id: Long,
        val text: String,
    ) : ChatMessage()

    data class Assistant(
        override val id: Long,
        val text: String,
        val verses: List<VerseResult>,
    ) : ChatMessage()
}

/**
 * Immutable UI state for the chat screen.
 *
 * @param messages Ordered list of messages to display (oldest first).
 * @param inputText Current value of the message text field.
 * @param isLoading True while waiting for the backend response.
 * @param errorMessage Non-null when an error should be shown to the user.
 * @param sessionId Opaque session UUID returned by the backend; sent on subsequent requests.
 */
data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val inputText: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val sessionId: String? = null,
)

// ── ViewModel ─────────────────────────────────────────────────────────────────

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    /** Monotonically increasing counter used as a stable, unique ID for messages. */
    private var nextMessageId = 0L

    // ── Public events (called from the UI) ─────────────────────────────────────

    /** Called whenever the user types in the input field. */
    fun onInputChanged(text: String) {
        _uiState.update { it.copy(inputText = text, errorMessage = null) }
    }

    /** Called when the user taps the Send button or submits the keyboard action. */
    fun onSendMessage() {
        val text = _uiState.value.inputText.trim()
        if (text.isBlank() || _uiState.value.isLoading) return

        val userMessage = ChatMessage.User(id = nextMessageId++, text = text)

        _uiState.update { state ->
            state.copy(
                messages = state.messages + userMessage,
                inputText = "",
                isLoading = true,
                errorMessage = null,
            )
        }

        viewModelScope.launch {
            chatRepository
                .sendMessage(message = text, sessionId = _uiState.value.sessionId)
                .fold(
                    onSuccess = { response ->
                        val assistantMessage = ChatMessage.Assistant(
                            id = nextMessageId++,
                            text = response.response,
                            verses = response.verses,
                        )
                        _uiState.update { state ->
                            state.copy(
                                messages = state.messages + assistantMessage,
                                isLoading = false,
                                sessionId = response.sessionId,
                            )
                        }
                    },
                    onFailure = { throwable ->
                        _uiState.update { state ->
                            state.copy(
                                isLoading = false,
                                errorMessage = throwable.message
                                    ?: "An unexpected error occurred. Please try again.",
                            )
                        }
                    },
                )
        }
    }

    /** Dismiss an error snackbar / banner. */
    fun onErrorDismissed() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}

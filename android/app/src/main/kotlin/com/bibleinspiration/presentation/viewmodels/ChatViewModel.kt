package com.bibleinspiration.presentation.viewmodels

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.bibleinspiration.R
import com.bibleinspiration.data.preferences.LanguagePreferences
import com.bibleinspiration.data.preferences.SessionPreferences
import com.bibleinspiration.data.preferences.ThemePreferences
import com.bibleinspiration.data.preferences.TranslationPreferences
import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.models.ChapterResponseDto
import com.bibleinspiration.data.remote.models.TranslationDto
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.domain.repositories.ChatRepository
import com.bibleinspiration.security.TurnstileManager
import com.bibleinspiration.utils.LogCollector
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import timber.log.Timber
import java.io.File
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.UUID
import javax.inject.Inject

/** State of the chapter bottom sheet. */
sealed class ChapterSheetState {
    object Idle : ChapterSheetState()
    object Loading : ChapterSheetState()
    data class Success(val response: ChapterResponseDto) : ChapterSheetState()
    data class Error(val message: String) : ChapterSheetState()
}

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val currentLocale: String = "en",
    val isTurnstileReady: Boolean = false,
    /** ID of the currently active conversation; null when no conversation has started. */
    val currentConversationId: String? = null,
    /** The user's persisted theme preference: "light", "dark", or "system". */
    val themeMode: String = "system",
    /** True when the backend returns HTTP 429 with a session_lifetime_limit error. */
    val isSessionLimitReached: Boolean = false,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository,
    val turnstileManager: TurnstileManager,
    private val languagePreferences: LanguagePreferences,
    @ApplicationContext private val context: Context,
    private val themePreferences: ThemePreferences,
    private val translationPreferences: TranslationPreferences,
    private val sessionPreferences: SessionPreferences,
    private val bibleApiService: BibleApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    /**
     * Exposes the currently selected BCP-47 language code as a [StateFlow].
     * Derived from [uiState] so callers don't need to map themselves.
     */
    val selectedLanguage: StateFlow<String> = _uiState
        .map { it.currentLocale }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = _uiState.value.currentLocale,
        )

    /** Available Bible translations fetched from the backend. Empty while loading or on error. */
    private val _availableTranslations = MutableStateFlow<List<TranslationDto>>(emptyList())
    val availableTranslations: StateFlow<List<TranslationDto>> = _availableTranslations.asStateFlow()

    /** The user's currently preferred translation ID (empty string = no preference). */
    val preferredTranslation: StateFlow<String> = translationPreferences.preferredTranslationFlow
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = TranslationPreferences.DEFAULT_TRANSLATION,
        )

    private val _chapterSheetState = MutableStateFlow<ChapterSheetState>(ChapterSheetState.Idle)
    val chapterSheetState: StateFlow<ChapterSheetState> = _chapterSheetState.asStateFlow()

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
        // Restore persisted theme mode on startup.
        viewModelScope.launch {
            themePreferences.themeModeFlow.collect { mode ->
                _uiState.update { it.copy(themeMode = mode) }
            }
        }
        // Fetch available translations from the backend.
        viewModelScope.launch {
            try {
                val response = bibleApiService.getTranslations()
                _availableTranslations.value = response.translations
            } catch (e: Exception) {
                Timber.w(e, "Failed to fetch translations; defaulting to empty list")
                _availableTranslations.value = emptyList()
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

            val translation = preferredTranslation.value.ifBlank { null }
            val sessionId = sessionPreferences.getOrCreateSessionId()

            val request = ChatRequest(
                message = trimmed,
                conversationHistory = history,
                preferredTranslation = translation,
                sessionId = sessionId,
            )

            var accumulatedContent = ""
            var finalVerses: List<Verse> = emptyList()
            var didError = false
            var metadataMessageId = ""

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
                    // Turnstile tokens are single-use: the server consumes the token on the
                    // first validated request. Always reset after every stream attempt
                    // (success or error) so the next message obtains a fresh token.
                    turnstileManager.onTokenConsumed()

                    if (!didError) {
                        val finalAssistant = Message(
                            id = assistantId,
                            role = Message.Role.ASSISTANT,
                            content = accumulatedContent,
                            verses = finalVerses,
                            isStreaming = false,
                            messageId = metadataMessageId,
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
                    // Handle metadata events (sent before content chunks).
                    if (chunk.messageId.isNotBlank() && accumulatedContent.isEmpty()) {
                        metadataMessageId = chunk.messageId
                        // Update the in-progress assistant message with the backend message_id.
                        _uiState.update { state ->
                            state.copy(
                                messages = state.messages.map { msg ->
                                    if (msg.id == assistantId) {
                                        msg.copy(messageId = chunk.messageId)
                                    } else msg
                                },
                            )
                        }
                        return@collect
                    }

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
                isSessionLimitReached = false,
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

    /**
     * Updates the theme mode in-memory and persists it via DataStore.
     *
     * @param mode One of "light", "dark", or "system".
     */
    fun setThemeMode(mode: String) {
        _uiState.update { it.copy(themeMode = mode) }
        viewModelScope.launch {
            themePreferences.setThemeMode(mode)
        }
    }

    /**
     * Persists the user's preferred Bible translation ID via DataStore.
     *
     * @param id Translation ID (e.g. "KJV"), or "" to clear the preference.
     */
    fun setPreferredTranslation(id: String) {
        viewModelScope.launch {
            translationPreferences.setPreferredTranslation(id)
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    /** Clears the session-limit flag without starting a new conversation. */
    fun dismissSessionLimit() {
        _uiState.update { it.copy(isSessionLimitReached = false) }
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
    // Chapter sheet
    // ---------------------------------------------------------------------------

    /**
     * Loads all verses for [book] and [chapter] from the API and updates [chapterSheetState].
     */
    fun loadChapter(book: String, chapter: Int, translation: String?) {
        _chapterSheetState.value = ChapterSheetState.Loading
        viewModelScope.launch {
            try {
                val response = bibleApiService.getChapter(book, chapter, translation)
                _chapterSheetState.value = ChapterSheetState.Success(response)
            } catch (e: Exception) {
                Timber.e(e, "loadChapter error: $book $chapter")
                _chapterSheetState.value = ChapterSheetState.Error(mapExceptionToMessage(e))
            }
        }
    }

    /** Resets the chapter sheet state back to [ChapterSheetState.Idle]. */
    fun clearChapterSheet() {
        _chapterSheetState.value = ChapterSheetState.Idle
    }

    // ---------------------------------------------------------------------------
    // Debug log export
    // ---------------------------------------------------------------------------

    /**
     * Collects in-memory logs from [LogCollector], writes them to a cache file,
     * and launches the system share sheet so the user can send the log file.
     */
    fun shareDebugLogs(context: Context) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val log = LogCollector.getLog()
                val file = File(context.cacheDir, "bible_inspiration_debug.log")
                file.writeText(log)
                val uri = FileProvider.getUriForFile(
                    context,
                    "${context.packageName}.fileprovider",
                    file,
                )
                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    putExtra(Intent.EXTRA_SUBJECT, "Bible Inspiration Debug Log")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(
                    Intent.createChooser(intent, "Share debug log").apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    },
                )
            } catch (e: Exception) {
                Timber.e(e, "Failed to share debug logs")
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
        e is HttpException && e.code() == 429 -> {
            val body = e.response()?.errorBody()?.string() ?: ""
            if (body.contains("session_lifetime_limit")) {
                _uiState.update { it.copy(isSessionLimitReached = true, isLoading = false) }
                context.getString(R.string.error_session_limit)
            } else {
                context.getString(R.string.error_server)
            }
        }
        e is HttpException ->
            context.getString(R.string.error_server)
        e is IOException ->
            context.getString(R.string.error_network)
        else ->
            context.getString(R.string.error_generic)
    }
}

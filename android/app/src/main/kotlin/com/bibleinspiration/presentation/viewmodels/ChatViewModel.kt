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
import com.bibleinspiration.data.remote.models.BookNamesResponseDto
import com.bibleinspiration.data.remote.models.ChapterResponseDto
import com.bibleinspiration.data.remote.models.TranslationDto
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Church
import com.bibleinspiration.domain.models.FeedbackRating
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.domain.repositories.ChatRepository
import com.bibleinspiration.domain.repositories.ChurchRepository
import com.bibleinspiration.domain.repositories.ContactRepository
import com.bibleinspiration.presentation.components.ContactFormState
import com.bibleinspiration.security.TurnstileManager
import com.bibleinspiration.utils.LogCollector
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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

/** State of the church-finder bottom sheet. */
sealed class ChurchFinderSheetState {
    object Idle : ChurchFinderSheetState()
    object Loading : ChurchFinderSheetState()
    data class Success(val churches: List<Church>, val location: String) : ChurchFinderSheetState()
    data class Error(val message: String) : ChurchFinderSheetState()
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
    /** True when loading has been in-progress for >3 s with no chunk received yet. */
    val isBackendWarming: Boolean = false,
    /** Maps message ID (local UUID) to the rating given: "positive" or "negative". */
    val feedbackGiven: Map<String, String> = emptyMap(),
    /** True while a feedback submission is in flight. */
    val isFeedbackSubmitting: Boolean = false,
    /**
     * Number of completed user↔assistant exchange rounds.
     * Incremented each time an assistant message finishes streaming without error.
     * Used to trigger the church-finder prompt at the right moment.
     */
    val interactionCount: Int = 0,
    /**
     * True once [interactionCount] reaches exactly 3 and the user hasn't
     * dismissed the church-finder banner yet. Uses == 3 (not >= 3) so the
     * banner is not re-shown after being dismissed.
     */
    val showChurchFinderBanner: Boolean = false,
    /**
     * True when the inline church-finder card should appear in the message list
     * (after 5 interactions, or immediately after the banner is dismissed via
     * "Find a Church").
     */
    val showChurchFinderInlineCard: Boolean = false,
    /**
     * Flat, deduplicated list of all [Verse] objects across every finished assistant
     * message in the current conversation.  Populated incrementally as each
     * streaming response completes.  Used by the Verses sidebar panel.
     */
    val allVerses: List<Verse> = emptyList(),
    /**
     * The Bible translation auto-detected by the backend for this conversation
     * (e.g. "ita1927" for Italian).  Populated from the SSE metadata event.
     * Used as a fallback when the user has not set an explicit preferred translation.
     */
    val detectedTranslation: String = "",
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository,
    private val churchRepository: ChurchRepository,
    private val contactRepository: ContactRepository,
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

    /**
     * Book name data fetched from the backend.  Null until the first successful fetch.
     * Provides [multiWordNames] (for dynamic regex) and [localizedToEnglish] (for normalization).
     */
    private val _bookNames = MutableStateFlow<BookNamesResponseDto?>(null)
    val bookNames: StateFlow<BookNamesResponseDto?> = _bookNames.asStateFlow()

    /** Multi-word book names derived from [_bookNames], sorted longest-first (as provided by API). */
    val multiWordNames: StateFlow<List<String>> = _bookNames
        .map { it?.multiWordNames ?: emptyList() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = emptyList(),
        )

    /** Localized-to-English book name map derived from [_bookNames]. */
    val localizedToEnglish: StateFlow<Map<String, String>> = _bookNames
        .map { it?.localizedToEnglish ?: emptyMap() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = emptyMap(),
        )

    /** The user's currently preferred translation ID (empty string = no preference). */
    val preferredTranslation: StateFlow<String> = translationPreferences.preferredTranslationFlow
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = TranslationPreferences.DEFAULT_TRANSLATION,
        )

    private val _chapterSheetState = MutableStateFlow<ChapterSheetState>(ChapterSheetState.Idle)
    val chapterSheetState: StateFlow<ChapterSheetState> = _chapterSheetState.asStateFlow()
    private var loadChapterJob: Job? = null

    private val _churchFinderSheetState = MutableStateFlow<ChurchFinderSheetState>(ChurchFinderSheetState.Idle)
    val churchFinderSheetState: StateFlow<ChurchFinderSheetState> = _churchFinderSheetState.asStateFlow()

    private val _contactFormState = MutableStateFlow<ContactFormState>(ContactFormState.Idle)
    val contactFormState: StateFlow<ContactFormState> = _contactFormState.asStateFlow()

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
        // Fetch available translations from the backend with retry.
        viewModelScope.launch { fetchTranslationsWithRetry() }
        // Fetch book name mappings from the backend with retry.
        viewModelScope.launch { fetchBookNamesWithRetry() }
    }

    /**
     * Fetches the available translations from the backend with exponential backoff.
     * Attempts up to [maxAttempts] times, starting with a [initialDelayMs] ms delay that
     * doubles on each retry. Falls back to an empty list when all attempts fail.
     */
    private suspend fun fetchTranslationsWithRetry(
        maxAttempts: Int = 3,
        initialDelayMs: Long = 1_000L,
    ) {
        var delayMs = initialDelayMs
        repeat(maxAttempts) { attempt ->
            try {
                val response = bibleApiService.getTranslations()
                _availableTranslations.value = response.translations
                return
            } catch (e: Exception) {
                val isLastAttempt = attempt == maxAttempts - 1
                if (isLastAttempt) {
                    Timber.w(e, "Failed to fetch translations after $maxAttempts attempts; defaulting to empty list")
                    _availableTranslations.value = emptyList()
                } else {
                    Timber.w(e, "Failed to fetch translations (attempt ${attempt + 1}/$maxAttempts); retrying in ${delayMs}ms")
                    delay(delayMs)
                    delayMs *= 2
                }
            }
        }
    }

    /** Triggers a fresh fetch of available translations (e.g. after a network error banner). */
    fun refreshTranslations() {
        viewModelScope.launch { fetchTranslationsWithRetry() }
    }

    /**
     * Fetches book name mappings from the backend with exponential backoff.
     * Attempts up to [maxAttempts] times, starting with a [initialDelayMs] ms delay that
     * doubles on each retry. Falls back to null (no dynamic regex) when all attempts fail.
     */
    private suspend fun fetchBookNamesWithRetry(
        maxAttempts: Int = 3,
        initialDelayMs: Long = 1_000L,
    ) {
        var delayMs = initialDelayMs
        repeat(maxAttempts) { attempt ->
            try {
                val response = bibleApiService.getBookNames()
                _bookNames.value = response
                return
            } catch (e: Exception) {
                val isLastAttempt = attempt == maxAttempts - 1
                if (isLastAttempt) {
                    Timber.w(e, "Failed to fetch book names after $maxAttempts attempts; falling back to default regex")
                } else {
                    Timber.w(e, "Failed to fetch book names (attempt ${attempt + 1}/$maxAttempts); retrying in ${delayMs}ms")
                    delay(delayMs)
                    delayMs *= 2
                }
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

            // Show warm-up hint if the backend hasn't responded within 3 seconds.
            val warmUpJob = launch {
                delay(3_000L)
                if (_uiState.value.isLoading) {
                    _uiState.update { it.copy(isBackendWarming = true) }
                }
            }

            var accumulatedContent = ""
            var finalVerses: List<Verse> = emptyList()
            var didError = false
            var metadataMessageId = ""

            repository
                .chatStream(request)
                .catch { e ->
                    Timber.e(e, "chatStream error")
                    didError = true
                    warmUpJob.cancel()
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
                            isBackendWarming = false,
                            error = errorMessage,
                        )
                    }
                }
                .onCompletion {
                    // Turnstile tokens are single-use: the server consumes the token on the
                    // first validated request. Always reset after every stream attempt
                    // (success or error) so the next message obtains a fresh token.
                    turnstileManager.onTokenConsumed()
                    warmUpJob.cancel()

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
                            val newCount = state.interactionCount + 1
                            // Append new verses, deduplicating by reference only (not translation)
                            // so each verse appears once regardless of which translation it came from.
                            val existingRefs = state.allVerses.map { "${it.book}${it.chapter}:${it.verse}" }.toHashSet()
                            val dedupedNew = finalVerses.filterNot { v ->
                                "${v.book}${v.chapter}:${v.verse}" in existingRefs
                            }
                            state.copy(
                                messages = state.messages.map { msg ->
                                    if (msg.id == assistantId) finalAssistant else msg
                                },
                                isLoading = false,
                                isBackendWarming = false,
                                interactionCount = newCount,
                                // Show the banner exactly once, at interaction 3.
                                // Using == rather than >= prevents re-showing the banner
                                // after it has been dismissed (banner=false, inline=false).
                                showChurchFinderBanner = !state.showChurchFinderBanner &&
                                    !state.showChurchFinderInlineCard &&
                                    newCount == 3,
                                // Show the inline card after 5 interactions if the banner
                                // was already dismissed without opening the sheet.
                                showChurchFinderInlineCard = state.showChurchFinderInlineCard ||
                                    (newCount >= 5 && !state.showChurchFinderBanner),
                                allVerses = state.allVerses + dedupedNew,
                            )
                        }
                    }
                }
                .collect { chunk ->
                    // First content chunk received — cancel the warm-up hint.
                    if (accumulatedContent.isEmpty() && chunk.content.isNotEmpty()) {
                        warmUpJob.cancel()
                        _uiState.update { it.copy(isBackendWarming = false) }
                    }

                    // Handle metadata events (sent before content chunks).
                    if (chunk.messageId.isNotBlank() && accumulatedContent.isEmpty()) {
                        metadataMessageId = chunk.messageId
                        // Verses are delivered in the metadata event via scripture_context.
                        if (chunk.verses.isNotEmpty()) finalVerses = chunk.verses
                        // Update the in-progress assistant message with the backend message_id.
                        _uiState.update { state ->
                            state.copy(
                                messages = state.messages.map { msg ->
                                    if (msg.id == assistantId) {
                                        msg.copy(messageId = chunk.messageId)
                                    } else msg
                                },
                                detectedTranslation = chunk.detectedTranslation.ifBlank { state.detectedTranslation },
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
                // Re-derive allVerses from loaded messages (deduplicated).
                val allVerses = messages
                    .filter { it.role == Message.Role.ASSISTANT }
                    .flatMap { it.verses }
                    .distinctBy { "${it.book}${it.chapter}:${it.verse}" }
                _uiState.update { it.copy(messages = messages, currentConversationId = conversationId, allVerses = allVerses) }
            }
        }
    }

    /** Reset in-memory state and clear the active conversation ID (starts a new session). */
    fun startNewConversation() {
        viewModelScope.launch {
            sessionPreferences.resetSessionId()
        }
        _uiState.update {
            it.copy(
                messages = emptyList(),
                error = null,
                isLoading = false,
                isBackendWarming = false,
                currentConversationId = null,
                isSessionLimitReached = false,
                interactionCount = 0,
                showChurchFinderBanner = false,
                showChurchFinderInlineCard = false,
                allVerses = emptyList(),
            )
        }
        _churchFinderSheetState.value = ChurchFinderSheetState.Idle
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

    /**
     * Submits thumbs-up or thumbs-down feedback for an assistant message.
     *
     * @param messageLocalId The local UUID of the assistant [Message] (its [Message.id]).
     * @param rating "positive" or "negative".
     * @param comment Optional free-text comment (reserved for future use).
     */
    fun submitFeedback(messageLocalId: String, rating: String, comment: String? = null) {
        // Look up the message and its context (user message preceding it).
        val messages = _uiState.value.messages
        val assistantMsg = messages.firstOrNull { it.id == messageLocalId } ?: return
        if (assistantMsg.messageId.isBlank()) return // no backend message_id yet — skip

        // Find the user message that immediately preceded this assistant message.
        val assistantIndex = messages.indexOf(assistantMsg)
        val userMessage = messages.subList(0, assistantIndex).lastOrNull { it.role == Message.Role.USER }

        _uiState.update { it.copy(isFeedbackSubmitting = true) }

        viewModelScope.launch {
            try {
                val feedbackRating = if (rating == "positive") FeedbackRating.POSITIVE else FeedbackRating.NEGATIVE
                repository.submitFeedback(
                    messageId = assistantMsg.messageId,
                    rating = feedbackRating,
                    userMessage = userMessage?.content ?: "",
                    assistantResponse = assistantMsg.content,
                )
                _uiState.update { state ->
                    state.copy(
                        feedbackGiven = state.feedbackGiven + (messageLocalId to rating),
                        isFeedbackSubmitting = false,
                    )
                }
                Timber.i("Feedback submitted: messageId=%s rating=%s", assistantMsg.messageId, rating)
            } catch (e: Exception) {
                Timber.e(e, "Failed to submit feedback")
                _uiState.update { it.copy(isFeedbackSubmitting = false) }
            }
        }
    }

    /** Deletes the active conversation from DB and resets in-memory state. */
    fun clearConversation() {
        val conversationId = _uiState.value.currentConversationId
        _uiState.update { it.copy(messages = emptyList(), error = null, currentConversationId = null, allVerses = emptyList()) }
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
        loadChapterJob?.cancel()
        _chapterSheetState.value = ChapterSheetState.Loading
        loadChapterJob = viewModelScope.launch {
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
    // Church Finder
    // ---------------------------------------------------------------------------

    /**
     * Dismisses the church-finder banner without opening the sheet.
     * Also hides the inline card if it was already shown.
     */
    fun dismissChurchFinderBanner() {
        _uiState.update {
            it.copy(
                showChurchFinderBanner = false,
                showChurchFinderInlineCard = false,
            )
        }
    }

    /**
     * Called when the user taps "Find a Church" — dismisses the banner, shows
     * the inline card, and triggers the bottom sheet to open (caller observes
     * [churchFinderSheetState] transitioning away from Idle).
     *
     * The bottom sheet itself calls [searchChurches] with the user-supplied location.
     */
    fun openChurchFinder() {
        _uiState.update {
            it.copy(
                showChurchFinderBanner = false,
                showChurchFinderInlineCard = true,
            )
        }
        // Reset to Idle so ChatScreen knows to open the sheet.
        _churchFinderSheetState.value = ChurchFinderSheetState.Idle
    }

    /**
     * Searches for churches near [location] (English city name).
     * Updates [churchFinderSheetState] from Loading → Success / Error.
     */
    fun searchChurches(location: String) {
        if (location.isBlank()) return
        _churchFinderSheetState.value = ChurchFinderSheetState.Loading
        viewModelScope.launch {
            try {
                val churches = churchRepository.searchChurches(location.trim())
                _churchFinderSheetState.value = ChurchFinderSheetState.Success(
                    churches = churches,
                    location = location.trim(),
                )
            } catch (e: Exception) {
                Timber.e(e, "searchChurches error for location=$location")
                _churchFinderSheetState.value = ChurchFinderSheetState.Error(
                    mapExceptionToMessage(e),
                )
            }
        }
    }

    /** Resets the church-finder sheet state back to [ChurchFinderSheetState.Idle]. */
    fun clearChurchFinderSheet() {
        _churchFinderSheetState.value = ChurchFinderSheetState.Idle
    }

    // ---------------------------------------------------------------------------
    // Contact Form
    // ---------------------------------------------------------------------------

    /**
     * Submits the contact form to the backend.
     *
     * @param subject One of the [ContactSubject] constants.
     * @param message The user's free-text message (non-blank).
     * @param email   Optional reply-to email address.
     */
    fun submitContact(subject: String, message: String, email: String?) {
        if (message.isBlank()) return
        _contactFormState.value = ContactFormState.Submitting
        viewModelScope.launch {
            try {
                contactRepository.submitContact(
                    subject = subject,
                    message = message,
                    email = email,
                )
                _contactFormState.value = ContactFormState.Success
                Timber.i("Contact submitted: subject=%s", subject)
            } catch (e: Exception) {
                Timber.e(e, "Failed to submit contact form")
                _contactFormState.value = ContactFormState.Error(
                    mapExceptionToMessage(e),
                )
            }
        }
    }

    /** Resets the contact form state back to [ContactFormState.Idle]. */
    fun resetContactForm() {
        _contactFormState.value = ContactFormState.Idle
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

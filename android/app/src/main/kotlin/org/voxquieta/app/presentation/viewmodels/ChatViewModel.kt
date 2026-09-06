package org.voxquieta.app.presentation.viewmodels

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import org.voxquieta.app.R
import org.voxquieta.app.data.preferences.LanguagePreferences
import org.voxquieta.app.data.preferences.LastConversationPreferences
import org.voxquieta.app.data.preferences.SessionPreferences
import org.voxquieta.app.data.preferences.ThemePreferences
import org.voxquieta.app.data.preferences.TranslationPreferences
import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.remote.models.BookNamesResponseDto
import org.voxquieta.app.data.remote.models.ChapterResponseDto
import org.voxquieta.app.data.remote.models.ContactSubject
import org.voxquieta.app.data.remote.models.TranslationDto
import org.voxquieta.app.domain.models.ChatRequest
import org.voxquieta.app.domain.models.Church
import org.voxquieta.app.domain.models.FeedbackRating
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.domain.repositories.ChatRepository
import org.voxquieta.app.domain.repositories.ChurchRepository
import org.voxquieta.app.domain.repositories.ContactRepository
import org.voxquieta.app.presentation.components.ContactFormState
import org.voxquieta.app.security.TurnstileManager
import org.voxquieta.app.utils.LocaleApplier
import org.voxquieta.app.utils.normalizeBookName
import org.voxquieta.app.utils.LogCollector
import org.voxquieta.app.utils.NetworkMonitor
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import retrofit2.HttpException
import timber.log.Timber
import java.io.File
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.Locale
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
    // Empty string = no explicit user preference; backend auto-detects from message text.
    val currentLocale: String = "",
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
    /** True when the device has no active internet connection. */
    val isOffline: Boolean = false,
    /**
     * ISO 639-1 code of the language the backend detected the user typing in, when
     * it differs from the explicitly-selected UI locale. Non-null means show the
     * language-switch suggestion banner. Null means no banner.
     */
    val languageSuggestion: String? = null,
    /**
     * Effective max characters allowed in a single chat message. Seeded from
     * the compiled-in [ChatViewModel.MAX_MESSAGE_LENGTH] fallback and updated
     * once GET /config resolves (BITB-075) — see [ChatViewModel.fetchConfigWithRetry].
     */
    val maxMessageLength: Int = ChatViewModel.MAX_MESSAGE_LENGTH,
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
    private val lastConversationPreferences: LastConversationPreferences,
    private val bibleApiService: BibleApiService,
    private val networkMonitor: NetworkMonitor,
    private val localeApplier: LocaleApplier,
) : ViewModel() {

    companion object {
        /**
         * Number of completed interactions after which the session ends.
         * Must match the backend's RATE_LIMIT_SESSION_MAX_REQUESTS setting (default 10).
         */
        const val MAX_INTERACTIONS = 10

        /** Chapter fetch client-side timeout; mirrors the backend verse_query_timeout_s. */
        const val CHAPTER_LOAD_TIMEOUT_MS = 10_000L

        /**
         * Pre-config fallback only (BITB-075). The effective max characters
         * allowed in a single chat message comes from the backend at runtime
         * via GET /config -> chat.max_message_length (see
         * [ChatUiState.maxMessageLength], seeded from this constant and
         * updated by [fetchConfigWithRetry]). The server always enforces its
         * own configured limit regardless of this value.
         */
        const val MAX_MESSAGE_LENGTH = 500
    }

    // Read the persisted theme synchronously so the very first composition (and every
    // Activity re-creation after rotation) uses the correct value.  DataStore serves
    // subsequent reads from an in-memory cache, so this blocks for < 1 ms after the
    // first cold-start disk read.  Without this, the state starts as "system" and the
    // async collect in init{} arrives one frame late, causing a brief theme flash.
    private val _uiState = MutableStateFlow(
        ChatUiState(
            themeMode = runBlocking { themePreferences.themeModeFlow.first() },
            currentLocale = languagePreferences.readInitial(),
        )
    )
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

    /**
     * The user's currently preferred translation ID (empty string = no preference),
     * scoped to the active UI language (BITB-115) so switching languages never
     * carries a stale translation choice into the new one.
     */
    @OptIn(ExperimentalCoroutinesApi::class)
    val preferredTranslation: StateFlow<String> = selectedLanguage
        .flatMapLatest { locale -> translationPreferences.preferredTranslationFlow(locale) }
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

    // Diagnostic-report submission reuses the generic submit-lifecycle states
    // from [ContactFormState] because the flow is the same: Idle → Submitting →
    // Success / Error. The bottom sheet renders a spinner, success screen or
    // inline error message based on this state.
    private val _diagnosticReportState = MutableStateFlow<ContactFormState>(ContactFormState.Idle)
    val diagnosticReportState: StateFlow<ContactFormState> = _diagnosticReportState.asStateFlow()

    /**
     * The currently running send-message coroutine. Cancelling this job interrupts
     * the SSE stream so the user can stop generation mid-response. The partial
     * assistant content collected so far is preserved by [onCompletion].
     */
    private var streamJob: Job? = null

    init {
        // isTurnstileReady is true when a valid token is held OR when Turnstile has
        // errored (fail-open): the interceptor already forwards requests without a
        // token, so the backend decides whether to accept them. This prevents the
        // Turnstile widget from permanently blocking the input on widget errors.
        viewModelScope.launch {
            combine(
                turnstileManager.tokenFlow,
                turnstileManager.hasError,
            ) { token, errored -> token != null || errored }
                .collect { ready ->
                    _uiState.update { it.copy(isTurnstileReady = ready) }
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
        // Restore the persisted per-session interaction count so the 10-message
        // limit survives app restarts and conversation loads. The count is keyed
        // to the session lifetime (reset by startNewConversation), so we seed both
        // the counter and the limit flag from DataStore on cold start. We do NOT
        // restore the church-finder banner/inline flags: those use one-shot
        // triggers (== 3 / >= 5) and must not re-nag after a restart.
        viewModelScope.launch {
            val restoredCount = sessionPreferences.getInteractionCount()
            _uiState.update {
                it.copy(
                    interactionCount = restoredCount,
                    isSessionLimitReached = restoredCount >= MAX_INTERACTIONS,
                )
            }
        }
        // Fetch available translations from the backend with retry.
        viewModelScope.launch { fetchTranslationsWithRetry() }
        // Fetch book name mappings from the backend with retry.
        viewModelScope.launch { fetchBookNamesWithRetry() }
        // Fetch server-published config (currently just the effective chat
        // message-length limit) from the backend with retry (BITB-075).
        viewModelScope.launch { fetchConfigWithRetry() }
        // Mirror the connectivity state into uiState so the UI can react.
        viewModelScope.launch {
            networkMonitor.isOffline.collect { offline ->
                _uiState.update { it.copy(isOffline = offline) }
            }
        }
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
                translationPreferences.migrateLegacyPreference(response.translations)
                return
            } catch (e: Exception) {
                if (e is CancellationException) throw e
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
                if (e is CancellationException) throw e
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

    /**
     * Fetches server-published config from the backend with exponential backoff
     * (BITB-075). Attempts up to [maxAttempts] times, starting with a
     * [initialDelayMs] ms delay that doubles on each retry. Falls back to
     * leaving [ChatUiState.maxMessageLength] at its compiled-in default when
     * all attempts fail, or when the response doesn't include a valid
     * positive value.
     */
    private suspend fun fetchConfigWithRetry(
        maxAttempts: Int = 3,
        initialDelayMs: Long = 1_000L,
    ) {
        var delayMs = initialDelayMs
        repeat(maxAttempts) { attempt ->
            try {
                val response = bibleApiService.getConfig()
                val maxLength = response.chat?.maxMessageLength
                if (maxLength != null && maxLength > 0) {
                    _uiState.update { it.copy(maxMessageLength = maxLength) }
                }
                return
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                val isLastAttempt = attempt == maxAttempts - 1
                if (isLastAttempt) {
                    Timber.w(e, "Failed to fetch config after $maxAttempts attempts; keeping fallback maxMessageLength")
                } else {
                    Timber.w(e, "Failed to fetch config (attempt ${attempt + 1}/$maxAttempts); retrying in ${delayMs}ms")
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
                languageSuggestion = null,
            )
        }

        streamJob = viewModelScope.launch {
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
                language = _uiState.value.currentLocale.ifBlank { null },
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
            var finalVersesCited: List<String> = emptyList()
            var finalResolvedVerses: List<Verse> = emptyList()
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
                        // When the session limit is reached, deliver the invitation text as a
                        // proper assistant message (matching web-frontend behaviour) rather than
                        // flagging it as an error.  isSessionLimitReached was already set to
                        // true inside mapExceptionToMessage before this update runs.
                        val isSessionLimit = state.isSessionLimitReached
                        state.copy(
                            messages = state.messages.map { msg ->
                                if (msg.id == assistantId) {
                                    if (isSessionLimit) {
                                        msg.copy(
                                            content = errorMessage,
                                            isStreaming = false,
                                            isError = false,
                                        )
                                    } else {
                                        // Carry the (often empathetic) explanation on the
                                        // message itself so it renders in the chat bubble
                                        // above the Retry button. Previously this was left
                                        // empty and the text only went to the snackbar, which
                                        // ChatScreen suppresses whenever an inline Retry exists
                                        // — so blocked/error messages showed only a bare Retry
                                        // button with no explanation.
                                        msg.copy(
                                            content = errorMessage,
                                            isStreaming = false,
                                            isError = true,
                                        )
                                    }
                                } else msg
                            },
                            isLoading = false,
                            isBackendWarming = false,
                            error = if (isSessionLimit) null else errorMessage,
                        )
                    }
                }
                .onCompletion {
                    // Turnstile token consumption is now centralised in
                    // TurnstileInterceptor — every gated POST clears the cached
                    // token and triggers a WebView reset, so each repository
                    // (chat, church, feedback) inherits the fix without having
                    // to remember to call onTokenConsumed() here.
                    warmUpJob.cancel()

                    if (!didError) {
                        // Merge backend-resolved cited verses into the message's verse
                        // list (deduped by reference). This both feeds the verse panel
                        // and persists them in versesJson, so the "Cited" tab survives
                        // a reload even for verses outside the semantic pool.
                        val mergedVerses = if (finalResolvedVerses.isEmpty()) {
                            finalVerses
                        } else {
                            val existing = finalVerses
                                .map { "${it.book}${it.chapter}:${it.verse}" }
                                .toHashSet()
                            finalVerses + finalResolvedVerses.filterNot { v ->
                                "${v.book}${v.chapter}:${v.verse}" in existing
                            }
                        }
                        val finalAssistant = Message(
                            id = assistantId,
                            role = Message.Role.ASSISTANT,
                            content = accumulatedContent,
                            verses = mergedVerses,
                            isStreaming = false,
                            messageId = metadataMessageId,
                            versesCited = finalVersesCited,
                        )
                        // Use NonCancellable so that DB writes and the isLoading reset always
                        // complete even when the coroutine was cancelled by the Stop button.
                        // Without this, the first suspending call (saveMessage) throws
                        // CancellationException and isLoading stays true permanently.
                        withContext(NonCancellable) {
                            // Persist finished assistant message and bump conversation timestamp.
                            repository.saveMessage(conversationId, finalAssistant)
                            repository.touchConversation(conversationId)

                            _uiState.update { state ->
                                val newCount = state.interactionCount + 1
                                // Detect the exact moment the session limit is reached so we can
                                // proactively block the input and show the invitation message —
                                // no need for the user to attempt a failing 11th request.
                                val sessionLimitJustReached =
                                    !state.isSessionLimitReached && newCount >= MAX_INTERACTIONS
                                // Append new verses, deduplicating by reference only (not translation)
                                // so each verse appears once regardless of which translation it came from.
                                val existingRefs = state.allVerses.map { "${it.book}${it.chapter}:${it.verse}" }.toHashSet()
                                val dedupedNew = mergedVerses.filterNot { v ->
                                    "${v.book}${v.chapter}:${v.verse}" in existingRefs
                                }
                                // When the limit is just reached, append a synthetic assistant
                                // message so the user sees the invitation in the conversation.
                                val limitMessage = if (sessionLimitJustReached) {
                                    Message(
                                        id = UUID.randomUUID().toString(),
                                        role = Message.Role.ASSISTANT,
                                        content = context.getString(R.string.error_session_limit),
                                    )
                                } else null
                                state.copy(
                                    messages = state.messages.map { msg ->
                                        if (msg.id == assistantId) finalAssistant else msg
                                    } + listOfNotNull(limitMessage),
                                    isLoading = false,
                                    isBackendWarming = false,
                                    interactionCount = newCount,
                                    isSessionLimitReached = state.isSessionLimitReached || sessionLimitJustReached,
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
                            // Persist the new count so the 10-message limit survives
                            // app restarts and conversation loads. state is the
                            // in-memory mirror of the persisted value; write it back.
                            sessionPreferences.setInteractionCount(_uiState.value.interactionCount)
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
                    if (chunk.type == "metadata") {
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
                                // Show the language-switch banner only when the backend is
                                // confident the message was typed in a different language than
                                // the user's explicitly-selected UI locale.
                                languageSuggestion = chunk.languageSuggestion?.takeIf {
                                    it.isNotBlank() && it != state.currentLocale
                                },
                            )
                        }
                        return@collect
                    }

                    // Handle completion event with server-extracted verse citations.
                    if (chunk.type == "completion") {
                        if (chunk.versesCited.isNotEmpty()) {
                            finalVersesCited = chunk.versesCited
                        }
                        // Backend-resolved cited verses (with text). Merging these
                        // into the verse pool ensures the "Cited" tab surfaces
                        // citations that fell outside the semantic search — common
                        // on follow-up questions whose pool reflects the short
                        // follow-up text, not what the answer actually cited.
                        if (chunk.resolvedVerses.isNotEmpty()) {
                            finalResolvedVerses = chunk.resolvedVerses
                        }
                        // Grounding rewrote a fabricated/mismatched verse quote: the
                        // streamed text is already on screen, so replace it with the
                        // authoritative corrected body.
                        chunk.correctedMessage?.let { corrected ->
                            accumulatedContent = corrected
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
     * Cancels the in-flight streaming response, if any. The partial assistant
     * message accumulated so far is kept and persisted via the onCompletion
     * handler in [sendMessage], so the user sees what was produced before they
     * stopped generation.
     */
    fun cancelStream() {
        streamJob?.takeIf { it.isActive }?.cancel()
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
        lastConversationPreferences.setLastConversationId(conversation.id)
        return conversation.id
    }

    /** Load a previously saved conversation by ID and replace in-memory messages. */
     fun loadConversation(conversationId: String) {
        viewModelScope.launch {
            lastConversationPreferences.setLastConversationId(conversationId)
            repository.observeMessages(conversationId).collect { messages ->
                // Re-derive allVerses from loaded messages (deduplicated).
                val allVerses = messages
                    .filter { it.role == Message.Role.ASSISTANT }
                    .flatMap { it.verses }
                    .distinctBy { "${it.book}${it.chapter}:${it.verse}" }
                // Intentionally do NOT recompute interactionCount / isSessionLimitReached
                // from these messages. The limit is per session_id (shared across all
                // conversations and matching the backend), not per conversation thread —
                // an old thread's historical messages belong to past sessions. The current
                // session count is restored from DataStore on init and must be preserved
                // here. Deriving it from the loaded thread would reintroduce
                // per-conversation behaviour and diverge from the backend's 429.
                _uiState.update { it.copy(messages = messages, currentConversationId = conversationId, allVerses = allVerses) }
            }
        }
    }

    /**
     * Resolve the conversation to land on at app launch.
     *
     * Returns the id of the last conversation the user opened if it still exists,
     * or `null` if there is no prior conversation. The caller decides whether to
     * navigate to `chat/<id>` or `chat/new`.
     */
    suspend fun resolveResumeConversationId(): String? {
        val candidate = lastConversationPreferences.getLastConversationId() ?: return null
        val exists = repository.observeConversations().first().any { it.id == candidate }
        if (!exists) {
            lastConversationPreferences.setLastConversationId(null)
            return null
        }
        return candidate
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
                languageSuggestion = null,
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
     * Updates the language locale in-memory, persists it via DataStore, and applies
     * it system-wide so every stringResource() reflects the new locale after the
     * Activity recreate that AppCompatDelegate.setApplicationLocales triggers.
     *
     * Persistence must complete before localeApplier.apply() triggers recreation.
     * If apply() fires first, the init-block languageFlow collector sees the old
     * DataStore value and overwrites _uiState back to the previous locale for the
     * duration of the recreation window, causing a visible revert to the old language.
     */
    fun setLocale(locale: String) {
        if (locale == _uiState.value.currentLocale) return
        Timber.tag("VoxLocale").i("ChatViewModel.setLocale(%s) called", locale)
        _uiState.update { it.copy(currentLocale = locale) }
        viewModelScope.launch {
            languagePreferences.setLanguage(locale)
            localeApplier.apply(locale)
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
            translationPreferences.setPreferredTranslation(_uiState.value.currentLocale, id)
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
     * @param comment Optional free-text comment the user added on thumbs-down.
     */
    fun submitFeedback(messageLocalId: String, rating: String, comment: String? = null, reason: String? = null) {
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
                    comment = comment,
                    reason = if (feedbackRating == FeedbackRating.NEGATIVE) reason else null,
                )
                _uiState.update { state ->
                    state.copy(
                        feedbackGiven = state.feedbackGiven + (messageLocalId to rating),
                        isFeedbackSubmitting = false,
                    )
                }
                Timber.i("Feedback submitted: messageId=%s rating=%s", assistantMsg.messageId, rating)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                Timber.e(e, "Failed to submit feedback")
                _uiState.update { it.copy(isFeedbackSubmitting = false) }
            }
        }
    }

    /** Deletes the active conversation from DB and resets in-memory state. */
    fun clearConversation() {
        // Stop any in-flight stream first: its onCompletion would otherwise try to persist
        // the assistant message against the conversation we are about to delete.
        cancelStream()
        val conversationId = _uiState.value.currentConversationId
        _uiState.update { it.copy(messages = emptyList(), error = null, isLoading = false, currentConversationId = null, allVerses = emptyList()) }
        if (conversationId != null) {
            viewModelScope.launch {
                lastConversationPreferences.setLastConversationId(null)
                repository.deleteConversation(conversationId)
            }
        }
    }

    /** Deletes ALL conversations from DB and resets in-memory state. */
    fun clearAllConversations() {
        // Stop any in-flight stream first: its onCompletion would otherwise try to persist
        // the assistant message against a conversation we are about to delete.
        cancelStream()
        _uiState.update { it.copy(messages = emptyList(), error = null, isLoading = false, currentConversationId = null, allVerses = emptyList()) }
        viewModelScope.launch {
            lastConversationPreferences.setLastConversationId(null)
            repository.clearAllConversations()
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
                // The reference book name comes from the LLM in the conversation language
                // (e.g. German "2 Korinther"); the backend chapter lookup is keyed by English
                // names. Normalize first so localized references resolve instead of 404ing.
                val normalizedBook = normalizeBookName(book, localizedToEnglish.value)
                // Pass the active UI language so that, with no explicit translation,
                // the backend defaults to the version for the language the user is
                // reading rather than English (OkHttp sends no Accept-Language). When
                // the user has no explicit preference, fall back to the default locale
                // config (the device language), then to English.
                val lang = _uiState.value.currentLocale.ifBlank {
                    Locale.getDefault().language.ifBlank { "en" }
                }
                val response = withTimeoutOrNull(CHAPTER_LOAD_TIMEOUT_MS) {
                    bibleApiService.getChapter(normalizedBook, chapter, translation, lang)
                }
                if (response == null) {
                    _chapterSheetState.value =
                        ChapterSheetState.Error(context.getString(R.string.error_timeout))
                } else {
                    _chapterSheetState.value = ChapterSheetState.Success(response)
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
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

    /** Dismisses the language-switch suggestion banner without switching locale. */
    fun dismissLanguageSuggestion() {
        _uiState.update { it.copy(languageSuggestion = null) }
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
                if (e is CancellationException) throw e
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
                if (e is CancellationException) throw e
                Timber.e(e, "Failed to submit contact form")
                _contactFormState.value = ContactFormState.Error(
                    mapContactExceptionToMessage(e),
                )
            }
        }
    }

    /** Resets the contact form state back to [ContactFormState.Idle]. */
    fun resetContactForm() {
        _contactFormState.value = ContactFormState.Idle
    }

    // ---------------------------------------------------------------------------
    // Diagnostic / bug report
    // ---------------------------------------------------------------------------

    /**
     * Sends a bug report through the app's built-in contact pipeline (same
     * backend path used by the contact form) with the user's answers, device
     * metadata, and current diagnostic log in the message body.
     *
     * Transitions [diagnosticReportState] through Submitting → Success or
     * Error so the bottom sheet can show a spinner, a success screen, or an
     * inline error message.
     */
    fun sendDiagnosticEmail(whatWereYouDoing: String, whatDidYouExpect: String, email: String? = null) {
        _diagnosticReportState.value = ContactFormState.Submitting
        viewModelScope.launch {
            try {
                val log = LogCollector.getLog()
                val body = buildBugReportBody(whatWereYouDoing, whatDidYouExpect, log)
                contactRepository.submitContact(
                    subject = ContactSubject.BUG,
                    message = body,
                    email = email,
                    userAgent = "Android/${android.os.Build.VERSION.RELEASE} " +
                        "(SDK ${android.os.Build.VERSION.SDK_INT}; " +
                        "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL})",
                )
                _diagnosticReportState.value = ContactFormState.Success
                Timber.i("Diagnostic bug report submitted")
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                Timber.e(e, "Failed to send diagnostic email")
                _diagnosticReportState.value = ContactFormState.Error(
                    mapContactExceptionToMessage(e),
                )
            }
        }
    }

    /** Resets the diagnostic-report state to [ContactFormState.Idle]. */
    fun resetDiagnosticReport() {
        _diagnosticReportState.value = ContactFormState.Idle
    }

    /**
     * Writes the diagnostic log to a cache file and opens the system share
     * sheet so the user can save or send it via any app of their choice.
     * This is the secondary "save locally" option in the bug-report flow.
     */
    fun saveDiagnosticLogLocally(context: Context) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val uri = writeLogToCache(context) ?: return@launch
                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    putExtra(Intent.EXTRA_SUBJECT, "Vox Quieta Debug Log")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(
                    Intent.createChooser(intent, "Share debug log").apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    },
                )
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                Timber.e(e, "Failed to share debug logs")
            }
        }
    }

    private fun writeLogToCache(context: Context): android.net.Uri? {
        return try {
            val log = LogCollector.getLog()
            val file = File(context.cacheDir, "bible_inspiration_debug.log")
            file.writeText(log)
            FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                file,
            )
        } catch (e: Exception) {
            Timber.e(e, "Failed to write debug log to cache")
            null
        }
    }

    private fun buildBugReportBody(
        whatWereYouDoing: String,
        whatDidYouExpect: String,
        diagnosticLog: String,
    ): String {
        val doing = whatWereYouDoing.trim().ifEmpty { "(not provided)" }
        val expected = whatDidYouExpect.trim().ifEmpty { "(not provided)" }
        val log = diagnosticLog.ifBlank { "(no log entries captured)" }
        val versionName = try {
            org.voxquieta.app.BuildConfig.VERSION_NAME
        } catch (_: Throwable) {
            "unknown"
        }
        return buildString {
            appendLine("What were you doing?")
            appendLine(doing)
            appendLine()
            appendLine("What did you expect to happen?")
            appendLine(expected)
            appendLine()
            appendLine("---")
            appendLine("App version: $versionName")
            appendLine("Android: ${android.os.Build.VERSION.RELEASE} (SDK ${android.os.Build.VERSION.SDK_INT})")
            appendLine("Device: ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}")
            appendLine()
            appendLine("Diagnostic log:")
            appendLine(log)
        }
    }


    // ---------------------------------------------------------------------------
    // Private helpers
    // ---------------------------------------------------------------------------

    /**
     * Error mapping for the contact pipeline (contact form + diagnostic report).
     *
     * Unlike the chat path — where a 422 realistically means an over-long message —
     * a 422 from `POST /api/v1/feedback/contact` is the required email field being
     * missing or malformed. Surface that instead of the misleading "message too
     * long" string; everything else falls back to the shared mapping.
     */
    private fun mapContactExceptionToMessage(e: Throwable): String = when {
        e is HttpException && e.code() == 422 ->
            context.getString(R.string.error_contact_email_invalid)
        else -> mapExceptionToMessage(e)
    }

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
        e is HttpException && e.code() == 400 -> {
            val body = e.response()?.errorBody()?.string() ?: ""
            if (body.contains("content_blocked")) {
                context.getString(R.string.error_content_blocked)
            } else {
                context.getString(R.string.error_server)
            }
        }
        // 403: Cloudflare Turnstile bot verification. The backend returns a
        // body with code TURNSTILE_REQUIRED (no/empty token reached the server)
        // or TURNSTILE_FAILED (token rejected, e.g. stale/duplicate). Log the
        // body so future diagnostic reports show which one it was, then tell the
        // user it's a verification hiccup — not a generic "server error" — since
        // the Turnstile widget self-heals and a retry usually succeeds.
        e is HttpException && e.code() == 403 -> {
            val body = e.response()?.errorBody()?.string() ?: ""
            Timber.w("Turnstile verification rejected request (HTTP 403): %s", body)
            context.getString(R.string.error_verification)
        }
        // 422 request validation: the realistic client-controllable cause is an
        // over-long message. Tell the user to shorten it rather than showing a
        // generic server error.
        e is HttpException && e.code() == 422 ->
            context.getString(R.string.error_message_too_long, _uiState.value.maxMessageLength)
        e is HttpException ->
            context.getString(R.string.error_server)
        e is IOException ->
            context.getString(R.string.error_network)
        else ->
            context.getString(R.string.error_generic)
    }
}

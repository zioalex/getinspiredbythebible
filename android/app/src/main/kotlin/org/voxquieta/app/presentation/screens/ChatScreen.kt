package org.voxquieta.app.presentation.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationDrawerItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import org.voxquieta.app.R
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.presentation.components.ChatInputField
import org.voxquieta.app.presentation.components.ChatMessageItem
import org.voxquieta.app.presentation.components.ChurchFinderBanner
import org.voxquieta.app.presentation.components.LanguageSwitchBanner
import org.voxquieta.app.presentation.components.ChurchFinderBottomSheet
import org.voxquieta.app.presentation.components.LanguagePickerBottomSheet
import org.voxquieta.app.presentation.components.TranslationPickerBottomSheet
import org.voxquieta.app.presentation.components.VersesPanel
import org.voxquieta.app.presentation.components.WelcomeBanner
import org.voxquieta.app.presentation.components.buildVerseRefRegex
import org.voxquieta.app.presentation.viewmodels.ChatViewModel
import org.voxquieta.app.presentation.viewmodels.ConversationsViewModel
import org.voxquieta.app.utils.LOCALIZED_BOOK_TO_ENGLISH
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    conversationId: String? = null,
    onOpenSettings: () -> Unit = {},
    onOpenAllConversations: () -> Unit = {},
    onSelectConversation: (String) -> Unit = {},
    onNewConversation: () -> Unit = {},
    viewModel: ChatViewModel = hiltViewModel(),
    conversationsViewModel: ConversationsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val chapterSheetState by viewModel.chapterSheetState.collectAsState()
    val churchFinderSheetState by viewModel.churchFinderSheetState.collectAsState()
    val availableTranslations by viewModel.availableTranslations.collectAsState()
    val preferredTranslation by viewModel.preferredTranslation.collectAsState()
    val multiWordNames by viewModel.multiWordNames.collectAsState()
    val localizedToEnglish by viewModel.localizedToEnglish.collectAsState()
    // Seed multi-word book names from the bundled fallback map so connector books (e.g.
    // "Song of Solomon", "Cantico dei Cantici") resolve offline / before the API loads, unioned
    // with any server-provided names. Number-prefixed keys ("1 samuele", "1. mose", "1 शमूएल")
    // are excluded: the numbered-prefix branch (Alt 1) already handles them via the generic book
    // pattern, and including them here would double-consume the "1 " prefix.
    //
    // NB: we intentionally do NOT seed CJK names here. A non-empty CJK list makes
    // buildVerseRefRegex exclude BOTH Han and Hangul from the generic pattern, but only Han
    // names get an explicit alternation — so seeding it offline would break Korean. CJK/Hangul
    // are matched by the generic pattern (they are \p{L}) plus the isKnownBook gate instead.
    val bundledMultiWord = remember {
        LOCALIZED_BOOK_TO_ENGLISH.keys.filter { it.contains(' ') && !it.first().isDigit() }
    }
    val allMultiWord = remember(multiWordNames) {
        (multiWordNames + bundledMultiWord).distinct().sortedByDescending { it.length }
    }
    // Extract CJK (Han-script) book names from the localized map for no-space matching.
    val cjkBookNames = remember(localizedToEnglish) {
        localizedToEnglish.keys.filter { key ->
            key.length >= 2 && key.all { ch ->
                Character.UnicodeScript.of(ch.code) == Character.UnicodeScript.HAN
            }
        }.sortedByDescending { it.length }
    }
    val verseRefRegex = remember(allMultiWord, cjkBookNames) {
        buildVerseRefRegex(allMultiWord, cjkBookNames)
    }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }
    var inputText by rememberSaveable { mutableStateOf("") }

    // Show the FAB only when the user has scrolled up from the bottom (i.e. the last item
    // in the list is not currently visible).
    val showScrollFab by remember {
        derivedStateOf {
            val layoutInfo = listState.layoutInfo
            val lastVisibleIndex = layoutInfo.visibleItemsInfo.lastOrNull()?.index
            lastVisibleIndex != null && lastVisibleIndex < layoutInfo.totalItemsCount - 1
        }
    }

    // Whether the church-finder bottom sheet should be open.
    var showChurchFinderSheet by rememberSaveable { mutableStateOf(false) }

    // Whether the verses panel should be open.
    var showVersesPanel by rememberSaveable { mutableStateOf(false) }

    // Whether the translation picker bottom sheet should be open.
    var showTranslationPicker by rememberSaveable { mutableStateOf(false) }

    // Whether the language picker bottom sheet should be open.
    var showLanguagePicker by rememberSaveable { mutableStateOf(false) }

    // Load existing conversation when navigated to a specific one.
    // Guard for the "new" route: only start a fresh conversation when the ViewModel
    // has no active in-memory conversation. This prevents rotation (which re-runs
    // this effect on the still-"new" route) from wiping an in-progress chat. It also
    // covers the locale-change recreate path — the ViewModel is Activity-scoped so
    // locale recreations create a fresh ViewModel with empty state anyway, but the
    // guard makes the intent explicit and handles any future edge cases.
    LaunchedEffect(conversationId) {
        when {
            conversationId == null || conversationId == "new" -> {
                val s = viewModel.uiState.value
                if (s.messages.isEmpty() && s.currentConversationId == null) {
                    viewModel.startNewConversation()
                }
            }
            else -> viewModel.loadConversation(conversationId)
        }
    }

    // Auto-scroll to bottom when messages change
    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    // Show errors in snackbar only when there is no inline retry available.
    // Inline retry is shown when the last assistant message is in an error state.
    val hasInlineRetry = uiState.messages.lastOrNull()
        ?.let { it.role == Message.Role.ASSISTANT && it.isError }
        ?: false

    LaunchedEffect(uiState.error) {
        uiState.error?.let { error ->
            if (!hasInlineRetry && !uiState.isSessionLimitReached) {
                snackbarHostState.showSnackbar(error)
            }
            viewModel.clearError()
        }
    }

    // Church-finder bottom sheet
    if (showChurchFinderSheet) {
        ChurchFinderBottomSheet(
            churchFinderState = churchFinderSheetState,
            onSearch = viewModel::searchChurches,
            onDismiss = {
                showChurchFinderSheet = false
                viewModel.clearChurchFinderSheet()
            },
        )
    }

    // Verses sidebar panel
    if (showVersesPanel) {
        VersesPanel(
            allVerses = uiState.allVerses,
            messages = uiState.messages,
            chapterSheetState = chapterSheetState,
            preferredTranslation = preferredTranslation.takeIf { it.isNotBlank() }
                ?: uiState.detectedTranslation.takeIf { it.isNotBlank() }
                ?: uiState.allVerses.firstOrNull()?.translation?.takeIf { it.isNotBlank() },
            localizedToEnglish = localizedToEnglish,
            onLoadChapter = viewModel::loadChapter,
            onDismissSheet = viewModel::clearChapterSheet,
            onDismiss = { showVersesPanel = false },
        )
    }

    // Translation picker bottom sheet
    if (showTranslationPicker) {
        TranslationPickerBottomSheet(
            availableTranslations = availableTranslations,
            selectedTranslationId = preferredTranslation,
            onSelectTranslation = { id ->
                viewModel.setPreferredTranslation(id)
                showTranslationPicker = false
            },
            onDismiss = { showTranslationPicker = false },
        )
    }

    // Language picker bottom sheet
    if (showLanguagePicker) {
        LanguagePickerBottomSheet(
            currentLocale = uiState.currentLocale,
            onSelectLocale = { code ->
                viewModel.setLocale(code)
                showLanguagePicker = false
            },
            onDismiss = { showLanguagePicker = false },
        )
    }

    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val conversations by conversationsViewModel.conversations.collectAsState()
    val topBarPolicy = chatTopBarPolicy(
        versesCount = uiState.allVerses.size,
        messagesCount = uiState.messages.size,
    )

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ChatHistoryDrawer(
                conversations = conversations,
                currentConversationId = uiState.currentConversationId,
                hasMessages = topBarPolicy.showClearConversationInDrawer,
                onNewChat = {
                    scope.launch { drawerState.close() }
                    onNewConversation()
                },
                onSelectConversation = { id ->
                    scope.launch { drawerState.close() }
                    onSelectConversation(id)
                },
                onOpenAllConversations = {
                    scope.launch { drawerState.close() }
                    onOpenAllConversations()
                },
                onClearConversation = {
                    scope.launch { drawerState.close() }
                    viewModel.clearConversation()
                },
                onOpenLanguagePicker = {
                    scope.launch { drawerState.close() }
                    showLanguagePicker = true
                },
                onOpenTranslationPicker = {
                    scope.launch { drawerState.close() }
                    showTranslationPicker = true
                },
                onOpenChurchFinder = {
                    scope.launch { drawerState.close() }
                    showChurchFinderSheet = true
                    viewModel.openChurchFinder()
                },
                onOpenSettings = {
                    scope.launch { drawerState.close() }
                    onOpenSettings()
                },
            )
        },
    ) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.app_name),
                        style = MaterialTheme.typography.titleMedium,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { scope.launch { drawerState.open() } }) {
                        Icon(
                            imageVector = Icons.Default.Menu,
                            contentDescription = stringResource(R.string.action_open_chat_history),
                        )
                    }
                },
                actions = {
                    // Verses panel icon — shown when there are related verses.
                    if (topBarPolicy.showVersesPanelInTopBar) {
                        IconButton(onClick = { showVersesPanel = true }) {
                            BadgedBox(
                                badge = {
                                    Badge { Text(uiState.allVerses.size.toString()) }
                                },
                            ) {
                                Icon(
                                    imageVector = Icons.AutoMirrored.Filled.MenuBook,
                                    contentDescription = stringResource(R.string.action_open_verses_panel),
                                )
                            }
                        }
                    }
                    // ── New chat ───────────────────────────────────────────────
                    IconButton(onClick = onNewConversation) {
                        Icon(
                            imageVector = Icons.Default.Add,
                            contentDescription = stringResource(R.string.action_new_chat),
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        snackbarHost = {
            SnackbarHost(snackbarHostState) { data ->
                Snackbar(snackbarData = data)
            }
        },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .imePadding()
                .navigationBarsPadding(),
        ) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    state = listState,
                ) {
                    if (uiState.messages.isEmpty()) {
                        item {
                            WelcomeBanner(
                                // BITB-081: an example question always sends on the
                                // first tap. No Turnstile-readiness gate here — the
                                // TurnstileInterceptor already waits for a token,
                                // fails open on timeout and retries once on 403.
                                onPromptSelected = { prompt ->
                                    onExamplePromptTapped(
                                        prompt = prompt,
                                        clearInput = { inputText = "" },
                                        sendMessage = viewModel::sendMessage,
                                    )
                                },
                                modifier = Modifier.padding(24.dp),
                            )
                        }
                    }

                    itemsIndexed(
                        items = uiState.messages,
                        key = { _, msg -> msg.id },
                    ) { index, message ->
                        val userMsg = if (message.role == Message.Role.ASSISTANT && index > 0) {
                            uiState.messages[index - 1].content
                        } else ""
                        ChatMessageItem(
                            message = message,
                            userMessage = userMsg,
                            chapterSheetState = chapterSheetState,
                            preferredTranslation = preferredTranslation.takeIf { it.isNotBlank() }
                                ?: uiState.detectedTranslation.takeIf { it.isNotBlank() }
                                ?: uiState.allVerses.firstOrNull()?.translation?.takeIf { it.isNotBlank() },
                            onLoadChapter = viewModel::loadChapter,
                            onDismissSheet = viewModel::clearChapterSheet,
                            onRetry = if (message.isError) viewModel::retryLastMessage else null,
                            onFeedback = { messageLocalId, rating, comment, reason ->
                                viewModel.submitFeedback(messageLocalId, rating, comment.ifBlank { null }, reason)
                            },
                            feedbackGiven = uiState.feedbackGiven[message.id],
                            verseRefRegex = verseRefRegex,
                            localizedToEnglish = localizedToEnglish,
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                    }

                    // Church-finder inline card — appears in the message list after 5 interactions.
                    if (uiState.showChurchFinderInlineCard) {
                        item(key = "church_finder_inline") {
                            ChurchFinderBanner(
                                onFindChurch = {
                                    showChurchFinderSheet = true
                                    viewModel.openChurchFinder()
                                },
                                onDismiss = viewModel::dismissChurchFinderBanner,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                            )
                        }
                    }
                }

                // Scroll-to-bottom FAB — visible when the user has scrolled up from the bottom.
                if (showScrollFab) {
                    FloatingActionButton(
                        onClick = {
                            scope.launch {
                                val lastIndex = listState.layoutInfo.totalItemsCount - 1
                                if (lastIndex >= 0) listState.animateScrollToItem(lastIndex)
                            }
                        },
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .padding(16.dp),
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                    ) {
                        Icon(
                            imageVector = Icons.Default.KeyboardArrowDown,
                            contentDescription = stringResource(R.string.action_scroll_to_bottom),
                        )
                    }
                }
            }

            HorizontalDivider()

            // Offline banner — shown whenever the device has no active internet connection.
            // The user can still read old session history, but sending new messages requires internet.
            if (uiState.isOffline) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ),
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            imageVector = Icons.Default.WifiOff,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onErrorContainer,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = stringResource(R.string.offline_notice),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                    }
                }
            }

            // "Start New Session" button — shown when the backend returns HTTP 429
            // with a session_lifetime_limit detail.  The invitation text is already
            // displayed as a proper assistant message in the chat above, so the
            // banner only needs to surface the action button.
            if (uiState.isSessionLimitReached) {
                Button(
                    onClick = { viewModel.startNewConversation() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                ) {
                    Text(stringResource(R.string.action_start_new_session))
                }
            }

            // Language-switch suggestion banner — shown when the backend detects typing
            // in a different language than the user's selected UI locale.
            uiState.languageSuggestion?.let { suggestedLocale ->
                LanguageSwitchBanner(
                    suggestedLocale = suggestedLocale,
                    onSwitch = { viewModel.setLocale(suggestedLocale) },
                    onDismiss = viewModel::dismissLanguageSuggestion,
                )
            }

            // Church-finder banner — shown above the input field after 3 interactions.
            if (uiState.showChurchFinderBanner) {
                ChurchFinderBanner(
                    onFindChurch = {
                        showChurchFinderSheet = true
                        viewModel.openChurchFinder()
                    },
                    onDismiss = viewModel::dismissChurchFinderBanner,
                )
            }

            // Turnstile WebView is mounted once globally in MainActivity so it
            // pre-warms during splash/conversations and outlives any single
            // screen.

            // Warm-up hint — shown when loading has been in-progress for >3 s with no response.
            if (uiState.isBackendWarming && uiState.isLoading) {
                Text(
                    text = stringResource(R.string.backend_warming_up),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }

            ChatInputField(
                value = inputText,
                onValueChange = { inputText = it },
                onSend = { text ->
                    viewModel.sendMessage(text)
                    inputText = ""
                },
                onStop = { viewModel.cancelStream() },
                isLoading = uiState.isLoading,
                isTurnstileReady = uiState.isTurnstileReady,
                isSessionLimitReached = uiState.isSessionLimitReached,
                maxLength = uiState.maxMessageLength,
            )
        }
    }
    } // ModalNavigationDrawer
}

@Composable
private fun ChatHistoryDrawer(
    conversations: List<org.voxquieta.app.domain.models.Conversation>,
    currentConversationId: String?,
    hasMessages: Boolean,
    onNewChat: () -> Unit,
    onSelectConversation: (String) -> Unit,
    onOpenAllConversations: () -> Unit,
    onClearConversation: () -> Unit,
    onOpenLanguagePicker: () -> Unit,
    onOpenTranslationPicker: () -> Unit,
    onOpenChurchFinder: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    ModalDrawerSheet {
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = stringResource(R.string.drawer_chat_history_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp),
        )
        NavigationDrawerItem(
            icon = {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = null,
                )
            },
            label = { Text(stringResource(R.string.action_new_chat)) },
            selected = false,
            onClick = onNewChat,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        if (conversations.isEmpty()) {
            Text(
                text = stringResource(R.string.drawer_no_conversations),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp),
            )
        } else {
            // Show up to 20 recent conversations; the "See all" link below
            // navigates to the full list when there are more.
            LazyColumn(
                modifier = Modifier
                    .weight(1f, fill = false)
                    .fillMaxWidth(),
            ) {
                items(
                    items = conversations.take(20),
                    key = { it.id },
                ) { conversation ->
                    NavigationDrawerItem(
                        label = {
                            Text(
                                text = conversation.title,
                                maxLines = 1,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        },
                        selected = conversation.id == currentConversationId,
                        onClick = { onSelectConversation(conversation.id) },
                        modifier = Modifier.padding(horizontal = 12.dp),
                        colors = NavigationDrawerItemDefaults.colors(),
                    )
                }
            }
            if (conversations.size > 20) {
                NavigationDrawerItem(
                    label = { Text(stringResource(R.string.drawer_see_all_conversations)) },
                    selected = false,
                    onClick = onOpenAllConversations,
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
            }
        }
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        if (hasMessages) {
            NavigationDrawerItem(
                icon = {
                    Icon(
                        imageVector = Icons.Default.Delete,
                        contentDescription = null,
                    )
                },
                label = { Text(stringResource(R.string.action_clear_conversation)) },
                selected = false,
                onClick = onClearConversation,
                modifier = Modifier.padding(horizontal = 12.dp),
            )
        }
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        NavigationDrawerItem(
            icon = {
                Icon(
                    imageVector = Icons.Default.Language,
                    contentDescription = null,
                )
            },
            label = { Text(stringResource(R.string.drawer_change_language)) },
            selected = false,
            onClick = onOpenLanguagePicker,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        NavigationDrawerItem(
            icon = {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.MenuBook,
                    contentDescription = null,
                )
            },
            label = { Text(stringResource(R.string.drawer_change_bible_version)) },
            selected = false,
            onClick = onOpenTranslationPicker,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        NavigationDrawerItem(
            icon = {
                Icon(
                    imageVector = Icons.Default.LocationOn,
                    contentDescription = null,
                )
            },
            label = { Text(stringResource(R.string.drawer_search_community)) },
            selected = false,
            onClick = onOpenChurchFinder,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        NavigationDrawerItem(
            icon = {
                Icon(
                    imageVector = Icons.Default.Settings,
                    contentDescription = null,
                )
            },
            label = { Text(stringResource(R.string.action_open_settings)) },
            selected = false,
            onClick = onOpenSettings,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        Spacer(modifier = Modifier.height(16.dp))
    }
}

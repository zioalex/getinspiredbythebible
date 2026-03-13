package com.bibleinspiration.presentation.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import com.bibleinspiration.R
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.presentation.components.ChatInputField
import com.bibleinspiration.presentation.components.ChatMessageItem
import com.bibleinspiration.presentation.components.TurnstileWebView
import com.bibleinspiration.presentation.components.WelcomeBanner
import com.bibleinspiration.presentation.viewmodels.ChatViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    conversationId: String? = null,
    onOpenSettings: () -> Unit = {},
    viewModel: ChatViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val chapterSheetState by viewModel.chapterSheetState.collectAsState()
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }
    var inputText by rememberSaveable { mutableStateOf("") }

    // Show the FAB when the user has scrolled up (i.e. not at the bottom).
    val showScrollFab by remember {
        derivedStateOf {
            listState.firstVisibleItemIndex > 0 || listState.firstVisibleItemScrollOffset > 0
        }
    }

    // Load existing conversation when navigated to a specific one.
    LaunchedEffect(conversationId) {
        when {
            conversationId == null || conversationId == "new" -> viewModel.startNewConversation()
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

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.app_name),
                        style = MaterialTheme.typography.titleMedium,
                    )
                },
                actions = {
                    if (uiState.messages.isNotEmpty()) {
                        IconButton(onClick = viewModel::clearConversation) {
                            Icon(
                                imageVector = Icons.Default.Delete,
                                contentDescription = stringResource(R.string.action_clear_conversation),
                            )
                        }
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = stringResource(R.string.action_open_settings),
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
                                onPromptSelected = { prompt -> inputText = prompt },
                                modifier = Modifier.padding(24.dp),
                            )
                        }
                    }

                    items(
                        items = uiState.messages,
                        key = { it.id },
                    ) { message ->
                        ChatMessageItem(
                            message = message,
                            chapterSheetState = chapterSheetState,
                            preferredTranslation = uiState.currentLocale.takeIf { it != "en" },
                            onLoadChapter = viewModel::loadChapter,
                            onDismissSheet = viewModel::clearChapterSheet,
                            onRetry = if (message.isError) viewModel::retryLastMessage else null,
                            onFeedback = { messageLocalId, rating -> viewModel.submitFeedback(messageLocalId, rating) },
                            feedbackGiven = uiState.feedbackGiven[message.id],
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                    }
                }

                // Scroll-to-bottom FAB — visible when the user has scrolled up.
                if (showScrollFab) {
                    FloatingActionButton(
                        onClick = {
                            scope.launch {
                                listState.animateScrollToItem(uiState.messages.size - 1)
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

            // "Take a Break" session-limit banner — shown when the backend returns HTTP 429
            // with a session_lifetime_limit detail.
            if (uiState.isSessionLimitReached) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    ),
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = stringResource(R.string.error_session_limit),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSecondaryContainer,
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Button(
                            onClick = { viewModel.startNewConversation() },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.action_start_new_session))
                        }
                    }
                }
            }

            TurnstileWebView(turnstileManager = viewModel.turnstileManager)

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
                isLoading = uiState.isLoading,
                isTurnstileReady = uiState.isTurnstileReady,
                isSessionLimitReached = uiState.isSessionLimitReached,
            )
        }
    }
}

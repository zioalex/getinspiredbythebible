package com.bibleinspiration.presentation.screens

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
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
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
    val snackbarHostState = remember { SnackbarHostState() }
    var inputText by rememberSaveable { mutableStateOf("") }

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
            if (!hasInlineRetry) {
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
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
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
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                }
            }

            HorizontalDivider()

            TurnstileWebView(turnstileManager = viewModel.turnstileManager)

            ChatInputField(
                value = inputText,
                onValueChange = { inputText = it },
                onSend = { text ->
                    viewModel.sendMessage(text)
                    inputText = ""
                },
                isLoading = uiState.isLoading,
                isTurnstileReady = uiState.isTurnstileReady,
            )
        }
    }
}

package org.voxquieta.app.presentation.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import org.voxquieta.app.BuildConfig
import org.voxquieta.app.R
import org.voxquieta.app.presentation.components.ContactFormBottomSheet
import org.voxquieta.app.presentation.components.DiagnosticReportBottomSheet
import org.voxquieta.app.presentation.viewmodels.ChatViewModel
import org.voxquieta.app.utils.privacyUrl
import org.voxquieta.app.utils.termsUrl

/** Theme option shown in the settings section. */
private data class ThemeOption(
    val mode: String,
    val labelRes: Int,
)

private val themeOptions = listOf(
    ThemeOption("light", R.string.settings_theme_light),
    ThemeOption("dark", R.string.settings_theme_dark),
    ThemeOption("system", R.string.settings_theme_system),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onNavigateBack: () -> Unit,
    onOpenChangelog: () -> Unit = {},
    viewModel: ChatViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val currentThemeMode = uiState.themeMode
    val availableTranslations by viewModel.availableTranslations.collectAsState()
    val preferredTranslation by viewModel.preferredTranslation.collectAsState()
    val contactFormState by viewModel.contactFormState.collectAsState()
    val diagnosticReportState by viewModel.diagnosticReportState.collectAsState()
    val context = LocalContext.current
    val currentLanguage = LocalConfiguration.current.locales[0].language
    var showContactSheet by rememberSaveable { mutableStateOf(false) }
    var showDiagnosticSheet by rememberSaveable { mutableStateOf(false) }
    var showClearHistoryDialog by rememberSaveable { mutableStateOf(false) }

    // Resolve current translation display name for the read-only row.
    val currentTranslationName = when {
        preferredTranslation.isBlank() -> stringResource(R.string.bible_translation_default)
        else -> availableTranslations
            .firstOrNull { it.id == preferredTranslation }
            ?.name
            ?: preferredTranslation.uppercase()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.settings_title),
                        style = MaterialTheme.typography.titleMedium,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_cancel),
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            // ── Appearance section ─────────────────────────────────────────────
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = stringResource(R.string.settings_theme_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            themeOptions.forEach { option ->
                ThemeRow(
                    labelRes = option.labelRes,
                    selected = option.mode == currentThemeMode,
                    onSelect = { viewModel.setThemeMode(option.mode) },
                )
            }

            // ── Bible section ──────────────────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = stringResource(R.string.bible_translation_section),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            // Read-only row showing the active translation; the in-chat chip is
            // the canonical place to change it.
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.settings_current_translation),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        text = stringResource(R.string.settings_bible_change_from_chat),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = currentTranslationName,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            // ── Data & Privacy section ─────────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = stringResource(R.string.settings_data_privacy_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = { showClearHistoryDialog = true },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MaterialTheme.colorScheme.error,
                ),
            ) {
                Text(stringResource(R.string.action_clear_all_conversations))
            }

            // ── Support section ────────────────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = stringResource(R.string.settings_support_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = { showDiagnosticSheet = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.action_send_diagnostic_report))
            }

            // ── Get in Touch section ───────────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = stringResource(R.string.contact_section_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = { showContactSheet = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.contact_open_button))
            }

            // ── About section ──────────────────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = stringResource(R.string.settings_about_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.settings_version),
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = BuildConfig.VERSION_NAME,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(
                onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(privacyUrl(currentLanguage)))
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = stringResource(R.string.settings_privacy_policy),
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
            TextButton(
                onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(termsUrl(currentLanguage)))
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = stringResource(R.string.settings_terms_of_service),
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
            TextButton(
                onClick = onOpenChangelog,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = stringResource(R.string.settings_changelog_link),
                    style = MaterialTheme.typography.bodyLarge,
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }

        // Turnstile widget is mounted globally in MainActivity, so a token is
        // already cached by the time the user reaches this screen.

        // ── Clear history confirmation dialog ──────────────────────────────────
        if (showClearHistoryDialog) {
            AlertDialog(
                onDismissRequest = { showClearHistoryDialog = false },
                title = { Text(stringResource(R.string.settings_clear_history_title)) },
                text = { Text(stringResource(R.string.settings_clear_history_message)) },
                confirmButton = {
                    TextButton(
                        onClick = {
                            viewModel.clearAllConversations()
                            showClearHistoryDialog = false
                        },
                        colors = ButtonDefaults.textButtonColors(
                            contentColor = MaterialTheme.colorScheme.error,
                        ),
                    ) {
                        Text(stringResource(R.string.action_clear_all_conversations))
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showClearHistoryDialog = false }) {
                        Text(stringResource(R.string.action_cancel))
                    }
                },
            )
        }

        // ── Contact Form bottom sheet ──────────────────────────────────────────
        if (showContactSheet) {
            ContactFormBottomSheet(
                formState = contactFormState,
                onSubmit = { subject, message, email ->
                    viewModel.submitContact(subject, message, email)
                },
                onDismiss = {
                    showContactSheet = false
                    viewModel.resetContactForm()
                },
            )
        }

        // ── Diagnostic report bottom sheet ─────────────────────────────────────
        if (showDiagnosticSheet) {
            DiagnosticReportBottomSheet(
                formState = diagnosticReportState,
                onSendEmail = { doing, expected, email ->
                    viewModel.sendDiagnosticEmail(doing, expected, email)
                },
                onSaveLocally = {
                    viewModel.saveDiagnosticLogLocally(context)
                    showDiagnosticSheet = false
                    viewModel.resetDiagnosticReport()
                },
                onDismiss = {
                    showDiagnosticSheet = false
                    viewModel.resetDiagnosticReport()
                },
            )
        }
    }
}

@Composable
private fun ThemeRow(
    labelRes: Int,
    selected: Boolean,
    onSelect: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(
            selected = selected,
            onClick = onSelect,
        )
        Text(
            text = stringResource(labelRes),
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}

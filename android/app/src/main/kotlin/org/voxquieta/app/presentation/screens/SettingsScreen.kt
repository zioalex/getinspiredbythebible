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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import org.voxquieta.app.BuildConfig
import org.voxquieta.app.R
import org.voxquieta.app.presentation.components.ContactFormBottomSheet
import org.voxquieta.app.presentation.components.ContactFormState
import org.voxquieta.app.presentation.components.TurnstileWebView
import org.voxquieta.app.presentation.viewmodels.ChatViewModel

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
    viewModel: ChatViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val currentThemeMode = uiState.themeMode
    val availableTranslations by viewModel.availableTranslations.collectAsState()
    val preferredTranslation by viewModel.preferredTranslation.collectAsState()
    val contactFormState by viewModel.contactFormState.collectAsState()
    val context = LocalContext.current
    var showContactSheet by rememberSaveable { mutableStateOf(false) }

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
            // ── Theme section ─────────────────────────────────────────────────
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

            // ── Bible Translation section ──────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = stringResource(R.string.bible_translation_section),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            if (availableTranslations.isEmpty()) {
                // Loading or error state — show a single "Default" option selected.
                TranslationRow(
                    label = stringResource(R.string.bible_translation_default),
                    sublabel = null,
                    selected = true,
                    onSelect = { viewModel.setPreferredTranslation("") },
                )
            } else {
                // "Default" (no preference) row first.
                TranslationRow(
                    label = stringResource(R.string.bible_translation_default),
                    sublabel = null,
                    selected = preferredTranslation.isBlank(),
                    onSelect = { viewModel.setPreferredTranslation("") },
                )
                availableTranslations.forEach { translation ->
                    TranslationRow(
                        label = translation.name,
                        sublabel = translation.language.uppercase(),
                        selected = translation.id == preferredTranslation,
                        onSelect = { viewModel.setPreferredTranslation(translation.id) },
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // ── Support section ────────────────────────────────────────────────
            Text(
                text = stringResource(R.string.settings_support_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = { viewModel.shareDebugLogs(context) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.action_send_diagnostic_report))
            }

            // ── Contact section ────────────────────────────────────────────────
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
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.PRIVACY_POLICY_URL))
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = stringResource(R.string.settings_privacy_policy),
                    style = MaterialTheme.typography.bodyLarge,
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }

        // ── Turnstile bot-protection widget (invisible, 1×1 dp) ───────────────
        // Ensures a valid token is available when the contact form is submitted,
        // even when the user navigates here without first visiting ChatScreen.
        // Mirrors the web app where the Turnstile widget is on the same page as
        // the contact form.
        TurnstileWebView(turnstileManager = viewModel.turnstileManager)

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

@Composable
private fun TranslationRow(
    label: String,
    sublabel: String?,
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
        Column(modifier = Modifier.padding(start = 8.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge,
            )
            if (sublabel != null) {
                Text(
                    text = sublabel,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

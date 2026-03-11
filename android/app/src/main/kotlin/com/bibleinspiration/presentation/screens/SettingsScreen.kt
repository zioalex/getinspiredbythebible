package com.bibleinspiration.presentation.screens

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
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.bibleinspiration.R
import com.bibleinspiration.presentation.viewmodels.ChatViewModel

/** Language option shown in the settings list. */
private data class LanguageOption(
    val code: String,
    val displayName: String,
)

private val languageOptions = listOf(
    LanguageOption("en", "🇬🇧 English"),
    LanguageOption("it", "🇮🇹 Italiano"),
    LanguageOption("de", "🇩🇪 Deutsch"),
    LanguageOption("es", "🇪🇸 Español"),
    LanguageOption("fr", "🇫🇷 Français"),
    LanguageOption("ar", "🇸🇦 العربية"),
    LanguageOption("pt", "🇧🇷 Português"),
)

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
    val currentLocale = uiState.currentLocale
    val currentThemeMode = uiState.themeMode
    val availableTranslations by viewModel.availableTranslations.collectAsState()
    val preferredTranslation by viewModel.preferredTranslation.collectAsState()

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
            // ── Language section ──────────────────────────────────────────────
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = stringResource(R.string.settings_language_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = stringResource(R.string.settings_language_subtitle),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(8.dp))
            languageOptions.forEach { option ->
                LanguageRow(
                    option = option,
                    selected = option.code == currentLocale,
                    onSelect = { viewModel.setLocale(option.code) },
                )
            }

            // ── Theme section ─────────────────────────────────────────────────
            Spacer(modifier = Modifier.height(24.dp))
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
        }
    }
}

@Composable
private fun LanguageRow(
    option: LanguageOption,
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
            text = option.displayName,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(start = 8.dp),
        )
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

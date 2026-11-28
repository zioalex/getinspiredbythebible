package org.voxquieta.app.presentation.components

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.jeziellago.compose.markdowntext.MarkdownText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.voxquieta.app.R

internal fun shouldShowWhatsNew(storedVersionCode: Int, currentVersionCode: Int): Boolean =
    storedVersionCode != -1 && storedVersionCode < currentVersionCode

/**
 * One release's curated end-user notes (BITB-175), from assets/whats_new.json, which the
 * generateWhatsNewJson Gradle task builds from release-notes/<version>/<locale>.md. `body` is
 * the English text; `notes` holds every translated locale.
 */
@Serializable
data class WhatsNewEntry(
    val version: String,
    val date: String = "",
    val body: String = "",
    val notes: Map<String, String> = emptyMap(),
)

internal const val WHATS_NEW_ASSET = "whats_new.json"

private val whatsNewJson = Json { ignoreUnknownKeys = true }

/** The release's notes, or null when the asset is empty, malformed or has no text. */
internal fun parseWhatsNew(raw: String): WhatsNewEntry? =
    runCatching { whatsNewJson.decodeFromString<List<WhatsNewEntry>>(raw) }
        .getOrDefault(emptyList())
        .firstOrNull()
        ?.takeIf { pickWhatsNewNotes(it, "en").isNotBlank() }

/** The notes in the UI language, else English. Never the raw developer CHANGELOG. */
internal fun pickWhatsNewNotes(entry: WhatsNewEntry, language: String): String =
    entry.notes[language] ?: entry.notes["en"] ?: entry.body

/** Reads assets/whats_new.json; null when this release has no curated notes. */
fun loadWhatsNew(context: Context): WhatsNewEntry? =
    runCatching { context.assets.open(WHATS_NEW_ASSET).bufferedReader().use { it.readText() } }
        .getOrNull()
        ?.let(::parseWhatsNew)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WhatsNewBottomSheet(onDismiss: () -> Unit, onSeeAll: () -> Unit) {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val language = LocalConfiguration.current.locales[0].language
    var entry by remember { mutableStateOf<WhatsNewEntry?>(null) }
    var loaded by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        entry = withContext(Dispatchers.IO) { loadWhatsNew(context) }
        loaded = true
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .navigationBarsPadding()
                .padding(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.whats_new_title),
                style = MaterialTheme.typography.headlineSmall,
            )

            val currentEntry = entry
            if (currentEntry != null) {
                Text(
                    text = currentEntry.version,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                MarkdownText(
                    markdown = pickWhatsNewNotes(currentEntry, language),
                    style = MaterialTheme.typography.bodyMedium,
                    linkColor = MaterialTheme.colorScheme.primary,
                    onLinkClicked = { url -> uriHandler.openUri(url) },
                )
            } else if (loaded) {
                Text(
                    text = stringResource(R.string.changelog_empty),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Row(modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onDismiss) {
                    Text(text = stringResource(R.string.whats_new_dismiss))
                }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onSeeAll) {
                    Text(text = stringResource(R.string.whats_new_see_all))
                }
            }
        }
    }
}

package org.voxquieta.app.presentation.components

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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.jeziellago.compose.markdowntext.MarkdownText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import org.voxquieta.app.R
import org.voxquieta.app.presentation.screens.ChangelogEntry

internal fun shouldShowWhatsNew(storedVersionCode: Int, currentVersionCode: Int): Boolean =
    storedVersionCode != -1 && storedVersionCode < currentVersionCode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WhatsNewBottomSheet(onDismiss: () -> Unit, onSeeAll: () -> Unit) {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    var entry by remember { mutableStateOf<ChangelogEntry?>(null) }
    var loaded by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        entry = withContext(Dispatchers.IO) {
            runCatching {
                val raw = context.assets.open("changelog.json")
                    .bufferedReader().use { it.readText() }
                Json { ignoreUnknownKeys = true }.decodeFromString<List<ChangelogEntry>>(raw)
            }.getOrDefault(emptyList()).firstOrNull()
        }
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
                    markdown = currentEntry.body,
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

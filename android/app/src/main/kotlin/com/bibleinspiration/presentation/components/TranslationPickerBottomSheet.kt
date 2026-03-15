package com.bibleinspiration.presentation.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.bibleinspiration.R
import com.bibleinspiration.data.remote.models.TranslationDto

/**
 * A `ModalBottomSheet` allowing the user to select a preferred Bible translation.
 *
 * Mirrors the translation `<select>` dropdown in the web header.  The sheet lists:
 *  - **Auto** (blank ID) — the backend picks the best translation for the current locale.
 *  - One row per available [TranslationDto] fetched from the backend.
 *
 * @param availableTranslations  List of translations returned by the backend.
 * @param selectedTranslationId  Currently selected translation ID, or blank for "Auto".
 * @param onSelectTranslation    Called with the chosen ID when the user taps a row.
 * @param onDismiss              Called when the sheet is dismissed without a selection.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranslationPickerBottomSheet(
    availableTranslations: List<TranslationDto>,
    selectedTranslationId: String,
    onSelectTranslation: (id: String) -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp)
                .padding(bottom = 16.dp),
        ) {
            Text(
                text = stringResource(R.string.translation_picker_title),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 4.dp),
            )
            Text(
                text = stringResource(R.string.translation_picker_subtitle),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider()

            // Scrollable list — important for devices with many translations.
            LazyColumn {
                // "Auto" row — no explicit preference; backend chooses based on locale.
                item(key = "auto") {
                    TranslationPickerRow(
                        label = stringResource(R.string.translation_auto),
                        sublabel = stringResource(R.string.translation_auto_description),
                        selected = selectedTranslationId.isBlank(),
                        onClick = { onSelectTranslation("") },
                    )
                }

                items(availableTranslations, key = { it.id }) { translation ->
                    TranslationPickerRow(
                        label = translation.name,
                        sublabel = translation.language.uppercase(),
                        selected = translation.id == selectedTranslationId,
                        onClick = { onSelectTranslation(translation.id) },
                    )
                }
            }
        }
    }
}

@Composable
private fun TranslationPickerRow(
    label: String,
    sublabel: String?,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(
            selected = selected,
            onClick = onClick,
        )
        Column(modifier = Modifier.padding(start = 8.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge,
                color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
            )
            if (!sublabel.isNullOrBlank()) {
                Text(
                    text = sublabel,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

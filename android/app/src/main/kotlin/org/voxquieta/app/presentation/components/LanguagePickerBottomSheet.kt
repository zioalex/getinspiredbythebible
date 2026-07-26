package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
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
import org.voxquieta.app.R
import org.voxquieta.app.presentation.screens.LANGUAGE_OPTIONS

/**
 * A `ModalBottomSheet` allowing the user to select the app's UI language.
 *
 * Mirrors [TranslationPickerBottomSheet]'s structure: one row per entry in
 * [LANGUAGE_OPTIONS], with the currently active locale marked selected.
 *
 * @param currentLocale     Currently active UI locale code (e.g. "en").
 * @param onSelectLocale    Called with the chosen locale code when the user taps a row.
 * @param onDismiss         Called when the sheet is dismissed without a selection.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LanguagePickerBottomSheet(
    currentLocale: String,
    onSelectLocale: (code: String) -> Unit,
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
                text = stringResource(R.string.action_select_language),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 12.dp),
            )

            LazyColumn {
                items(LANGUAGE_OPTIONS, key = { it.code }) { option ->
                    LanguagePickerRow(
                        label = option.displayName,
                        selected = option.code == currentLocale,
                        onClick = { onSelectLocale(option.code) },
                    )
                }
            }
        }
    }
}

@Composable
private fun LanguagePickerRow(
    label: String,
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
        Text(
            text = label,
            style = MaterialTheme.typography.bodyLarge,
            color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}

package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SheetState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

/**
 * Bottom sheet that lets the user file a bug report. Collects two short answers
 * (what they were doing / what they expected) and offers two actions:
 *
 *  1. Primary — submit the report through the built-in contact pipeline
 *     (same backend path the contact form uses). The sheet stays open and
 *     reflects [formState] so the user sees a spinner, a success screen, or
 *     an inline error message rather than the sheet silently closing.
 *  2. Secondary — save the full diagnostic log locally via the system share
 *     sheet.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiagnosticReportBottomSheet(
    formState: ContactFormState,
    onSendEmail: (whatWereYouDoing: String, whatDidYouExpect: String) -> Unit,
    onSaveLocally: () -> Unit,
    onDismiss: () -> Unit,
    sheetState: SheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
) {
    var doingInput by rememberSaveable { mutableStateOf("") }
    var expectedInput by rememberSaveable { mutableStateOf("") }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp)
                .padding(bottom = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = Icons.Default.BugReport,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.size(24.dp),
                )
                Column {
                    Text(
                        text = stringResource(R.string.diagnostic_title),
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(
                        text = stringResource(R.string.diagnostic_subtitle),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            // ── Success state ─────────────────────────────────────────────────
            if (formState is ContactFormState.Success) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = stringResource(R.string.diagnostic_success_title),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Text(
                        text = stringResource(R.string.diagnostic_success_description),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.action_cancel))
                    }
                }
                return@Column
            }

            val isSubmitting = formState is ContactFormState.Submitting

            OutlinedTextField(
                value = doingInput,
                onValueChange = { doingInput = it },
                label = { Text(stringResource(R.string.diagnostic_doing_label)) },
                placeholder = { Text(stringResource(R.string.diagnostic_doing_placeholder)) },
                minLines = 3,
                maxLines = 6,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                enabled = !isSubmitting,
            )

            OutlinedTextField(
                value = expectedInput,
                onValueChange = { expectedInput = it },
                label = { Text(stringResource(R.string.diagnostic_expected_label)) },
                placeholder = { Text(stringResource(R.string.diagnostic_expected_placeholder)) },
                minLines = 3,
                maxLines = 6,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Default),
                enabled = !isSubmitting,
            )

            Text(
                text = stringResource(R.string.diagnostic_attachment_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            // ── Error ─────────────────────────────────────────────────────────
            if (formState is ContactFormState.Error) {
                Text(
                    text = formState.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            Button(
                onClick = { onSendEmail(doingInput, expectedInput) },
                modifier = Modifier.fillMaxWidth(),
                enabled = !isSubmitting,
            ) {
                if (isSubmitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                } else {
                    Text(stringResource(R.string.diagnostic_send_email_button))
                }
            }

            // Secondary, less prominent option to save the raw log without sending.
            TextButton(
                onClick = onSaveLocally,
                modifier = Modifier.fillMaxWidth(),
                enabled = !isSubmitting,
            ) {
                Text(
                    text = stringResource(R.string.diagnostic_save_locally_link),
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            Spacer(Modifier.height(8.dp))
        }
    }
}

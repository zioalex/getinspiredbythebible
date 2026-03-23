package com.bibleinspiration.presentation.components

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
import androidx.compose.material.icons.filled.Email
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SheetState
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.bibleinspiration.R
import com.bibleinspiration.data.remote.models.ContactSubject

/**
 * Sealed state for the contact form submission lifecycle.
 */
sealed class ContactFormState {
    data object Idle : ContactFormState()
    data object Submitting : ContactFormState()
    data object Success : ContactFormState()
    data class Error(val message: String) : ContactFormState()
}

/**
 * Subject option shown in the dropdown.
 */
private data class SubjectOption(val value: String, val labelRes: Int)

private val subjectOptions = listOf(
    SubjectOption(ContactSubject.SPIRITUAL, R.string.contact_subject_spiritual),
    SubjectOption(ContactSubject.FEEDBACK, R.string.contact_subject_feedback),
    SubjectOption(ContactSubject.BUG, R.string.contact_subject_bug),
    SubjectOption(ContactSubject.FEATURE, R.string.contact_subject_feature),
    SubjectOption(ContactSubject.OTHER, R.string.contact_subject_other),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContactFormBottomSheet(
    formState: ContactFormState,
    onSubmit: (subject: String, message: String, email: String?) -> Unit,
    onDismiss: () -> Unit,
    sheetState: SheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
) {
    var selectedSubject by remember { mutableStateOf(subjectOptions.first()) }
    var subjectDropdownExpanded by rememberSaveable { mutableStateOf(false) }
    var emailInput by rememberSaveable { mutableStateOf("") }
    var messageInput by rememberSaveable { mutableStateOf("") }

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
            // ── Header ───────────────────────────────────────────────────────
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = Icons.Default.Email,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.size(24.dp),
                )
                Column {
                    Text(
                        text = stringResource(R.string.contact_title),
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(
                        text = stringResource(R.string.contact_subtitle),
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
                        text = stringResource(R.string.contact_success_title),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Text(
                        text = stringResource(R.string.contact_success_description),
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

            // ── Subject dropdown ──────────────────────────────────────────────
            ExposedDropdownMenuBox(
                expanded = subjectDropdownExpanded,
                onExpandedChange = { subjectDropdownExpanded = it },
            ) {
                OutlinedTextField(
                    value = stringResource(selectedSubject.labelRes),
                    onValueChange = {},
                    readOnly = true,
                    label = { Text(stringResource(R.string.contact_subject_label)) },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = subjectDropdownExpanded) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(MenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(
                    expanded = subjectDropdownExpanded,
                    onDismissRequest = { subjectDropdownExpanded = false },
                ) {
                    subjectOptions.forEach { option ->
                        DropdownMenuItem(
                            text = { Text(stringResource(option.labelRes)) },
                            onClick = {
                                selectedSubject = option
                                subjectDropdownExpanded = false
                            },
                            contentPadding = ExposedDropdownMenuDefaults.ItemContentPadding,
                        )
                    }
                }
            }

            // ── Email input (optional) ────────────────────────────────────────
            OutlinedTextField(
                value = emailInput,
                onValueChange = { emailInput = it },
                label = { Text(stringResource(R.string.contact_email_label)) },
                placeholder = { Text(stringResource(R.string.contact_email_placeholder)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Next,
                ),
            )

            // ── Message input ─────────────────────────────────────────────────
            OutlinedTextField(
                value = messageInput,
                onValueChange = { messageInput = it },
                label = { Text(stringResource(R.string.contact_message_label)) },
                placeholder = { Text(stringResource(R.string.contact_message_placeholder)) },
                minLines = 4,
                maxLines = 8,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Default),
            )

            // ── Privacy note ──────────────────────────────────────────────────
            Text(
                text = stringResource(R.string.contact_privacy_note),
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

            // ── Send button ───────────────────────────────────────────────────
            Button(
                onClick = {
                    if (messageInput.isNotBlank()) {
                        onSubmit(
                            selectedSubject.value,
                            messageInput,
                            emailInput.ifBlank { null },
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = messageInput.isNotBlank() && formState !is ContactFormState.Submitting,
            ) {
                if (formState is ContactFormState.Submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                } else {
                    Text(stringResource(R.string.contact_send_button))
                }
            }

            Spacer(Modifier.height(8.dp))
        }
    }
}

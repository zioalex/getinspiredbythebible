package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

@Composable
fun ChatInputField(
    value: String,
    onValueChange: (String) -> Unit,
    onSend: (String) -> Unit,
    modifier: Modifier = Modifier,
    isLoading: Boolean = false,
    isTurnstileReady: Boolean = true,
    isSessionLimitReached: Boolean = false,
    onStop: () -> Unit = {},
) {
    val canSend = !isLoading && isTurnstileReady && !isSessionLimitReached

    fun submit() {
        if (value.isNotBlank() && canSend) {
            onSend(value)
        }
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.weight(1f),
            placeholder = { Text(stringResource(R.string.chat_input_hint)) },
            shape = RoundedCornerShape(24.dp),
            // Multi-line: Enter inserts a newline (ImeAction.Default), the Send
            // button is the only way to submit. maxLines caps visible height.
            maxLines = 5,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Default),
            // Keep the text field editable while generation is running so the
            // user can already type the next message. We just block submit.
            enabled = !isSessionLimitReached,
        )

        Spacer(Modifier.width(8.dp))

        if (isLoading) {
            IconButton(onClick = onStop) {
                Icon(
                    imageVector = Icons.Filled.Stop,
                    contentDescription = stringResource(R.string.chat_stop_button),
                    tint = MaterialTheme.colorScheme.primary,
                )
            }
        } else {
            IconButton(
                onClick = { submit() },
                enabled = value.isNotBlank() && canSend,
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Send,
                    contentDescription = stringResource(R.string.chat_send_button),
                    tint = if (value.isNotBlank() && canSend) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.outline
                    },
                )
            }
        }
    }
}

package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

/**
 * Session-limit actions (BITB-156, mirrors the web pairing in ChatIsland.tsx).
 * "Continue this conversation" is the primary, non-destructive action (keeps the
 * thread, rotates only the session id); "Start New Session" is the secondary,
 * destructive one (clears the thread).
 */
@Composable
fun SessionLimitActions(
    onContinueConversation: () -> Unit,
    onStartNewSession: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Button(
            onClick = onContinueConversation,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.action_continue_conversation))
        }
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedButton(
            onClick = onStartNewSession,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.action_start_new_session))
        }
    }
}

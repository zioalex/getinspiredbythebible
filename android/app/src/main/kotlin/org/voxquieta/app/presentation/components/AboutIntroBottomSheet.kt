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
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

/**
 * One-time "Why Vox Quieta" intro sheet (BITB-082) — the Android counterpart of the web
 * AboutIntroModal (BITB-077). Shown once ever per install (see [org.voxquieta.app.MainActivity]'s
 * `about_intro_seen` flag), not once per version like [WhatsNewBottomSheet].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutIntroBottomSheet(onDismiss: () -> Unit, onLearnMore: () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        AboutIntroContent(onDismiss = onDismiss, onLearnMore = onLearnMore)
    }
}

/**
 * The sheet's content, split out from [AboutIntroBottomSheet] so it can be mounted directly
 * in Robolectric-backed Compose tests — [ModalBottomSheet] itself has known rendering caveats
 * under Robolectric (see [VerseDetailBottomSheet] / [VerseDetailContent] for the same split).
 */
@Composable
internal fun AboutIntroContent(onDismiss: () -> Unit, onLearnMore: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
            .navigationBarsPadding()
            .padding(bottom = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = stringResource(R.string.about_intro_title),
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            text = stringResource(R.string.about_intro_body),
            style = MaterialTheme.typography.bodyMedium,
        )

        Row(modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = onDismiss) {
                Text(text = stringResource(R.string.about_intro_secondary_cta))
            }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onLearnMore) {
                Text(text = stringResource(R.string.about_intro_primary_cta))
            }
        }
    }
}

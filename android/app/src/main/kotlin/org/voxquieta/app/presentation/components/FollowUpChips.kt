package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

/**
 * One-tap suggested follow-up question chips rendered under the LATEST
 * assistant message only (BITB-149, Android consumer of the BITB-080
 * backend/web contract). Mirrors `frontend/src/components/FollowUpSuggestions.tsx`:
 * degrades silently (no spinner, no empty row) when there are no suggestions.
 *
 * @param suggestions The 2-3 suggested follow-up questions to render as chips.
 * @param onSelect Called with the tapped suggestion's exact text.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun FollowUpChips(
    suggestions: List<String>,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (suggestions.isEmpty()) return

    val groupDesc = stringResource(R.string.chat_follow_ups_label)
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = modifier.semantics(mergeDescendants = false) {
            contentDescription = groupDesc
        },
    ) {
        suggestions.forEach { suggestion ->
            SuggestionChip(
                onClick = { onSelect(suggestion) },
                label = { Text(suggestion) },
            )
        }
    }
}

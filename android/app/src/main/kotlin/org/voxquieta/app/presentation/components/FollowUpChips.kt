package org.voxquieta.app.presentation.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

/**
 * Follow-up chip palette (BITB-278): container/label/border colors for one
 * theme mode.
 *
 * Light values mirror the web chip EXACTLY
 * (`frontend/src/components/FollowUpSuggestions.tsx`:
 * `bg-white border-primary-200 text-gray-700`); dark values keep the stock
 * dark-scheme neutral trio (surfaceVariant/onSurfaceVariant/outlineVariant
 * family) because the web chip styling is light-only — `bg-white` is
 * hardcoded there, so no web dark reference exists. The dark scheme's blue
 * `primary` (#90CAF9) is deliberately NOT used for the border: it breaks the
 * warm web palette.
 */
internal data class FollowUpChipPalette(
    val containerColor: Color,
    val labelColor: Color,
    val borderColor: Color,
)

/**
 * Pure (Compose-free) palette resolver for [FollowUpChips] so the exact
 * values are pinnable by JVM unit tests (BITB-278 FR5 — regression guard for
 * the user-reported "colors were a bit off" bug).
 */
internal fun followUpChipPalette(darkTheme: Boolean): FollowUpChipPalette =
    if (darkTheme) {
        FollowUpChipPalette(
            containerColor = Color(0xFF2C2C2C), // dark scheme surfaceVariant
            labelColor = Color(0xFFBDBDBD),     // dark scheme onSurfaceVariant
            borderColor = Color(0xFF49454F),    // dark scheme outlineVariant
        )
    } else {
        FollowUpChipPalette(
            containerColor = Color(0xFFFFFFFF), // web bg-white
            labelColor = Color(0xFF374151),     // web text-gray-700
            borderColor = Color(0xFFE6D0B8),    // web primary-200
        )
    }

/**
 * One-tap suggested follow-up question chips rendered under the LATEST
 * assistant message only (BITB-149, Android consumer of the BITB-080
 * backend/web contract). Mirrors `frontend/src/components/FollowUpSuggestions.tsx`:
 * degrades silently (no spinner, no empty row) when there are no suggestions.
 *
 * Rendering is gated by the BITB-080 rollout flag
 * ([org.voxquieta.app.BuildConfig.CHAT_FOLLOW_UPS_ENABLED], mirrored in
 * [org.voxquieta.app.presentation.screens.shouldShowFollowUps] and the
 * ChatViewModel state exposure): default ON since BITB-278, killable
 * per-build with `-PchatFollowUpsEnabled=false`.
 *
 * Chip colors match the web chip in light mode (see [FollowUpChipPalette])
 * and stay dark-scheme-neutral in dark mode.
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

    // Follow the ACTIVE color scheme, not the raw system setting, so the
    // in-app theme override (ChatViewModel themeMode: dark/light/system)
    // cannot desync the chips from the rest of the themed chat surface —
    // same scheme-driven per-mode mechanism ChatMessageItem uses to match
    // web styling.
    val darkTheme = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val palette = followUpChipPalette(darkTheme)

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
                colors = SuggestionChipDefaults.suggestionChipColors(
                    containerColor = palette.containerColor,
                    labelColor = palette.labelColor,
                ),
                border = BorderStroke(1.dp, palette.borderColor),
            )
        }
    }
}

package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R

@Composable
fun WelcomeBanner(
    onPromptSelected: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val allSuggestions = listOf(
        stringResource(R.string.prompt_suggestion_1),
        stringResource(R.string.prompt_suggestion_2),
        stringResource(R.string.prompt_suggestion_3),
        stringResource(R.string.prompt_suggestion_4),
        stringResource(R.string.prompt_suggestion_5),
        stringResource(R.string.prompt_suggestion_6),
        stringResource(R.string.prompt_suggestion_7),
        stringResource(R.string.prompt_suggestion_8),
        stringResource(R.string.prompt_suggestion_9),
        stringResource(R.string.prompt_suggestion_10),
        stringResource(R.string.prompt_suggestion_11),
        stringResource(R.string.prompt_suggestion_12),
        stringResource(R.string.prompt_suggestion_13),
        stringResource(R.string.prompt_suggestion_14),
        stringResource(R.string.prompt_suggestion_15),
        stringResource(R.string.prompt_suggestion_16),
        stringResource(R.string.prompt_suggestion_17),
        stringResource(R.string.prompt_suggestion_18),
        stringResource(R.string.prompt_suggestion_19),
        stringResource(R.string.prompt_suggestion_20),
        stringResource(R.string.prompt_suggestion_21),
        stringResource(R.string.prompt_suggestion_22),
        stringResource(R.string.prompt_suggestion_23),
        stringResource(R.string.prompt_suggestion_24),
        stringResource(R.string.prompt_suggestion_25),
        stringResource(R.string.prompt_suggestion_26),
        stringResource(R.string.prompt_suggestion_27),
        stringResource(R.string.prompt_suggestion_28),
        stringResource(R.string.prompt_suggestion_29),
        stringResource(R.string.prompt_suggestion_30),
        stringResource(R.string.prompt_suggestion_31),
        stringResource(R.string.prompt_suggestion_32),
        stringResource(R.string.prompt_suggestion_33),
        stringResource(R.string.prompt_suggestion_34),
        stringResource(R.string.prompt_suggestion_35),
        stringResource(R.string.prompt_suggestion_36),
        stringResource(R.string.prompt_suggestion_37),
        stringResource(R.string.prompt_suggestion_38),
        stringResource(R.string.prompt_suggestion_39),
        stringResource(R.string.prompt_suggestion_40),
        stringResource(R.string.prompt_suggestion_41),
        stringResource(R.string.prompt_suggestion_42),
        stringResource(R.string.prompt_suggestion_43),
        stringResource(R.string.prompt_suggestion_44),
        stringResource(R.string.prompt_suggestion_45),
        stringResource(R.string.prompt_suggestion_46),
        stringResource(R.string.prompt_suggestion_47),
        stringResource(R.string.prompt_suggestion_48),
        stringResource(R.string.prompt_suggestion_49),
        stringResource(R.string.prompt_suggestion_50),
        stringResource(R.string.prompt_suggestion_51),
        stringResource(R.string.prompt_suggestion_52),
        stringResource(R.string.prompt_suggestion_53),
        stringResource(R.string.prompt_suggestion_54),
        stringResource(R.string.prompt_suggestion_55),
        stringResource(R.string.prompt_suggestion_56),
        stringResource(R.string.prompt_suggestion_57),
        stringResource(R.string.prompt_suggestion_58),
        stringResource(R.string.prompt_suggestion_59),
        stringResource(R.string.prompt_suggestion_60),
        stringResource(R.string.prompt_suggestion_61),
        stringResource(R.string.prompt_suggestion_62),
        stringResource(R.string.prompt_suggestion_63),
        stringResource(R.string.prompt_suggestion_64),
        stringResource(R.string.prompt_suggestion_65),
        stringResource(R.string.prompt_suggestion_66),
        stringResource(R.string.prompt_suggestion_67),
        stringResource(R.string.prompt_suggestion_68),
        stringResource(R.string.prompt_suggestion_69),
        stringResource(R.string.prompt_suggestion_70),
        stringResource(R.string.prompt_suggestion_71),
        stringResource(R.string.prompt_suggestion_72),
        stringResource(R.string.prompt_suggestion_73),
        stringResource(R.string.prompt_suggestion_74),
        stringResource(R.string.prompt_suggestion_75),
        stringResource(R.string.prompt_suggestion_76),
        stringResource(R.string.prompt_suggestion_77),
        stringResource(R.string.prompt_suggestion_78),
        stringResource(R.string.prompt_suggestion_79),
        stringResource(R.string.prompt_suggestion_80),
        stringResource(R.string.prompt_suggestion_81),
        stringResource(R.string.prompt_suggestion_82),
        stringResource(R.string.prompt_suggestion_83),
        stringResource(R.string.prompt_suggestion_84),
        stringResource(R.string.prompt_suggestion_85),
        stringResource(R.string.prompt_suggestion_86),
        stringResource(R.string.prompt_suggestion_87),
        stringResource(R.string.prompt_suggestion_88),
        stringResource(R.string.prompt_suggestion_89),
        stringResource(R.string.prompt_suggestion_90),
        stringResource(R.string.prompt_suggestion_91),
        stringResource(R.string.prompt_suggestion_92),
        stringResource(R.string.prompt_suggestion_93),
        stringResource(R.string.prompt_suggestion_94),
        stringResource(R.string.prompt_suggestion_95),
        stringResource(R.string.prompt_suggestion_96),
        stringResource(R.string.prompt_suggestion_97),
        stringResource(R.string.prompt_suggestion_98),
        stringResource(R.string.prompt_suggestion_99),
        stringResource(R.string.prompt_suggestion_100),
    )
    val suggestions = remember(LocalConfiguration.current.locales[0]) { allSuggestions.shuffled().take(4) }

    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Book icon — mirrors the web header's <Book> icon
        Icon(
            imageVector = Icons.AutoMirrored.Filled.MenuBook,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.5f),
            modifier = Modifier
                .size(64.dp)
                .padding(bottom = 8.dp),
        )
        Text(
            text = stringResource(R.string.welcome_title),
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = stringResource(R.string.welcome_subtitle),
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(32.dp))
        // 2×2 grid of tappable prompt suggestions
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            suggestions.chunked(2).forEach { rowItems ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    rowItems.forEach { prompt ->
                        PromptSuggestionCard(
                            text = prompt,
                            onClick = { onPromptSelected(prompt) },
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PromptSuggestionCard(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    OutlinedCard(
        onClick = onClick,
        modifier = modifier,
        colors = CardDefaults.outlinedCardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
        border = androidx.compose.foundation.BorderStroke(
            width = 1.dp,
            color = MaterialTheme.colorScheme.primary.copy(alpha = 0.3f),
        ),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(12.dp),
        )
    }
}

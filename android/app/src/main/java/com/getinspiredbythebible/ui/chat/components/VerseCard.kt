package com.getinspiredbythebible.ui.chat.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.getinspiredbythebible.data.model.VerseResult
import com.getinspiredbythebible.ui.theme.GetInspiredByTheBibleTheme

/**
 * A card that displays a Bible verse reference (e.g. "Philippians 4:6") and its text.
 * Shown below AI assistant messages.
 */
@Composable
fun VerseCard(
    verse: VerseResult,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            // Reference label
            Text(
                text = "${verse.book} ${verse.chapter}:${verse.verse}",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(4.dp))
            // Verse text in italic serif style
            Text(
                text = "\"${verse.text}\"",
                style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun VerseCardPreview() {
    GetInspiredByTheBibleTheme {
        VerseCard(
            verse = VerseResult(
                book = "Philippians",
                chapter = 4,
                verse = 6,
                text = "Be careful for nothing; but in every thing by prayer and supplication " +
                    "with thanksgiving let your requests be made known unto God.",
                similarity = 0.87,
            ),
            modifier = Modifier.padding(16.dp),
        )
    }
}

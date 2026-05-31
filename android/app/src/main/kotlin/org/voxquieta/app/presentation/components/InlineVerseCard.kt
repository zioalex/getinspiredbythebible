package org.voxquieta.app.presentation.components

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState

// Amber scripture palette — mirrors the inline quote highlight in ChatMessageItem and the
// web's amber verse cards (bg-amber-50 / amber-600 bar / amber-900 text).
private val InlineVerseBg = Color(0xFFFFFBEB)
private val InlineVerseAccent = Color(0xFFD97706)
private val InlineVerseText = Color(0xFF78350F)

/**
 * Inline scripture card shown directly under an assistant answer for each cited verse.
 *
 * Unlike [VerseChip] (reference + translation only), this shows the actual [Verse.text] so
 * the verse is readable without opening the top-bar Verses panel — matching the web. Tapping
 * the card opens the same [VerseDetailBottomSheet] (full chapter) that [VerseChip] uses.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InlineVerseCard(
    verse: Verse,
    preferredTranslation: String?,
    chapterState: ChapterSheetState,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismissSheet: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var showSheet by remember { mutableStateOf(false) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)

    Surface(
        modifier = modifier
            .border(
                width = 1.dp,
                color = InlineVerseAccent.copy(alpha = 0.4f),
                shape = RoundedCornerShape(8.dp),
            )
            .clickable {
                // Reset chapter state so VerseDetailBottomSheet always gets a fresh load.
                onDismissSheet()
                showSheet = true
            },
        shape = RoundedCornerShape(8.dp),
        color = InlineVerseBg,
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            Row {
                Text(
                    text = verse.reference,
                    style = MaterialTheme.typography.labelMedium,
                    color = InlineVerseAccent,
                )
                Spacer(Modifier.weight(1f))
                Text(
                    text = verse.translation.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = InlineVerseAccent.copy(alpha = 0.7f),
                )
            }
            if (verse.text.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    text = verse.text,
                    style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                    color = InlineVerseText,
                )
            }
        }
    }

    if (showSheet) {
        VerseDetailBottomSheet(
            verse = verse,
            preferredTranslation = preferredTranslation,
            chapterState = chapterState,
            onLoadChapter = onLoadChapter,
            sheetState = sheetState,
            onDismiss = {
                showSheet = false
                onDismissSheet()
            },
        )
    }
}

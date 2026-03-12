package com.bibleinspiration.presentation.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SheetState
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.bibleinspiration.R
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.presentation.viewmodels.ChapterSheetState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VerseDetailBottomSheet(
    verse: Verse,
    preferredTranslation: String?,
    chapterState: ChapterSheetState,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismiss: () -> Unit,
    sheetState: SheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
) {
    // Scroll chapter list to the target verse once it loads.
    val listState = rememberLazyListState()
    LaunchedEffect(chapterState) {
        if (chapterState is ChapterSheetState.Success) {
            val targetIndex = chapterState.response.verses
                .indexOfFirst { it.verseNumber == verse.verse }
            if (targetIndex >= 0) {
                listState.animateScrollToItem(targetIndex)
            }
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        // Use fillMaxHeight(0.65f) so the Column has a bounded height, which lets
        // the LazyColumn inside use weight(1f) without triggering a Compose
        // measurement crash ("Nesting scrollable in same direction layouts").
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.65f)
                .padding(horizontal = 16.dp)
                .navigationBarsPadding()
                .padding(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ── Header ──────────────────────────────────────────────────────────
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = verse.reference,
                    style = MaterialTheme.typography.headlineSmall,
                )
                val displayTranslation = preferredTranslation ?: verse.translation
                SuggestionChip(
                    onClick = {},
                    label = {
                        Text(
                            text = displayTranslation.uppercase(),
                            style = MaterialTheme.typography.labelSmall,
                        )
                    },
                    colors = SuggestionChipDefaults.suggestionChipColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    ),
                )
            }

            // ── Highlighted verse text ───────────────────────────────────────
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.6f),
                        shape = RoundedCornerShape(8.dp),
                    )
                    .padding(12.dp),
            ) {
                Text(
                    text = "\"${verse.text}\"",
                    style = MaterialTheme.typography.bodyLarge.copy(fontStyle = FontStyle.Italic),
                    color = MaterialTheme.colorScheme.onTertiaryContainer,
                )
            }

            // ── Read full chapter button ─────────────────────────────────────
            OutlinedButton(
                onClick = { onLoadChapter(verse.book, verse.chapter, preferredTranslation ?: verse.translation) },
                modifier = Modifier.align(Alignment.CenterHorizontally),
                enabled = chapterState !is ChapterSheetState.Loading,
            ) {
                Text(text = stringResource(R.string.read_full_chapter))
            }

            // ── Chapter content ──────────────────────────────────────────────
            when (chapterState) {
                is ChapterSheetState.Loading -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(120.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(32.dp))
                    }
                }

                is ChapterSheetState.Error -> {
                    Text(
                        text = chapterState.message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(vertical = 8.dp),
                    )
                }

                is ChapterSheetState.Success -> {
                    val response = chapterState.response
                    val headerText = "${response.book} ${response.chapter}"
                    Text(
                        text = headerText,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Spacer(Modifier.height(4.dp))
                    LazyColumn(
                        state = listState,
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        items(response.verses) { chapterVerse ->
                            val isTarget = chapterVerse.verseNumber == verse.verse
                            val annotated = buildAnnotatedString {
                                withStyle(
                                    SpanStyle(
                                        fontWeight = if (isTarget) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isTarget) {
                                            MaterialTheme.colorScheme.primary
                                        } else {
                                            MaterialTheme.colorScheme.onSurface
                                        },
                                    ),
                                ) {
                                    append("${chapterVerse.verseNumber}  ")
                                }
                                withStyle(
                                    SpanStyle(
                                        fontWeight = if (isTarget) FontWeight.SemiBold else FontWeight.Normal,
                                        color = if (isTarget) {
                                            MaterialTheme.colorScheme.onSurface
                                        } else {
                                            MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f)
                                        },
                                    ),
                                ) {
                                    append(chapterVerse.text)
                                }
                            }
                            Box(
                                modifier = if (isTarget) {
                                    Modifier
                                        .fillMaxWidth()
                                        .background(
                                            color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.4f),
                                            shape = RoundedCornerShape(4.dp),
                                        )
                                        .padding(horizontal = 6.dp, vertical = 4.dp)
                                } else {
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                },
                            ) {
                                Text(
                                    text = annotated,
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                            }
                        }
                    }
                }

                is ChapterSheetState.Idle -> {
                    // Nothing to show yet — user hasn't tapped "Read full chapter"
                }
            }
        }
    }
}

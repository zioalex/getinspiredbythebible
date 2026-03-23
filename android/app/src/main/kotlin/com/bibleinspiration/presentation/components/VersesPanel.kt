package com.bibleinspiration.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
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
import androidx.compose.ui.unit.dp
import com.bibleinspiration.R
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.presentation.viewmodels.ChapterSheetState

/**
 * Regex used to find verse references that are explicitly cited in a message body.
 * Mirrors the pattern in ChatMessageItem.kt (colon always required here since
 * citation matching needs book+chapter+verse).
 *
 * Uses \p{Lu}/\p{Lo} for the first character of book-name words so that only
 * uppercase (Latin/Cyrillic) or caseless (CJK) letters start a word. This avoids
 * greedily capturing preceding lowercase prose. No (?U) flag — \p{Lu}/\p{Lo}/\p{L}
 * stay Unicode while \w/\b stay ASCII.
 *
 * We use (?!\d) instead of \b to terminate digit sequences so that CJK characters
 * immediately after a verse number (e.g. "3:16是") don't cause boundary failures.
 *
 * Two alternatives:
 *   Alt 1 — numbered prefix ("1 ", "2 ", "3 ", "1. ", "2. ") + book + chapter:verse
 *   Alt 2 — book (no prefix) + chapter:verse
 */
private val CITED_BOOK_NAME =
    "[\\p{Lu}\\p{Lo}][\\p{L}\\d]*" +
        "(?:\\s+(?:of|de|des|der|da|del|van|af)\\s+[\\p{Lu}\\p{Lo}][\\p{L}\\d]*)*"

private val CITED_VERSE_REF_REGEX = Regex(
    "([1-3][\\s.][\\s]?$CITED_BOOK_NAME(?:\\s+[\\p{Lu}\\p{Lo}][\\p{L}\\d]+)*)\\s+(\\d+):(\\d+(?:-\\d+)?)(?!\\d)" +
        "|" +
        "($CITED_BOOK_NAME)\\s+(\\d+):(\\d+(?:-\\d+)?)(?!\\d)",
)

/**
 * Returns the subset of [allVerses] whose human-readable reference (e.g. "John 3:16")
 * appears explicitly in the text of at least one [messages] entry.
 */
internal fun referencedVerses(allVerses: List<Verse>, messages: List<Message>): List<Verse> {
    val combinedText = messages
        .filter { it.role == Message.Role.ASSISTANT }
        .joinToString(" ") { it.content }
    val citedRefs = CITED_VERSE_REF_REGEX.findAll(combinedText)
        .map {
            // Alt 1 (numbered prefix) fills groups 1-3; Alt 2 fills groups 4-6.
            if (it.groupValues[1].isNotEmpty()) {
                "${it.groupValues[1]} ${it.groupValues[2]}:${it.groupValues[3]}"
            } else {
                "${it.groupValues[4]} ${it.groupValues[5]}:${it.groupValues[6]}"
            }
        }
        .toHashSet()
    return allVerses.filter { verse ->
        // Match if the base reference (book chapter:verse) appears — ignore range suffix.
        val baseRef = "${verse.book} ${verse.chapter}:${verse.verse}"
        citedRefs.any { it.startsWith(baseRef) }
    }
}

/**
 * A `ModalBottomSheet` displaying all verses referenced in the current conversation.
 *
 * Provides a "Referenced" / "All Related" segment control:
 * - **Referenced**: only verses explicitly cited in assistant message text.
 * - **All Related**: every verse returned by the backend across all messages.
 *
 * @param allVerses       All unique verses across finished assistant messages.
 * @param messages        Full message list (used to determine which verses are referenced).
 * @param chapterSheetState Current state of the chapter-detail sheet.
 * @param preferredTranslation The user's preferred Bible translation code, or null.
 * @param onLoadChapter   Callback to open the chapter-detail sheet.
 * @param onDismissSheet  Callback to clear the chapter-detail sheet state.
 * @param onDismiss       Callback to close this panel.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VersesPanel(
    allVerses: List<Verse>,
    messages: List<Message>,
    chapterSheetState: ChapterSheetState,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismissSheet: () -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)
    var showReferenced by rememberSaveable { mutableStateOf(true) }

    val displayedVerses = if (showReferenced) {
        referencedVerses(allVerses, messages)
    } else {
        allVerses
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp),
        ) {
            // Title row
            Text(
                text = stringResource(R.string.verses_panel_title),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 12.dp),
            )

            // Segment control — "Referenced" | "All Related (N)"
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                FilterChip(
                    selected = showReferenced,
                    onClick = { showReferenced = true },
                    label = { Text(stringResource(R.string.verses_filter_referenced)) },
                )
                FilterChip(
                    selected = !showReferenced,
                    onClick = { showReferenced = false },
                    label = {
                        Text(
                            stringResource(
                                R.string.verses_filter_all_related,
                                allVerses.size,
                            ),
                        )
                    },
                )
            }

            Spacer(modifier = Modifier.height(8.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(4.dp))

            if (displayedVerses.isEmpty()) {
                Text(
                    text = stringResource(R.string.verses_panel_empty),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 16.dp),
                )
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(displayedVerses, key = { "${it.book}${it.chapter}:${it.verse}" }) { verse ->
                        VerseChip(
                            verse = verse,
                            preferredTranslation = preferredTranslation,
                            chapterState = chapterSheetState,
                            onLoadChapter = onLoadChapter,
                            onDismissSheet = onDismissSheet,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
    }
}

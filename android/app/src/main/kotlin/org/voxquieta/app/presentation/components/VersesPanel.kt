package org.voxquieta.app.presentation.components

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
import org.voxquieta.app.R
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.utils.normalizeBookName
import org.voxquieta.app.utils.normalizeTraditionalToSimplified

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
// The connector-repeat group is bounded to {0,3} (BITB-114, mirroring the web fix in
// BITB-108/versePatterns.ts): unbounded `*` here let adversarial input (long chains of
// connector words) drive superlinear-time regex backtracking. No real supported book name
// needs more than one connector (e.g. "Song of Solomon" — see LocalizedBookToEnglish.kt);
// {0,3} keeps 3x headroom while eliminating the unbounded blowup.
private val CITED_BOOK_NAME =
    "[\\p{Lu}\\p{Lo}][\\p{L}\\d]*" +
        "(?:\\s+(?:of|de|des|der|da|del|dei|dos|van|af)\\s+[\\p{Lu}\\p{Lo}][\\p{L}\\d]*){0,3}"

private val CITED_VERSE_REF_REGEX = Regex(
    "([1-3][\\s.][\\s]?$CITED_BOOK_NAME(?:\\s+[\\p{Lu}\\p{Lo}][\\p{L}\\d]+)*)\\s+(\\d+):(\\d+(?:-\\d+)?)(?!\\d)" +
        "|" +
        "($CITED_BOOK_NAME)\\s+(\\d+):(\\d+(?:-\\d+)?)(?!\\d)",
)

/**
 * Returns the subset of [allVerses] whose human-readable reference (e.g. "John 3:16")
 * appears explicitly in the text of at least one [messages] entry.
 *
 * Prefers server-provided [Message.versesCited] (dual-source: LLM structured output + backend
 * regex) when available, falling back to client-side regex extraction for older messages.
 *
 * @param localizedToEnglish Optional runtime map of localized book names to English names (from
 *   the API). The bundled map remains available when this map is empty or misses a name.
 */
internal fun referencedVerses(
    allVerses: List<Verse>,
    messages: List<Message>,
    localizedToEnglish: Map<String, String> = emptyMap(),
): List<Verse> {
    val assistantMessages = messages.filter { it.role == Message.Role.ASSISTANT }

    // Prefer server-provided versesCited when any assistant message has them.
    val serverCited = assistantMessages.flatMap { it.versesCited }
    if (serverCited.isNotEmpty()) {
        // Server citations are in English canonical form (e.g. "John 3:16").
        // Normalize to lowercase for case-insensitive matching.
        val citedLower = serverCited.map { it.lowercase() }.toHashSet()
        return allVerses.filter { verse ->
            val baseRef = "${verse.book} ${verse.chapter}:${verse.verse}".lowercase()
            citedLower.any { it.startsWith(baseRef) }
        }
    }

    // Fallback: client-side regex extraction for older messages without versesCited.
    val combinedText = assistantMessages.joinToString(" ") { it.content }
    val citedRefs = CITED_VERSE_REF_REGEX.findAll(combinedText)
        .map {
            // Alt 1 (numbered prefix) fills groups 1-3; Alt 2 fills groups 4-6.
            val rawBook: String
            val chapter: String
            val verse: String
            if (it.groupValues[1].isNotEmpty()) {
                rawBook = it.groupValues[1]
                chapter = it.groupValues[2]
                verse = it.groupValues[3]
            } else {
                rawBook = it.groupValues[4]
                chapter = it.groupValues[5]
                verse = it.groupValues[6]
            }
            // Uses both the runtime API map and its bundled offline fallback. Traditional Chinese
            // is normalized to Simplified before the fallback lookup.
            val book = normalizeBookName(
                normalizeTraditionalToSimplified(rawBook),
                localizedToEnglish,
            )
            "$book $chapter:$verse".lowercase()
        }
        .toHashSet()
    return allVerses.filter { verse ->
        // Match if the base reference (book chapter:verse) appears — ignore range suffix.
        // Check both the English book name and the localized book name so that non-English
        // conversations (e.g. Italian "Salmi 60:1") correctly surface in the Referenced tab.
        val baseRef = "${verse.book} ${verse.chapter}:${verse.verse}".lowercase()
        val localizedBaseRef = verse.localizedBook?.let {
            "${it} ${verse.chapter}:${verse.verse}".lowercase()
        }
        citedRefs.any { cited ->
            cited.startsWith(baseRef) ||
                (localizedBaseRef != null && cited.startsWith(localizedBaseRef))
        }
    }
}

/**
 * Default value for the "Referenced" / "All Related" segment control.
 * Extracted as a constant so JVM unit tests and Compose UI tests can assert
 * the expected default without rendering the full composable (BITB-034).
 */
internal const val DEFAULT_SHOW_REFERENCED: Boolean = true

/**
 * The scrollable body of the verses panel — title, segment control, verse list.
 * Extracted from [VersesPanel] so Compose UI tests can mount this directly
 * without needing a [ModalBottomSheet] (which has Robolectric rendering caveats).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun VersesPanelContent(
    allVerses: List<Verse>,
    messages: List<Message>,
    chapterSheetState: ChapterSheetState,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismissSheet: () -> Unit,
    localizedToEnglish: Map<String, String> = emptyMap(),
) {
    var showReferenced by rememberSaveable { mutableStateOf(DEFAULT_SHOW_REFERENCED) }

    val displayedVerses = if (showReferenced) {
        referencedVerses(allVerses, messages, localizedToEnglish)
    } else {
        allVerses
    }

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

        // Segment control — "Cited" | "All Related (N)"
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

/**
 * A `ModalBottomSheet` displaying all verses referenced in the current conversation.
 *
 * Provides a "Cited" / "All Related" segment control:
 * - **Cited**: only verses explicitly cited in assistant message text.
 * - **All Related**: every verse returned by the backend across all messages.
 *
 * @param allVerses            All unique verses across finished assistant messages.
 * @param messages             Full message list (used to determine which verses are referenced).
 * @param chapterSheetState    Current state of the chapter-detail sheet.
 * @param preferredTranslation The user's preferred Bible translation code, or null.
 * @param localizedToEnglish   Runtime map from localized book names to English names (from the API),
 *                             layered over the bundled fallback map.
 * @param onLoadChapter        Callback to open the chapter-detail sheet.
 * @param onDismissSheet       Callback to clear the chapter-detail sheet state.
 * @param onDismiss            Callback to close this panel.
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
    localizedToEnglish: Map<String, String> = emptyMap(),
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        VersesPanelContent(
            allVerses = allVerses,
            messages = messages,
            chapterSheetState = chapterSheetState,
            preferredTranslation = preferredTranslation,
            onLoadChapter = onLoadChapter,
            onDismissSheet = onDismissSheet,
            localizedToEnglish = localizedToEnglish,
        )
    }
}

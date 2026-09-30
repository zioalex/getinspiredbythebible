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
import org.voxquieta.app.utils.VerseGrammar
import org.voxquieta.app.utils.knownBooks
import org.voxquieta.app.utils.normalizeBookName
import org.voxquieta.app.utils.normalizeTraditionalToSimplified

/**
 * Returns the subset of [allVerses] whose human-readable reference (e.g. "John 3:16")
 * appears explicitly in the text of at least one [messages] entry.
 *
 * Prefers server-provided [Message.versesCited] (dual-source: LLM structured output + backend
 * regex) when available, falling back to client-side regex extraction for older messages.
 *
 * The fallback reuses the shared verse grammar (BITB-164): [verseRefRegex] defaults to
 * [DEFAULT_VERSE_REF_REGEX] (composed from VerseGrammar.kt) and the scan mirrors
 * [injectVerseLinks] -- Traditional->Simplified shadow copy, manual find loop, and a rewind
 * on a match that resolves to none of [allVerses] and whose book is not a known book (so a
 * greedy over-match such as "you of Psalm 56:9" still recovers "Psalm 56:9", while an uncited
 * "1 John 3:16" is not rewound into a false "John 3:16"). A cited reference matches a verse
 * only on exact chapter, exact verse number and exact (case-insensitive) book -- so
 * "John 3:16" no longer surfaces John 3:1. Hits are gated on [allVerses], not on the allowlist.
 *
 * @param verseRefRegex Regex used for the fallback scan; pass ChatScreen's dynamically built
 *   regex once API book-name data has loaded.
 * @param localizedToEnglish Optional runtime map of localized book names to English names (from
 *   the API). The bundled map remains available when this map is empty or misses a name.
 */
internal fun referencedVerses(
    allVerses: List<Verse>,
    messages: List<Message>,
    localizedToEnglish: Map<String, String> = emptyMap(),
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
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
    if (allVerses.isEmpty()) return emptyList()
    val combinedText = assistantMessages.joinToString(" ") { it.content }
    // Length-preserving Traditional->Simplified shadow copy (mirrors injectVerseLinks), so
    // group ranges found in `search` are valid offsets into `combinedText` as well.
    val search = normalizeTraditionalToSimplified(combinedText)
    // Book allowlist, used only to decide whether to rewind on a match that cites none of
    // [allVerses] (see below); hits themselves are still gated on [allVerses].
    val known = knownBooks(localizedToEnglish)
    val matched = HashSet<Verse>()
    var start = 0
    while (start <= search.length) {
        val match = verseRefRegex.find(search, start) ?: break
        val g = match.groupValues
        // Alt 1 (numbered prefix) fills groups 1-3; Alt 2 fills groups 4-6.
        val bookGroup = if (g[1].isNotEmpty()) 1 else 4
        val shadowBook = g[bookGroup]
        val chapter = g[bookGroup + 1]
        val verseGroup = g[bookGroup + 2]
        val bookRange = match.groups[bookGroup]!!.range
        val origBook = combinedText.substring(bookRange.first, bookRange.last + 1)

        // A citation needs book + chapter + verse (chapter-only matches are not citations).
        val chapterNum = chapter.toIntOrNull()
        val verseNum = if (verseGroup.isEmpty()) {
            null
        } else {
            verseGroup.split(*VerseGrammar.RANGE_SEPARATORS.toCharArray()).first().toIntOrNull()
        }
        val hits = if (chapterNum == null || verseNum == null) {
            emptyList()
        } else {
            val bookKeys = setOf(
                origBook.trim().lowercase(),
                shadowBook.trim().lowercase(),
                normalizeBookName(shadowBook.trim(), localizedToEnglish).lowercase(),
            )
            allVerses.filter { v ->
                v.chapter == chapterNum &&
                    v.verse == verseNum &&
                    (
                        v.book.lowercase() in bookKeys ||
                            v.localizedBook?.lowercase()?.let { it in bookKeys } == true
                        )
            }
        }
        if (hits.isEmpty()) {
            // Rewind one char past the start only when the matched book is NOT a real book
            // (a greedy over-match such as "you of Psalm"), exactly like injectVerseLinks, so a
            // reference hidden inside it is still found. A real-but-uncited book is skipped
            // whole: rewinding "1 John 3:16" would otherwise re-match its "John 3:16" suffix
            // and surface the wrong verse. `start` strictly increases: no infinite loop.
            start = if (shadowBook.trim().lowercase() in known) {
                match.range.last + 1
            } else {
                match.range.first + 1
            }
        } else {
            matched.addAll(hits)
            start = match.range.last + 1
        }
    }
    return allVerses.filter { it in matched }
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
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
) {
    var showReferenced by rememberSaveable { mutableStateOf(DEFAULT_SHOW_REFERENCED) }

    val displayedVerses = if (showReferenced) {
        referencedVerses(allVerses, messages, localizedToEnglish, verseRefRegex)
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
 * @param verseRefRegex        Regex for the Cited-tab fallback scan (defaults to the shared
 *                             [DEFAULT_VERSE_REF_REGEX]).
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
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
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
            verseRefRegex = verseRefRegex,
        )
    }
}

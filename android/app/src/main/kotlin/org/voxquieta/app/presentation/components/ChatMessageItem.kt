package org.voxquieta.app.presentation.components

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Typeface
import android.text.Spannable
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.widget.Toast
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.LocalTextSelectionColors
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.text.selection.TextSelectionColors
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.app.ShareCompat
import org.voxquieta.app.R
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.utils.normalizeBookName
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import dev.jeziellago.compose.markdowntext.MarkdownText
import java.net.URLDecoder
import java.net.URLEncoder

/**
 * Minimal data class representing a verse reference parsed from a tapped markdown link.
 * We only have book/chapter/verseNumber from the URL; text will be shown once the chapter loads.
 */
internal data class PendingVerseLink(
    val book: String,
    val chapter: Int,
    val verseNumber: Int,
    val translation: String?,
    val localizedBook: String? = null,
)

/**
 * Regex matching standalone Bible verse references in message text.
 * Captures: group 1 = book name, group 2 = chapter number, group 3 = verse (may include range).
 *
 * `(?U)` enables Unicode mode so \p{L} matches any Unicode letter, supporting
 * non-English book names in addition to English.
 *
 * Examples matched:
 *   - English:       "John 3:16", "1 Corinthians 13:4", "Song of Solomon 2:1"
 *   - German:        "Johannes 3:16", "Römer 8:28", "1. Mose 1:1", "2. Könige 5:14"
 *   - Italian:       "Giovanni 3:16", "Salmi 23:1", "Romani 8:28"
 *   - Spanish:       "Juan 3:16", "Génesis 1:1", "Romanos 8:28", "Apocalipsis 21:4"
 *   - French:        "Jean 3:16", "Genèse 1:1", "Romains 8:28", "Psaumes 23:1"
 *   - Portuguese:     "João 3:16", "Gênesis 1:1", "Salmos 23:1", "Apocalipse 21:4"
 *   - Russian:       "Иоанн 3:16", "Псалтирь 23:1", "Плач Иеремии 3:3",
 *                   "1 Коринфянам 13:4", "Откровение 21:4"
 *   - Chinese:        "约翰福音 3:16", "诗篇 23:1", "创世记 1:1", "耶利米哀歌 3:3"
 *   - Korean:         "요한복음 3:16", "시편 23:1", "창세기 1:1", "예레미야 애가 3:3"
 *
 * We exclude references already inside a markdown link by checking the character before the
 * match in the replace lambda (if preceded by '[', the ref is already a link display text).
 */
// Book-name sub-pattern (multi-word, with connector words like "of", "de", "van", …).
// First character is any Unicode letter \p{L} (upper OR lower case) so that lowercase-emitted
// references ("as john 3:16 says") are detected too — the previous \p{Lu}\p{Lo} (uppercase /
// caseless only) silently dropped them. False positives are no longer prevented by casing but
// by the isKnownBook() allowlist gate + rewind loop in injectVerseLinks (mirrors the web).
// Continuation chars include \p{M} (combining marks) for Hindi/Arabic diacritics.
// Connector words include Western (of, de, des, …), Hindi (के), and Arabic article (ال).
private val BOOK_NAME =
    "[\\p{L}][\\p{L}\\p{M}\\d]*" +
        "(?:\\s+(?:of|de|des|der|da|del|dei|dos|van|af|के|ال)" +
        "\\s+[\\p{L}][\\p{L}\\p{M}\\d]*)*"

// Two alternatives joined by '|' so that numbered-prefix books require chapter:verse
// while un-numbered books also support chapter-only references (e.g. "Psalm 23").
// We do NOT use (?U) — \p{Lu}/\p{Lo}/\p{L} stay Unicode, but \w/\b stay ASCII.
// We use (?!\d) instead of \b to terminate digit sequences for CJK compatibility:
// \b requires a \w↔\W transition, but in Java without (?U) the behaviour at CJK
// boundaries is unreliable across JVM versions. (?!\d) is simpler and always works.

// Conditional whitespace sub-pattern: after a CJK (Han) or Hangul (Korean) character,
// or a closing bracket (》」』), the space between book name and chapter number is
// optional (\s*); otherwise at least one space is required (\s+).
// This enables matching "约翰福音10:28", "요한복음3:16", "《约翰福音》3:16",
// "「요한복음」3:16" while still requiring "John 3:16".
private const val COND_WS = "(?:(?<=[\\p{IsHan}\\p{IsHangul}\\u300B\\u300D\\u300F])\\s*|\\s+)"

/** Fallback regex used before book-name data loads from the API. */
internal val DEFAULT_VERSE_REF_REGEX = Regex(
    // Alt 1 — numbered prefix ("1 ", "2 ", "3 ", "1. ", "2. ", "3. "), colon REQUIRED.
    // Also handles Russian Synodal dash style ("1-я ", "1-е ", "2-я ") where a 1–2 letter
    // ordinal suffix follows the dash (lowercase Cyrillic, so \p{L}\p{M} not \p{Lu}\p{Lo}).
    // Allows multiple trailing words (e.g. Arabic "1 أخبار الأيام" = 1 Chronicles = 3 words).
    "([1-3](?:[\\s.][\\s]?|-[\\p{L}\\p{M}]{1,2}\\s+)$BOOK_NAME(?:\\s+[\\p{L}][\\p{L}\\p{M}\\d]+)*)\\s+(\\d+):(\\d+(?:-\\d+)?)(?!\\d)" +
        "|" +
        // Alt 2 — no prefix. Colon branch or chapter-only branch (with guard).
        // Chapter-only uses (?!\s+[\p{Lu}\p{Lo}]) so that "See 1 Corinthians..." does NOT
        // match "See" as book + "1" as chapter; the digit must not be followed by a word
        // that looks like a book name (preventing false numbered-book splits).
        // NOTE: this guard intentionally stays UPPERCASE (\p{Lu}\p{Lo}), unlike the book-name
        // pattern which was relaxed to any letter. It disambiguates a numbered book (next word
        // is a capitalized "Corinthians") from ordinary prose after a chapter-only reference
        // ("Psalm 23 is comforting"); relaxing it to \p{L} would break chapter-only refs
        // followed by a lowercase word.
        // Uses COND_WS so CJK/Hangul book names can abut the chapter number without a space.
        // [\u300B\u300D\u300F]? optionally consumes a closing bracket (》」』) after the
        // book name (e.g. 《约翰福音》3:16 or 「요한복음」3:16) so it does not block the match.
        "($BOOK_NAME)[\\u300B\\u300D\\u300F]?$COND_WS(\\d+)(?::(\\d+(?:-\\d+)?)(?!\\d)|(?!\\d)(?!\\s+[\\p{Lu}\\p{Lo}]))"
)

/**
 * Builds a [Regex] for matching verse references that includes explicit alternations for
 * [multiWordNames] (server-provided multi-word book names, sorted longest-first) and
 * [cjkBookNames] (CJK book names that may appear without a space before the chapter number).
 *
 * Each name is regex-escaped and spaces are replaced with `\s+` for flexible whitespace
 * matching.  The multi-word names are embedded into the book-name sub-pattern so that the
 * overall capture group structure remains identical to [DEFAULT_VERSE_REF_REGEX]:
 *   - Groups 1–3: numbered-prefix match
 *   - Groups 4–6: un-prefixed match (with or without verse number)
 *
 * When [cjkBookNames] are provided, the generic [BOOK_NAME] pattern is modified to exclude
 * Han characters as a first character (`(?!\p{IsHan})`) so that only the explicit CJK
 * alternation matches Chinese book names — preventing greedy over-matching in embedded text.
 *
 * Falls back to [DEFAULT_VERSE_REF_REGEX] when both lists are empty.
 */
internal fun buildVerseRefRegex(
    multiWordNames: List<String>,
    cjkBookNames: List<String> = emptyList(),
): Regex {
    if (multiWordNames.isEmpty() && cjkBookNames.isEmpty()) return DEFAULT_VERSE_REF_REGEX

    // Escape regex special chars in each name, then replace spaces with \s+ for flexible
    // whitespace matching. We cannot use Regex.escape() here because it wraps the whole
    // string in \Q...\E, which prevents per-character manipulation. Instead we escape
    // only the characters that are special in Java regex and replace spaces with \s+.
    val regexSpecialChars = Regex("""[.+*?^${'$'}{}()\[\]|\\]""")
    val escapedMultiWord = if (multiWordNames.isNotEmpty()) {
        multiWordNames.joinToString("|") { name ->
            regexSpecialChars.replace(name) { "\\${it.value}" }
                .replace(" ", "\\s+")
        }
    } else null

    // CJK book names: sorted longest-first, escaped, joined as alternation.
    val escapedCjk = if (cjkBookNames.isNotEmpty()) {
        cjkBookNames.sortedByDescending { it.length }.joinToString("|") { name ->
            regexSpecialChars.replace(name) { "\\${it.value}" }
        }
    } else null

    // When CJK alternation is present, prevent the generic BOOK_NAME from matching Han
    // characters as a first character — only the explicit CJK alternation handles those.
    // When CJK/Hangul alternation is present, prevent the generic BOOK_NAME from matching
    // Han or Hangul characters as a first character — only the explicit alternation handles those.
    val genericBookName = if (escapedCjk != null) {
        "(?!\\p{IsHan}|\\p{IsHangul})$BOOK_NAME"
    } else BOOK_NAME

    // Build a dynamic book-name pattern that first tries server names (longest-first),
    // then CJK names, then falls back to the generic Unicode pattern.
    val dynamicBookName = buildString {
        append("(?:")
        var needsPipe = false
        if (escapedMultiWord != null) { append(escapedMultiWord); needsPipe = true }
        if (escapedCjk != null) { if (needsPipe) append("|"); append(escapedCjk); needsPipe = true }
        if (needsPipe) append("|")
        append(genericBookName)
        append(")")
    }

    return Regex(
        // Alt 1 — numbered prefix, colon REQUIRED (see DEFAULT_VERSE_REF_REGEX comments)
        "([1-3](?:[\\s.][\\s]?|-[\\p{L}\\p{M}]{1,2}\\s+)$dynamicBookName(?:\\s+[\\p{L}][\\p{L}\\p{M}\\d]+)*)\\s+(\\d+):(\\d+(?:-\\d+)?)(?!\\d)" +
            "|" +
            // Alt 2 — no prefix. Uses COND_WS for CJK/Hangul no-space support.
            // [\u300B\u300D\u300F]? optionally consumes closing bracket (》」』) after book name.
            "($dynamicBookName)[\\u300B\\u300D\\u300F]?$COND_WS(\\d+)(?::(\\d+(?:-\\d+)?)(?!\\d)|(?!\\d)(?!\\s+[\\p{Lu}\\p{Lo}]))"
    )
}

private const val VERSE_SCHEME = "verse://"

/**
 * Resolves the book name to use as the `verse://` link **target** so the chapter lookup
 * succeeds even when the LLM labelled the reference in the wrong language.
 *
 * Priority:
 *  1. [normalizeBookName] against the backend `localized_to_english` map — resolves
 *     localized names (e.g. German "Matthäus" → "Matthew", "2 Korinther" → "2 Corinthians").
 *  2. If the map misses (e.g. the Latin/Vulgate "Proverbia", which is in no map) fall back
 *     to the authoritative per-message [verses] list: if exactly one cited verse has this
 *     [chapter]:[verse], use its canonical [Verse.book]. This bypasses the wrong label.
 *  3. Otherwise leave the raw name unchanged (already-English, or genuinely unknown) — the
 *     existing behaviour, so there is no regression.
 *
 * The displayed link text is unaffected; only the link target book is resolved here.
 */
private fun resolveLinkBook(
    rawBook: String,
    chapter: String,
    verse: String,
    verses: List<Verse>,
    localizedToEnglish: Map<String, String>,
): String {
    val normalized = normalizeBookName(rawBook, localizedToEnglish)
    if (normalized != rawBook) return normalized

    val chapterNum = chapter.toIntOrNull()
    val verseNum = verse.toIntOrNull()
    if (chapterNum != null && verseNum != null) {
        val candidates = verses
            .filter { it.chapter == chapterNum && it.verse == verseNum }
            .map { it.book }
            .distinct()
        if (candidates.size == 1) return candidates.first()
    }
    return rawBook
}

/**
 * Rewrites verse references in [markdown] as markdown links using the `verse://` scheme.
 *
 * E.g. "John 3:16" → "[John 3:16](verse://John/3/16)"
 * E.g. "Psalm 23"  → "[Psalm 23](verse://Psalm/23)"   (chapter-only, no verse number)
 *
 * The book name is URL-encoded so that spaces survive the round-trip through the Markwon
 * link renderer.  References already inside a markdown link (e.g. `[John 3:16](verse://…)`)
 * are left unchanged by checking that the character before the match is not `[`.
 *
 * The **displayed** text keeps the book name as the LLM wrote it (e.g. German "Proverbia
 * 17:17"), but the link **target** is resolved via [resolveLinkBook] so the chapter lookup
 * works even when the label is wrong-language.
 *
 * @param verseRefRegex The regex to use for matching verse references. Defaults to
 *   [DEFAULT_VERSE_REF_REGEX]; pass a dynamically built regex from [buildVerseRefRegex]
 *   once API book-name data has loaded.
 * @param verses The verses the backend cited for this message; used to resolve the link
 *   target book by chapter:verse when the written name isn't in the book-name map.
 * @param localizedToEnglish The backend `localized_to_english` book-name map.
 */
internal fun injectVerseLinks(
    markdown: String,
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
    verses: List<Verse> = emptyList(),
    localizedToEnglish: Map<String, String> = emptyMap(),
): String {
    // Allowlist computed once and reused for every candidate (see knownBooks docs).
    val known = knownBooks(localizedToEnglish)

    // Manual scan (instead of Regex.replace) so we can rewind on a rejected match. The verse
    // regex deliberately accepts any "Word digit:digit" shape and is case-agnostic at the book
    // position, so a greedy alternative can swallow the words *before* a real reference
    // ("you of Psalm 56:9" -> book "you of Psalm"). Such a match fails the isKnownBook gate; we
    // then rewind one character past its start so the embedded reference ("Psalm 56:9") still
    // gets linked. This mirrors the web highlightText()/extractVerseReferences() rewind.
    val out = StringBuilder(markdown.length)
    var appendedUpTo = 0 // markdown copied into `out` up to here (exclusive)
    var searchStart = 0
    while (true) {
        val result = verseRefRegex.find(markdown, searchStart) ?: break
        val g = result.groupValues

        // Alt 1 (numbered prefix) populates groups 1-3; Alt 2 populates groups 4-6.
        val book: String
        val chapter: String
        val verse: String
        if (g[1].isNotEmpty()) {
            book = g[1]; chapter = g[2]; verse = g[3]
        } else {
            book = g[4]; chapter = g[5]; verse = g[6]
        }

        // Reject anything that is not a real Bible book, then rewind so a valid reference
        // hidden inside a greedy over-match is still recovered. `searchStart` strictly
        // increases, so this cannot loop forever.
        if (book.trim().lowercase() !in known) {
            searchStart = result.range.first + 1
            continue
        }

        // Copy the untouched text between the previous output point and this match.
        out.append(markdown, appendedUpTo, result.range.first)

        // If the match is immediately preceded by '[', it is already the display text of a
        // markdown link -- leave it unchanged to avoid double-wrapping.
        val before = if (result.range.first > 0) markdown[result.range.first - 1] else ' '
        if (before == '[') {
            out.append(result.value)
        } else {
            val linkBook = resolveLinkBook(book, chapter, verse, verses, localizedToEnglish)
            val encodedBook = URLEncoder.encode(linkBook, "UTF-8")
            val display = if (verse.isNotEmpty()) "$book $chapter:$verse" else "$book $chapter"
            val urlVerse = if (verse.isNotEmpty()) "/$verse" else ""
            // Carry the localized book token in the URL so parseVerseLink can set it on
            // PendingVerseLink without discarding the name the LLM used.
            val localizedParam = if (book != linkBook) {
                "?localizedBook=${URLEncoder.encode(book, "UTF-8")}"
            } else {
                ""
            }
            val link = "[$display]($VERSE_SCHEME$encodedBook/$chapter$urlVerse$localizedParam)"
            // Wrap in bold so verse references are visually prominent (matching the web's
            // font-semibold styling) regardless of whether the LLM already used bold markdown.
            // If the LLM already wrapped the ref in ** (before == '*'), the surrounding **
            // in the original text stays in place and provides the bold -- just linkify.
            out.append(if (before == '*') link else "**$link**")
        }

        appendedUpTo = result.range.last + 1
        searchStart = result.range.last + 1
    }
    out.append(markdown, appendedUpTo, markdown.length)
    return out.toString()
}

// Matches any quoted text with supported quote-mark pairs, minimum 3 content chars.
// Mirrors the web's highlightQuotes() which matches all double-quoted text, extended with
// language-specific quote pairs for curly, guillemet, German, and CJK styles.
// Opening: " straight (U+0022), \u201C left curly, \u201D right curly (German open),
//          \u00AB guillemet, \u201E German low-9, \u300C CJK corner, \u300A double CJK.
// Closing: " straight (U+0022), \u201D right curly, \u201C left curly (German close),
//          \u00BB guillemet, \u300D CJK corner, \u300B double CJK.
internal val QUOTE_HIGHLIGHT_REGEX = Regex(
    "([\u0022\u201C\u201D\u00AB\u201E\u300C\u300A]" +
        "(?:[^\u0022\u201C\u201D\u00BB\u300D\u300B\n]{3,})" +
        "[\u0022\u201D\u201C\u00BB\u300D\u300B])"
)

internal fun injectVerseQuoteHighlights(markdown: String): String = markdown

/**
 * Returns the verses to show as inline cards under [message]: the ones the backend reported
 * this answer actually cited.
 *
 * Prefers the server-provided [Message.versesCited] (English canonical, e.g. "John 3:16"),
 * intersecting it with [Message.verses] (which carry the text). When [Message.versesCited]
 * is empty (older messages, or none reported) it falls back to all [Message.verses] so the
 * text is still shown. Matching mirrors [referencedVerses] in VersesPanel.
 */
internal fun citedVerses(message: Message): List<Verse> {
    if (message.verses.isEmpty()) return emptyList()
    if (message.versesCited.isEmpty()) return message.verses

    val citedLower = message.versesCited.map { it.lowercase() }.toHashSet()
    val filtered = message.verses.filter { verse ->
        val baseRef = "${verse.book} ${verse.chapter}:${verse.verse}".lowercase()
        citedLower.any { it.startsWith(baseRef) }
    }
    // If nothing matched (e.g. citation/verse book-name mismatch) fall back to all verses
    // rather than hiding the text entirely.
    return filtered.ifEmpty { message.verses }
}

/**
 * Parses a `verse://` URL and returns a [PendingVerseLink] if the URL is well-formed,
 * or null otherwise.
 *
 * URL format: `verse://<encoded-book>/<chapter>[/<verse>]`
 * The verse segment is optional; when absent the verse number defaults to 1.
 */
internal fun parseVerseLink(url: String, preferredTranslation: String?): PendingVerseLink? {
    if (!url.startsWith(VERSE_SCHEME)) return null
    val raw = url.removePrefix(VERSE_SCHEME)
    // Strip query string before positional path parsing; parse localizedBook from it.
    val (pathPart, query) = if ('?' in raw) raw.split("?", limit = 2) else listOf(raw, "")
    val localizedBook = query
        .split("&")
        .firstOrNull { it.startsWith("localizedBook=") }
        ?.removePrefix("localizedBook=")
        ?.let { runCatching { URLDecoder.decode(it, "UTF-8") }.getOrNull() }
    val parts = pathPart.split("/")
    if (parts.size < 2) return null
    val book = runCatching { URLDecoder.decode(parts[0], "UTF-8") }.getOrNull() ?: return null
    val chapter = parts[1].toIntOrNull() ?: return null
    // Verse number may be a range like "16-18" — take the first number.
    val verseNumber = parts.getOrNull(2)?.split("-")?.firstOrNull()?.toIntOrNull() ?: 1
    return PendingVerseLink(
        book = book,
        chapter = chapter,
        verseNumber = verseNumber,
        translation = preferredTranslation,
        localizedBook = localizedBook,
    )
}

/**
 * Parses a `verse://` URL and calls [onLoadChapter] if the URL is well-formed.
 *
 * URL format: `verse://<encoded-book>/<chapter>/<verse>`
 */
internal fun handleVerseLink(
    url: String,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
) {
    if (!url.startsWith(VERSE_SCHEME)) return
    val raw = url.removePrefix(VERSE_SCHEME)
    // Strip query string before positional path parsing.
    val pathPart = if ('?' in raw) raw.substringBefore('?') else raw
    val parts = pathPart.split("/")
    if (parts.size < 2) return
    val book = runCatching { URLDecoder.decode(parts[0], "UTF-8") }.getOrNull() ?: return
    val chapter = parts[1].toIntOrNull() ?: return
    onLoadChapter(book, chapter, preferredTranslation)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatMessageItem(
    message: Message,
    chapterSheetState: ChapterSheetState,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismissSheet: () -> Unit,
    modifier: Modifier = Modifier,
    userMessage: String = "",
    onRetry: (() -> Unit)? = null,
    onFeedback: ((messageLocalId: String, rating: String, comment: String) -> Unit)? = null,
    feedbackGiven: String? = null,
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
    localizedToEnglish: Map<String, String> = emptyMap(),
) {
    val isUser = message.role == Message.Role.USER
    val arrangement = if (isUser) Arrangement.End else Arrangement.Start

    // User bubble: primary colour (matches web's bg-primary-600 for user messages)
    // Assistant bubble: white surface with a subtle border (matches web's bg-white border)
    val bubbleColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.surface
    }
    val textColor = if (isUser) {
        MaterialTheme.colorScheme.onPrimary
    } else {
        MaterialTheme.colorScheme.onSurface
    }

    // Show the retry button when:
    //  - this is an assistant message
    //  - it is NOT currently streaming
    //  - it was flagged as an error
    val showRetry = !isUser && !message.isStreaming && message.isError

    // Render the message bubble for normal messages, and also for error messages
    // that carry explanatory text (e.g. the content-blocked / network-error copy) so
    // the user sees *why* it failed above the Retry button — not a bare button alone.
    val showBubble = !showRetry || message.content.isNotBlank()

    // Show the share button only for finished (non-streaming) assistant messages with content.
    val showShare = !isUser && !message.isStreaming && !message.isError && message.content.isNotBlank()

    val sharePrefix = stringResource(R.string.share_prefix)
    val context = LocalContext.current

    // Blinking cursor alpha — always created to respect Composable call order.
    val infiniteTransition = rememberInfiniteTransition(label = "cursor_blink")
    val cursorAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 500),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "cursor_alpha",
    )

    // State for the chapter sheet opened by tapping an inline verse link in the message text.
    var pendingVerseLink by remember { mutableStateOf<PendingVerseLink?>(null) }
    val linkSheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = arrangement,
    ) {
        Column(
            modifier = Modifier.widthIn(max = 320.dp),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start,
        ) {
            if (showBubble) {
                val bubbleModifier = if (isUser) {
                    // User bubble: filled primary, no border
                    Modifier
                        .background(
                            color = bubbleColor,
                            shape = RoundedCornerShape(
                                topStart = 18.dp,
                                topEnd = 18.dp,
                                bottomStart = 18.dp,
                                bottomEnd = 4.dp,
                            ),
                        )
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                } else {
                    // Assistant bubble: white surface with primary border — matches web card style
                    Modifier
                        .background(
                            color = bubbleColor,
                            shape = RoundedCornerShape(
                                topStart = 4.dp,
                                topEnd = 18.dp,
                                bottomStart = 18.dp,
                                bottomEnd = 18.dp,
                            ),
                        )
                        .border(
                            width = 1.dp,
                            color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                            shape = RoundedCornerShape(
                                topStart = 4.dp,
                                topEnd = 18.dp,
                                bottomStart = 18.dp,
                                bottomEnd = 18.dp,
                            ),
                        )
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                }

                Box(modifier = bubbleModifier) {
                    when {
                        // (a) Waiting for the first chunk — show animated typing dots
                        !isUser && message.isStreaming && message.content.isEmpty() -> {
                            TypingIndicator()
                        }

                        // (b) Streaming with partial content — show text + blinking cursor
                        !isUser && message.isStreaming && message.content.isNotEmpty() -> {
                            Row(verticalAlignment = Alignment.Bottom) {
                                SelectionContainer {
                                    Text(
                                        text = message.content,
                                        style = MaterialTheme.typography.bodyLarge,
                                        color = textColor,
                                    )
                                }
                                Text(
                                    text = "▌",
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = textColor,
                                    modifier = Modifier.alpha(cursorAlpha),
                                )
                            }
                        }

                        // (c) Finished assistant message — render as Markdown with tappable verse refs.
                        !isUser -> {
                            val bodyMedium = MaterialTheme.typography.bodyMedium
                            // Amber colour for verse links — matches web's amber-600 link colour
                            val amberColor = MaterialTheme.colorScheme.tertiary
                            MarkdownText(
                                markdown = injectVerseQuoteHighlights(
                                    injectVerseLinks(
                                        message.content,
                                        verseRefRegex,
                                        message.verses,
                                        localizedToEnglish,
                                    ),
                                ),
                                style = bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
                                linkColor = amberColor,
                                isTextSelectable = true,
                                // MUST stay true: compose-markdowntext is built on Markwon, whose
                                // softBreakAddsNewLine default flipped from true (0.5.x) to false (0.7.x).
                                // With false, single newlines in assistant messages collapse into one
                                // paragraph, breaking existing chat formatting. Do not remove. (BITB-037)
                                enableSoftBreakAddsNewLine = true,
                                onLinkClicked = { url ->
                                    val parsed = parseVerseLink(url, preferredTranslation)
                                    if (parsed != null) {
                                        // Reset chapter state so VerseDetailBottomSheet always gets a fresh load.
                                        onDismissSheet()
                                        pendingVerseLink = parsed
                                        onLoadChapter(parsed.book, parsed.chapter, parsed.translation)
                                    }
                                },
                                beforeSetMarkdown = { _, spanned ->
                                    if (spanned is Spannable) {
                                        applyQuoteHighlights(spanned)
                                    }
                                },
                            )
                        }

                        // (d) User message — plain text bubble, selectable so the
                        // question text can be copied manually (matches assistant text).
                        else -> {
                            // The default selection highlight is derived from the primary
                            // colour, which is also this bubble's background — so a selection
                            // would be nearly invisible. Pick a highlight that contrasts with
                            // the bubble in both themes: dark when the text is light, light
                            // when the text is dark, keeping the selected text readable.
                            val selectionHighlight =
                                if (textColor.luminance() > 0.5f) Color.Black else Color.White
                            val bubbleSelectionColors = remember(selectionHighlight) {
                                TextSelectionColors(
                                    handleColor = selectionHighlight,
                                    backgroundColor = selectionHighlight.copy(alpha = 0.4f),
                                )
                            }
                            CompositionLocalProvider(
                                LocalTextSelectionColors provides bubbleSelectionColors,
                            ) {
                                SelectionContainer {
                                    Text(
                                        text = message.content,
                                        style = MaterialTheme.typography.bodyLarge,
                                        color = textColor,
                                    )
                                }
                            }
                        }
                    }
                }
            }

            // Inline scripture cards — show the actual text of the verses the backend cited
            // for this answer, directly under the message (matching the web's verse cards),
            // so the verse text is visible without opening the top-bar Verses panel.
            if (!isUser && !message.isStreaming && !message.isError) {
                val cited = citedVerses(message)
                if (cited.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        cited.forEach { verse ->
                            InlineVerseCard(
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

            // Action row — feedback (left) and copy+share (right).
            val showFeedback = message.role == Message.Role.ASSISTANT
                && !message.isStreaming
                && message.messageId.isNotBlank()
                && onFeedback != null

            // Copy + share actions, reused as the trailing slot of FeedbackControls
            // or rendered alone when there is no feedback row.
            val trailingActions: @Composable RowScope.() -> Unit = {
                if (showShare) {
                    IconButton(
                        onClick = {
                            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            clipboard.setPrimaryClip(ClipData.newPlainText("message", message.content))
                            Toast.makeText(context, context.getString(R.string.action_copied), Toast.LENGTH_SHORT).show()
                        },
                    ) {
                        Icon(
                            imageVector = Icons.Default.ContentCopy,
                            contentDescription = stringResource(R.string.action_copy_message),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    IconButton(
                        onClick = {
                            val shareText = if (userMessage.isNotBlank()) {
                                "$sharePrefix\n\nQ: $userMessage\n\n${message.content}"
                            } else {
                                "$sharePrefix\n\n${message.content}"
                            }
                            ShareCompat.IntentBuilder(context)
                                .setType("text/plain")
                                .setText(shareText)
                                .startChooser()
                        },
                    ) {
                        Icon(
                            imageVector = Icons.Default.Share,
                            contentDescription = stringResource(R.string.action_share_message),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            if (showFeedback) {
                FeedbackControls(
                    feedbackGiven = feedbackGiven,
                    onSubmit = { rating, comment -> onFeedback!!(message.id, rating, comment) },
                    trailing = trailingActions,
                )
            } else if (showShare) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Spacer(modifier = Modifier.weight(1f))
                    trailingActions()
                }
            }

            // Inline Retry button for error assistant messages
            if (showRetry && onRetry != null) {
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedButton(
                    onClick = onRetry,
                ) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.padding(end = 4.dp),
                    )
                    Text(text = stringResource(R.string.action_retry))
                }
            }

        }
    }

    // Chapter bottom sheet — opened when the user taps an inline verse link in the message text.
    // We synthesise a minimal Verse object so VerseDetailBottomSheet can highlight the target verse.
    pendingVerseLink?.let { link ->
        // Build a synthetic Verse from the link so VerseDetailBottomSheet can highlight it.
        val syntheticVerse = buildSyntheticVerse(link, chapterSheetState)
        VerseDetailBottomSheet(
            verse = syntheticVerse,
            preferredTranslation = link.translation,
            chapterState = chapterSheetState,
            onLoadChapter = onLoadChapter,
            sheetState = linkSheetState,
            onDismiss = {
                pendingVerseLink = null
                onDismissSheet()
            },
        )
    }
}

/**
 * Highlights quoted scripture passages with amber background + italic serif styling,
 * matching the web's `bg-amber-50 italic font-serif` look.
 *
 * Each [QUOTE_HIGHLIGHT_REGEX] match gets a set of standard inline spans
 * ([BackgroundColorSpan], [ForegroundColorSpan], [StyleSpan], [TypefaceSpan]). Unlike a
 * [android.text.style.ReplacementSpan], these are laid out by the platform's normal text
 * engine, so a long quote **wraps across lines** instead of being measured as one
 * unbreakable unit and clipped at the bubble's right edge. The amber background follows the
 * text onto each wrapped line. This is language-agnostic — the regex already matches
 * straight, curly, German, guillemet and CJK quote pairs.
 */
internal fun applyQuoteHighlights(spanned: Spannable) {
    QUOTE_HIGHLIGHT_REGEX.findAll(spanned).forEach { match ->
        val start = match.range.first
        val end = match.range.last + 1
        spanned.setSpan(
            BackgroundColorSpan(0xFFFFFBEB.toInt()),
            start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        spanned.setSpan(
            ForegroundColorSpan(0xFF78350F.toInt()),
            start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        spanned.setSpan(
            StyleSpan(Typeface.ITALIC),
            start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        spanned.setSpan(
            TypefaceSpan("serif"),
            start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
    }
}

/**
 * Builds a [Verse] stub from a [PendingVerseLink].
 *
 * If the chapter has already loaded successfully we attempt to pull the actual verse text from
 * [chapterState]; otherwise we fall back to a placeholder so the sheet can still be shown.
 */
private fun buildSyntheticVerse(link: PendingVerseLink, chapterState: ChapterSheetState): Verse {
    val actualText = if (chapterState is ChapterSheetState.Success) {
        chapterState.response.verses
            .firstOrNull { it.verseNumber == link.verseNumber }
            ?.text
            ?: ""
    } else {
        ""
    }
    val translation = link.translation
        ?: if (chapterState is ChapterSheetState.Success) chapterState.response.translation ?: "KJV" else "KJV"
    // Prefer the link's localized name (available immediately on tap); backstop from the
    // chapter response once it loads.
    val localizedBook = link.localizedBook
        ?: (chapterState as? ChapterSheetState.Success)?.response?.localizedBook
    return Verse(
        book = link.book,
        chapter = link.chapter,
        verse = link.verseNumber,
        text = actualText,
        translation = translation,
        localizedBook = localizedBook,
    )
}

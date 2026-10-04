package org.voxquieta.app.tts

import org.voxquieta.app.presentation.components.DEFAULT_VERSE_REF_REGEX
import org.voxquieta.app.utils.VerseGrammar
import org.voxquieta.app.utils.knownBooks
import org.voxquieta.app.utils.normalizeTraditionalToSimplified

/**
 * BITB-119: turn an assistant answer (markdown) into text a speech synthesizer can read.
 *
 * The rules are specified once in tests/fixtures/speakable_text.json and implemented twice:
 * here and in frontend/src/lib/speakableText.ts. SpeakableTextParityTest verifies this
 * implementation against that fixture (and that [VERSE_SPEECH_TEMPLATES] equals the
 * fixture's table), so the two clients cannot drift apart.
 *
 * Verse references are detected with the app's EXISTING verse parser — the `verseRefRegex`
 * that ChatScreen already builds for ChatMessageItem — not a new regex family. That regex
 * also matches chapter-only references ("Psalm 23"); those are deliberately skipped so they
 * are left exactly as written, matching the web parser (which only matches chapter:verse).
 */

/** Maximum characters per utterance chunk (several engines truncate long utterances). */
internal const val MAX_CHUNK_CHARS = 200

/** Spoken form of a verse reference. Placeholders: {book} {c} {v} {e}. */
internal data class VerseSpeechTemplate(val verse: String, val range: String)

/** Mirrors `verseTemplates` in tests/fixtures/speakable_text.json (parity-tested). */
internal val VERSE_SPEECH_TEMPLATES: Map<String, VerseSpeechTemplate> = mapOf(
    "en" to VerseSpeechTemplate(
        "{book} chapter {c}, verse {v}",
        "{book} chapter {c}, verses {v} to {e}",
    ),
    "it" to VerseSpeechTemplate(
        "{book} capitolo {c}, versetto {v}",
        "{book} capitolo {c}, versetti da {v} a {e}",
    ),
    "de" to VerseSpeechTemplate(
        "{book} Kapitel {c}, Vers {v}",
        "{book} Kapitel {c}, Verse {v} bis {e}",
    ),
    "es" to VerseSpeechTemplate(
        "{book} capítulo {c}, versículo {v}",
        "{book} capítulo {c}, versículos {v} al {e}",
    ),
    "fr" to VerseSpeechTemplate(
        "{book} chapitre {c}, verset {v}",
        "{book} chapitre {c}, versets {v} à {e}",
    ),
    "pt" to VerseSpeechTemplate(
        "{book} capítulo {c}, versículo {v}",
        "{book} capítulo {c}, versículos {v} a {e}",
    ),
    "ar" to VerseSpeechTemplate(
        "{book} الإصحاح {c}، الآية {v}",
        "{book} الإصحاح {c}، الآيات {v} إلى {e}",
    ),
    "ru" to VerseSpeechTemplate(
        "{book}, глава {c}, стих {v}",
        "{book}, глава {c}, стихи с {v} по {e}",
    ),
    "zh" to VerseSpeechTemplate(
        "{book}第{c}章第{v}节",
        "{book}第{c}章第{v}至{e}节",
    ),
    "hi" to VerseSpeechTemplate(
        "{book} अध्याय {c}, पद {v}",
        "{book} अध्याय {c}, पद {v} से {e}",
    ),
    "ko" to VerseSpeechTemplate(
        "{book} {c}장 {v}절",
        "{book} {c}장 {v}절부터 {e}절까지",
    ),
)

private fun templatesFor(language: String): VerseSpeechTemplate {
    val primary = language.lowercase().split('-', '_').first()
    return VERSE_SPEECH_TEMPLATES[primary] ?: VERSE_SPEECH_TEMPLATES.getValue("en")
}

private fun fill(template: String, book: String, c: String, v: String, e: String): String =
    template
        .replace("{book}", book)
        .replace("{c}", c)
        .replace("{v}", v)
        .replace("{e}", e)

/** Devanagari (U+0966-096F) and Eastern Arabic (U+0660-0669) digits -> ASCII digits. */
private fun normalizeDigits(s: String): String = buildString(s.length) {
    for (ch in s) {
        append(
            when (ch) {
                in '०'..'९' -> '0' + (ch - '०')
                in '٠'..'٩' -> '0' + (ch - '٠')
                else -> ch
            },
        )
    }
}

private val RANGE_SEPARATORS: String =
    VerseGrammar.RANGE_SEPARATORS.joinToString("") { it.toString() }

/** Replace every recognised verse reference with its spoken form. */
private fun speakVerseReferences(
    text: String,
    language: String,
    verseRefRegex: Regex,
    localizedToEnglish: Map<String, String>,
): String {
    val template = templatesFor(language)
    val known = knownBooks(localizedToEnglish)
    // Match against a Simplified-Chinese shadow copy (length-preserving) so Traditional book
    // names are recognised, but slice the book from the ORIGINAL text (mirrors injectVerseLinks).
    val search = normalizeTraditionalToSimplified(text)

    val out = StringBuilder(text.length + 32)
    var copiedUpTo = 0
    var searchStart = 0
    while (searchStart <= search.length) {
        val result = verseRefRegex.find(search, searchStart) ?: break
        val g = result.groupValues

        // Alt 1 (numbered prefix) populates groups 1-3; Alt 2 populates groups 4-6.
        val shadowBook: String
        val bookRange: IntRange
        val chapter: String
        val verseAndRange: String
        if (g[1].isNotEmpty()) {
            shadowBook = g[1]
            bookRange = result.groups[1]!!.range
            chapter = g[2]
            verseAndRange = g[3]
        } else {
            shadowBook = g[4]
            bookRange = result.groups[4]!!.range
            chapter = g[5]
            verseAndRange = g[6]
        }

        // Chapter-only references are left as written; a non-book (prose, clock time,
        // greedy over-match) is rejected. Either way rewind one character past the start so
        // a valid reference hidden inside the match is still found.
        if (verseAndRange.isEmpty() || shadowBook.trim().lowercase() !in known) {
            searchStart = result.range.first + 1
            continue
        }

        val book = text.substring(bookRange.first, bookRange.last + 1).trim()
        val rangeAt = verseAndRange.indexOfFirst { it in RANGE_SEPARATORS }
        val verse = normalizeDigits(if (rangeAt >= 0) verseAndRange.substring(0, rangeAt) else verseAndRange)
        val end = if (rangeAt >= 0) normalizeDigits(verseAndRange.substring(rangeAt + 1)) else ""

        out.append(text, copiedUpTo, result.range.first)
        out.append(
            fill(
                if (end.isNotEmpty()) template.range else template.verse,
                book,
                normalizeDigits(chapter),
                verse,
                end,
            ),
        )
        copiedUpTo = result.range.last + 1
        searchStart = result.range.last + 1
    }
    out.append(text, copiedUpTo, text.length)
    return out.toString()
}

private val IMAGE_REGEX = Regex("""!\[([^\]]*)\]\([^)]*\)""")
private val LINK_REGEX = Regex("""\[([^\]]*)\]\([^)]*\)""")
// Leading blanks are consumed; trailing sentence punctuation / closing paren is left in place.
// URL characters are printable ASCII only (CJK has no spaces); parens only when balanced.
private val URL_REGEX = Regex("""[ \t]*https?://(?:[!-'*-~]|\([!-'*-~]*\))*(?<![.,;:!?])""")
private val EMPTY_PARENS_REGEX = Regex("""[ \t]*(?:\(\)|（）)""")
private val ANGLE_GUILLEMET_REGEX = Regex("""<<\s*([^<>]*?)\s*>>""")
private val CJK_GUILLEMET_REGEX = Regex("""《\s*([^《》]*?)\s*》""")
private val HORIZONTAL_RULE_REGEX = Regex("""^\s*([-*_]\s*){3,}$""")
private val CODE_FENCE_REGEX = Regex("""^\s*```.*$""")
private val HEADING_REGEX = Regex("""^\s{0,3}#{1,6}\s+""")
private val BLOCKQUOTE_REGEX = Regex("""^\s*>+\s?""")
private val BULLET_REGEX = Regex("""^\s*[-*+]\s+""")
private val LEADING_UNDERSCORES_REGEX = Regex("""(^|[\s(])_+""")
private val TRAILING_UNDERSCORES_REGEX = Regex("""_+(?=$|[\s).,;:!?])""")
private val INLINE_SPACE_REGEX = Regex("""[ \t ]+""")

/**
 * Normalize assistant markdown into plain speakable text (FR5).
 * Lines are joined with "\n"; blank lines collapse (each line is a sentence break).
 *
 * @param verseRefRegex the app's existing verse parser regex (see ChatScreen).
 * @param localizedToEnglish the backend book-name map, for the known-book allowlist.
 */
internal fun normalizeForSpeech(
    markdown: String,
    language: String,
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
    localizedToEnglish: Map<String, String> = emptyMap(),
): String {
    var text = markdown.replace("\r\n", "\n").replace('\r', '\n')

    // Markdown images -> alt text; links -> link text; bare URLs removed.
    text = IMAGE_REGEX.replace(text, "$1")
    text = LINK_REGEX.replace(text, "$1")
    text = URL_REGEX.replace(text, "")
    text = EMPTY_PARENS_REGEX.replace(text, "")

    // Guillemets around a book name: <<Book>> / 《Book》 -> Book.
    text = ANGLE_GUILLEMET_REGEX.replace(text, "$1")
    text = CJK_GUILLEMET_REGEX.replace(text, "$1")

    text = text.split("\n").joinToString("\n") { raw ->
        if (HORIZONTAL_RULE_REGEX.containsMatchIn(raw)) {
            ""
        } else {
            var line = raw
            line = CODE_FENCE_REGEX.replace(line, "")
            line = HEADING_REGEX.replace(line, "")
            line = BLOCKQUOTE_REGEX.replace(line, "")
            line = BULLET_REGEX.replace(line, "")
            // Inline emphasis / code markers.
            line = line.replace("*", "").replace("`", "").replace("~~", "")
            line = LEADING_UNDERSCORES_REGEX.replace(line, "$1")
            line = TRAILING_UNDERSCORES_REGEX.replace(line, "")
            line
        }
    }

    text = speakVerseReferences(text, language, verseRefRegex, localizedToEnglish)

    return text.split("\n")
        .map { INLINE_SPACE_REGEX.replace(it, " ").trim() }
        .filter { it.isNotEmpty() }
        .joinToString("\n")
}

// Terminators that always end a sentence, and ASCII ones that only do so before
// whitespace/end (so "1.5" or "e.g.x" stays intact).
private const val ALWAYS_TERMINATORS = "。！？।॥؟"
private const val SPACE_TERMINATORS = ".!?"
private const val CLOSERS = "\"'”’»)]」』》"

/** Split one line of text into sentences at terminators. */
private fun splitSentences(text: String): List<String> {
    val sentences = mutableListOf<String>()
    val current = StringBuilder()
    var i = 0
    while (i < text.length) {
        val ch = text[i]
        current.append(ch)
        val always = ch in ALWAYS_TERMINATORS
        val spaced = ch in SPACE_TERMINATORS &&
            (i + 1 >= text.length || text[i + 1].isWhitespace() || text[i + 1] in CLOSERS)
        if (always || spaced) {
            // Swallow trailing terminators / closing quotes into this sentence.
            while (i + 1 < text.length &&
                (text[i + 1] in ALWAYS_TERMINATORS || text[i + 1] in SPACE_TERMINATORS || text[i + 1] in CLOSERS)
            ) {
                i++
                current.append(text[i])
            }
            val sentence = current.toString().trim()
            if (sentence.isNotEmpty()) sentences.add(sentence)
            current.setLength(0)
        }
        i++
    }
    val tail = current.toString().trim()
    if (tail.isNotEmpty()) sentences.add(tail)
    return sentences
}

/** Hard-split an over-long sentence into pieces of at most [max] characters. */
private fun hardSplit(sentence: String, max: Int): MutableList<String> {
    val parts = mutableListOf<String>()
    var rest = sentence
    while (rest.length > max) {
        var cut = if (rest[max] == ' ') max else rest.lastIndexOf(' ', max - 1)
        if (cut <= 0) {
            cut = max
            // Never cut a surrogate pair in half.
            if (Character.isHighSurrogate(rest[cut - 1])) cut -= 1
        }
        parts.add(rest.substring(0, cut).trim())
        rest = rest.substring(cut).trim()
    }
    if (rest.isNotEmpty()) parts.add(rest)
    return parts
}

/** Joiner between two packed sentences: none after a CJK full stop, else a space. */
private fun joiner(previous: String): String =
    if (previous.last() in "。！？") "" else " "

/**
 * Split normalized text into chunks of at most [max] characters, at sentence and line
 * boundaries, so the whole answer can be queued as separate utterances (FR6).
 */
internal fun chunkForSpeech(text: String, max: Int = MAX_CHUNK_CHARS): List<String> {
    val chunks = mutableListOf<String>()
    var current = ""
    fun flush() {
        if (current.isNotEmpty()) chunks.add(current)
        current = ""
    }

    // A newline always ends the current chunk (a paragraph / list item is its own
    // utterance, giving a natural pause); sentences within a line are packed together.
    for (line in text.split("\n")) {
        for (sentence in splitSentences(line)) {
            if (sentence.length > max) {
                flush()
                val parts = hardSplit(sentence, max)
                current = if (parts.isEmpty()) "" else parts.removeAt(parts.lastIndex)
                chunks.addAll(parts)
                continue
            }
            if (current.isEmpty()) {
                current = sentence
            } else if (current.length + joiner(current).length + sentence.length <= max) {
                current += joiner(current) + sentence
            } else {
                flush()
                current = sentence
            }
        }
        flush()
    }
    return chunks
}

/** Convenience: markdown -> speakable chunks. */
internal fun speakableChunks(
    markdown: String,
    language: String,
    verseRefRegex: Regex = DEFAULT_VERSE_REF_REGEX,
    localizedToEnglish: Map<String, String> = emptyMap(),
): List<String> =
    chunkForSpeech(normalizeForSpeech(markdown, language, verseRefRegex, localizedToEnglish))

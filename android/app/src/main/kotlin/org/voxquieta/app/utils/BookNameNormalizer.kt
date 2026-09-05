package org.voxquieta.app.utils

/**
 * Normalizes a localized Bible book name to its canonical English form using the
 * `localized_to_english` map fetched from the backend (`/api/v1/scripture/book-names`).
 *
 * Why this exists: the LLM writes verse references in the conversation language, e.g.
 * German "2 Korinther 9:8" or "Matthäus 5:7". When the user taps such a reference we must
 * fetch the chapter from the backend, whose lookup keys are English ("2 Corinthians",
 * "Matthew"). Sending the raw localized name returns a 404 → the verse sheet shows the
 * "Serverfehler" error with an empty body.
 *
 * The backend DB lookup is case-insensitive, so returning the map's English value (whatever
 * its casing) resolves correctly. Inputs that are already English — or any name not in the
 * map — are returned unchanged, so this is safe to call unconditionally for every language.
 *
 * Numbered-book tolerance: the map keys German numbered books *with* a period
 * ("2. Korinther"), but LLMs frequently emit them *without* one ("2 Korinther"). We retry a
 * few period/spacing variants of a leading "1".."3" prefix so both forms resolve.
 */

private val NUMBERED_PREFIX = Regex("^([1-3])\\.?\\s*(.+)$")

/**
 * Looks up [name] in [map], also trying numbered-book period/spacing variants
 * ("2 Korinther" ⇄ "2. Korinther" ⇄ "2.Korinther"). Returns null when nothing matches.
 */
private fun lookupWithNumberedVariants(name: String, map: Map<String, String>): String? {
    map[name]?.let { return it }
    NUMBERED_PREFIX.find(name)?.let { m ->
        val number = m.groupValues[1]
        val rest = m.groupValues[2].trim()
        for (variant in listOf("$number. $rest", "$number $rest", "$number.$rest")) {
            map[variant]?.let { return it }
        }
    }
    return null
}

fun normalizeBookName(raw: String, localizedToEnglish: Map<String, String>): String {
    val trimmed = raw.trim()

    // 1) Runtime API map (keys are capitalized localized names): covers single-word books in
    // every language ("Matthäus", "Giovanni", "约翰福音", …) and the canonical numbered forms
    // ("2. Korinther", "1 Corinthians").
    lookupWithNumberedVariants(trimmed, localizedToEnglish)?.let { return it }

    // 2) Bundled fallback map (keys are lowercased): resolves localized names offline / before
    // the /api/v1/scripture/book-names call returns. Values are lowercase English canonicals;
    // the backend lookup is case-insensitive, so lowercase targets resolve correctly.
    lookupWithNumberedVariants(trimmed.lowercase(), LOCALIZED_BOOK_TO_ENGLISH)?.let { return it }

    // Unknown name or already-English → leave unchanged (backend resolves English directly).
    return raw
}

/**
 * Every recognised book name (lowercased): the union of the bundled fallback map's keys and
 * its English canonical values. Populated once at class load.
 */
private val BUNDLED_KNOWN_BOOKS: Set<String> = buildSet {
    for ((localized, english) in LOCALIZED_BOOK_TO_ENGLISH) {
        add(localized)
        add(english)
    }
}

/**
 * Returns the set of all recognised book names (lowercased): the bundled fallback map
 * (keys ∪ English values) plus any runtime [localizedToEnglish] the backend supplied
 * (keys ∪ values). Mirrors the web frontend's `getKnownBooks()`.
 *
 * Callers that validate many candidates in a row (e.g. injectVerseLinks) should call this
 * once and reuse the result rather than calling [isKnownBook] per candidate.
 */
fun knownBooks(localizedToEnglish: Map<String, String>): Set<String> {
    if (localizedToEnglish.isEmpty()) return BUNDLED_KNOWN_BOOKS
    return buildSet {
        addAll(BUNDLED_KNOWN_BOOKS)
        for ((localized, english) in localizedToEnglish) {
            add(localized.lowercase())
            add(english.lowercase())
        }
    }
}

/**
 * Returns true when [book] is a real Bible book name in any supported language.
 *
 * This is the allowlist that gates greedy verse-regex over-matches: the regex deliberately
 * accepts any "Word digit:digit" shape (to stay language- and case-agnostic), so this check
 * is what prevents prose ("Trost der Hoffnung 5:5"), clock times ("um 14:30"), and words
 * swallowed by a connector ("you of Psalm") from being linked. Mirrors the web `isKnownBook`.
 *
 * Traditional Chinese retry (BITB-110): [knownBooks] only stores Simplified forms, so a
 * Traditional-script name (e.g. "約翰福音") needs its Simplified form tried too. Normalize the
 * candidate, never the set — mirrors verseExtraction.ts's `isKnownBook`.
 */
fun isKnownBook(book: String, localizedToEnglish: Map<String, String> = emptyMap()): Boolean {
    val key = book.trim().lowercase()
    val known = knownBooks(localizedToEnglish)
    return key in known || normalizeTraditionalToSimplified(key) in known
}

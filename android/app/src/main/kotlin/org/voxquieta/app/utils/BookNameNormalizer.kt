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

fun normalizeBookName(raw: String, localizedToEnglish: Map<String, String>): String {
    val trimmed = raw.trim()

    // Direct hit: covers single-word books in every language ("Matthäus", "Giovanni",
    // "约翰福音", …) and the canonical numbered forms ("2. Korinther", "1 Corinthians").
    localizedToEnglish[trimmed]?.let { return it }

    // Numbered-book period/spacing variants: "2 Korinther" ⇄ "2. Korinther" ⇄ "2.Korinther".
    NUMBERED_PREFIX.find(trimmed)?.let { m ->
        val number = m.groupValues[1]
        val rest = m.groupValues[2].trim()
        for (variant in listOf("$number. $rest", "$number $rest", "$number.$rest")) {
            localizedToEnglish[variant]?.let { return it }
        }
    }

    // Unknown name or already-English → leave unchanged (backend resolves English directly).
    return raw
}

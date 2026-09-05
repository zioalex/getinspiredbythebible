package org.voxquieta.app.utils

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Unit tests for [normalizeBookName].
 *
 * The fixture mirrors the shape of the backend `localized_to_english` map
 * (`/api/v1/scripture/book-names`): keys are capitalized localized names, values are the
 * canonical English book names. German numbered books are keyed *with* a period
 * ("2. Korinther"), exactly as the backend stores them.
 */
class BookNameNormalizerTest {

    private val map = mapOf(
        // German (Schlachter) — note the period on numbered books
        "Matthäus" to "Matthew",
        "Lukas" to "Luke",
        "Römer" to "Romans",
        "1. Mose" to "Genesis",
        "1. Korinther" to "1 Corinthians",
        "2. Korinther" to "2 Corinthians",
        "2. Könige" to "2 Kings",
        // Italian
        "Giovanni" to "John",
        "1 Corinzi" to "1 Corinthians",
        // Spanish
        "Juan" to "John",
        // French
        "Jean" to "John",
        // Portuguese
        "João" to "John",
        // Russian
        "Иоанна" to "John",
        // Chinese
        "约翰福音" to "John",
        // Korean
        "요한복음" to "John",
    )

    // ── The reported bug: German numbered book without the period ──────────────

    @Test
    fun `normalizes German 2 Korinther without period to English`() {
        // The LLM emits "2 Korinther" (no period); the backend key is "2. Korinther".
        assertEquals("2 Corinthians", normalizeBookName("2 Korinther", map))
    }

    @Test
    fun `normalizes German 2 Korinther with period`() {
        assertEquals("2 Corinthians", normalizeBookName("2. Korinther", map))
    }

    @Test
    fun `normalizes German 2 Korinther without space after period`() {
        assertEquals("2 Corinthians", normalizeBookName("2.Korinther", map))
    }

    @Test
    fun `normalizes German 1 Mose without period`() {
        assertEquals("Genesis", normalizeBookName("1 Mose", map))
    }

    @Test
    fun `normalizes German 2 Koenige without period`() {
        assertEquals("2 Kings", normalizeBookName("2 Könige", map))
    }

    // ── Single-word books across all supported languages ───────────────────────

    @Test
    fun `normalizes single-word German books`() {
        assertEquals("Matthew", normalizeBookName("Matthäus", map))
        assertEquals("Luke", normalizeBookName("Lukas", map))
        assertEquals("Romans", normalizeBookName("Römer", map))
    }

    @Test
    fun `normalizes books in every supported language`() {
        assertEquals("John", normalizeBookName("Giovanni", map)) // Italian
        assertEquals("John", normalizeBookName("Juan", map)) // Spanish
        assertEquals("John", normalizeBookName("Jean", map)) // French
        assertEquals("John", normalizeBookName("João", map)) // Portuguese
        assertEquals("John", normalizeBookName("Иоанна", map)) // Russian
        assertEquals("John", normalizeBookName("约翰福音", map)) // Chinese
        assertEquals("John", normalizeBookName("요한복음", map)) // Korean
    }

    @Test
    fun `normalizes Italian numbered book with space`() {
        assertEquals("1 Corinthians", normalizeBookName("1 Corinzi", map))
    }

    // ── English / already-canonical / unknown inputs pass through unchanged ─────

    @Test
    fun `leaves English book names unchanged`() {
        // English names are not keys in the map; the backend resolves them directly.
        assertEquals("John", normalizeBookName("John", map))
        assertEquals("2 Corinthians", normalizeBookName("2 Corinthians", map))
    }

    @Test
    fun `leaves unknown names unchanged`() {
        assertEquals("Nonexistent", normalizeBookName("Nonexistent", map))
        assertEquals("3 Foobar", normalizeBookName("3 Foobar", map))
    }

    @Test
    fun `leaves Latin Vulgate name unchanged because it is in no map`() {
        // "Proverbia" is Latin; the German book is "Sprüche". The map can't resolve it, so
        // normalization returns it unchanged — which is why the link layer falls back to
        // matching the cited verse list by chapter:verse instead.
        assertEquals("Proverbia", normalizeBookName("Proverbia", map))
    }

    @Test
    fun `trims surrounding whitespace before lookup`() {
        assertEquals("2 Corinthians", normalizeBookName("  2 Korinther  ", map))
    }

    @Test
    fun `resolves via the bundled fallback map when the API map is empty`() {
        // Before the /api/v1/scripture/book-names call returns, the runtime map is empty.
        // The bundled fallback (lowercased keys, lowercase English values) still resolves
        // localized names offline — the backend chapter lookup is case-insensitive.
        assertEquals("2 corinthians", normalizeBookName("2 Korinther", emptyMap()))
        assertEquals("john", normalizeBookName("Giovanni", emptyMap()))
    }

    @Test
    fun `leaves genuinely unknown names unchanged even with the bundled map`() {
        assertEquals("Nonexistent", normalizeBookName("Nonexistent", emptyMap()))
        assertEquals("Proverbia", normalizeBookName("Proverbia", emptyMap()))
    }

    // ── isKnownBook allowlist (gates greedy regex over-matches) ─────────────────

    @Test
    fun `isKnownBook recognizes books from the bundled map without the API`() {
        assertEquals(true, isKnownBook("Psalm")) // English alias key
        assertEquals(true, isKnownBook("psalm")) // lowercase
        assertEquals(true, isKnownBook("Psalms")) // English canonical value
        assertEquals(true, isKnownBook("Giovanni")) // Italian key
        assertEquals(true, isKnownBook("Isaiah")) // English value
    }

    @Test
    fun `isKnownBook rejects non-books`() {
        assertEquals(false, isKnownBook("you of Psalm"))
        assertEquals(false, isKnownBook("Trost der Hoffnung"))
        assertEquals(false, isKnownBook("um"))
    }

    @Test
    fun `isKnownBook also honours runtime API names`() {
        assertEquals(true, isKnownBook("Matthäus", map))
    }

    // ── isKnownBook Traditional Chinese retry (BITB-110) ────────────────────────

    @Test
    fun `isKnownBook recognizes Traditional Chinese book names via the bundled map`() {
        assertEquals(true, isKnownBook("約翰福音")) // John, Traditional
        assertEquals(true, isKnownBook("馬太福音")) // Matthew, Traditional
        assertEquals(true, isKnownBook("創世記")) // Genesis, fully Traditional
    }

    @Test
    fun `isKnownBook recognizes mixed-script Traditional plus Simplified book names`() {
        assertEquals(true, isKnownBook("創世记")) // Traditional 創 + already-Simplified 世记
        assertEquals(true, isKnownBook("傳道书")) // Traditional 傳 + already-Simplified 道书
    }

    @Test
    fun `isKnownBook recognizes Traditional Chinese book names via the runtime API map`() {
        val chineseMap = mapOf("约翰福音" to "John")
        assertEquals(true, isKnownBook("約翰福音", chineseMap))
    }
}

package org.voxquieta.app.utils

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Guards the bundled fallback book-name map against silent drift from its canonical source
 * (BITB-059): tests/fixtures/localized_book_map.json, generated into this file by
 * scripts/generate_localized_book_map.py. Loaded from the test classpath via the
 * sourceSets["test"].resources.srcDir("../../tests/fixtures") entry in build.gradle.kts
 * (already wired for VerseCorpusParityTest / BITB-059 AC#4).
 *
 * This replaces the old entry-count-only guard (counts can match while contents diverge —
 * the exact drift mode the 2026-07 adversarial audit's A1 finding called out) with a
 * content-equivalence check: every key and value must match the canonical JSON exactly.
 */
@Serializable
private data class LocalizedBookMapFixture(
    val description: String,
    val book_map: Map<String, String>,
)

class LocalizedBookToEnglishTest {

    private fun loadCanonicalMap(): Map<String, String> {
        val stream =
            javaClass.classLoader?.getResourceAsStream("localized_book_map.json")
                ?: error(
                    "localized_book_map.json not found on the test classpath — check the " +
                        "sourceSets[\"test\"].resources.srcDir(\"../../tests/fixtures\") entry " +
                        "in android/app/build.gradle.kts"
                )
        val raw = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        return Json { ignoreUnknownKeys = true }
            .decodeFromString<LocalizedBookMapFixture>(raw)
            .book_map
    }

    @Test
    fun `matches the canonical map entry for entry`() {
        val canonical = loadCanonicalMap()
        val actual = LOCALIZED_BOOK_TO_ENGLISH

        val missing = canonical.keys - actual.keys
        val extra = actual.keys - canonical.keys
        val mismatched =
            (canonical.keys intersect actual.keys).filter { canonical[it] != actual[it] }

        val failures = mutableListOf<String>()
        if (missing.isNotEmpty()) failures += "missing keys (in canonical, not in Kotlin): $missing"
        if (extra.isNotEmpty()) failures += "extra keys (in Kotlin, not in canonical): $extra"
        for (key in mismatched) {
            failures += "value mismatch for '$key': canonical='${canonical[key]}' kotlin='${actual[key]}'"
        }

        assertTrue(
            "LocalizedBookToEnglish.kt is out of sync with tests/fixtures/localized_book_map.json " +
                "— run `python scripts/generate_localized_book_map.py` and commit the result.\n" +
                failures.joinToString("\n"),
            failures.isEmpty(),
        )
    }

    @Test
    fun `entry count matches the canonical map`() {
        assertEquals(loadCanonicalMap().size, LOCALIZED_BOOK_TO_ENGLISH.size)
    }

    @Test
    fun `maps to exactly the 66 canonical English books`() {
        assertEquals(66, LOCALIZED_BOOK_TO_ENGLISH.values.toSet().size)
    }

    @Test
    fun `keys and values are all lowercase`() {
        for ((k, v) in LOCALIZED_BOOK_TO_ENGLISH) {
            assertEquals("key not lowercased: $k", k.lowercase(), k)
            assertEquals("value not lowercased: $v", v.lowercase(), v)
        }
    }

    @Test
    fun `resolves the key English aliases used by the reported bug`() {
        assertEquals("psalms", LOCALIZED_BOOK_TO_ENGLISH["psalm"])
        assertEquals("psalms", LOCALIZED_BOOK_TO_ENGLISH["salmos"])
        assertEquals("isaiah", LOCALIZED_BOOK_TO_ENGLISH["isaías"])
        assertTrue(LOCALIZED_BOOK_TO_ENGLISH.containsKey("song of solomon"))
    }
}

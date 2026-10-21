package org.voxquieta.app.tts

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.components.buildVerseRefRegex
import org.voxquieta.app.presentation.components.cjkBookNamesFrom
import org.voxquieta.app.utils.LOCALIZED_BOOK_TO_ENGLISH

/**
 * BITB-119 — shared cross-platform speakable-text fixture (Android side).
 *
 * Loads tests/fixtures/speakable_text.json (shared with the web vitest suite — see
 * tests/fixtures/README.md), which is made available to this JVM unit test through the existing
 * `sourceSets["test"].resources.srcDir("../../tests/fixtures")` entry in build.gradle.kts, and
 * asserts that [normalizeForSpeech] / [chunkForSpeech] reproduce every expected string and that
 * [VERSE_SPEECH_TEMPLATES] equals the fixture's template table.
 */
@Serializable
private data class FixtureTemplate(val verse: String, val range: String)

@Serializable
private data class NormalizeCase(
    val id: String,
    val language: String,
    val input: String,
    val expected: String,
    val origin: String,
    val skip: List<String> = emptyList(),
    val skipReason: String = "",
)

@Serializable
private data class ChunkCase(
    val id: String,
    val language: String,
    val input: String,
    val expected: List<String>,
)

@Serializable
private data class SpeakableFixture(
    val description: String,
    val maxChunkChars: Int,
    val verseTemplates: Map<String, FixtureTemplate>,
    @kotlinx.serialization.SerialName("normalize_cases") val normalizeCases: List<NormalizeCase>,
    @kotlinx.serialization.SerialName("chunk_cases") val chunkCases: List<ChunkCase>,
)

class SpeakableTextParityTest {

    private fun loadFixture(): SpeakableFixture {
        val stream = javaClass.classLoader?.getResourceAsStream("speakable_text.json")
            ?: error(
                "speakable_text.json not found on the test classpath — check the " +
                    "sourceSets[\"test\"].resources.srcDir(\"../../tests/fixtures\") entry in " +
                    "android/app/build.gradle.kts",
            )
        val raw = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        return Json { ignoreUnknownKeys = true }.decodeFromString<SpeakableFixture>(raw)
    }

    /**
     * Same construction as ChatScreen: bundled multi-word names plus the Han/Hangul names
     * (cjkBookNamesFrom) for no-space CJK/Korean matching.
     */
    private fun verseRegex(): Regex {
        val multiWordNames = LOCALIZED_BOOK_TO_ENGLISH.keys
            .filter { it.contains(' ') && !it.first().isDigit() }
            .sortedByDescending { it.length }
        return buildVerseRefRegex(multiWordNames, cjkBookNamesFrom(LOCALIZED_BOOK_TO_ENGLISH))
    }

    @Test
    fun `fixture covers all 11 languages and requires a reason for every skip`() {
        val fixture = loadFixture()
        val languages = listOf("en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko")
        assertEquals(languages.sorted(), fixture.verseTemplates.keys.sorted())
        for (lang in languages) {
            val ids = fixture.normalizeCases.filter { it.language == lang }.map { it.id }
            assertTrue("$lang needs a verse_$lang case", "verse_$lang" in ids)
            assertTrue("$lang needs a range_$lang case", "range_$lang" in ids)
        }
        for (case in fixture.normalizeCases) {
            if (case.skip.isNotEmpty()) {
                assertTrue("${case.id}: skip needs a skipReason", case.skipReason.isNotBlank())
            }
        }
    }

    @Test
    fun `android verse template table equals the fixture's`() {
        val fixture = loadFixture()
        val android = VERSE_SPEECH_TEMPLATES.mapValues { FixtureTemplate(it.value.verse, it.value.range) }
        assertEquals(fixture.verseTemplates, android)
    }

    @Test
    fun `normalize cases match the shared fixture`() {
        val fixture = loadFixture()
        val regex = verseRegex()
        val failures = mutableListOf<String>()
        for (case in fixture.normalizeCases) {
            if ("android" in case.skip) continue
            val actual = normalizeForSpeech(case.input, case.language, regex)
            if (actual != case.expected) {
                failures += "${case.id} (${case.language}): expected <${case.expected}> but was <$actual>"
            }
        }
        assertTrue("Normalize mismatches:\n" + failures.joinToString("\n"), failures.isEmpty())
    }

    @Test
    fun `chunk cases match the shared fixture and respect the limit`() {
        val fixture = loadFixture()
        assertEquals(200, fixture.maxChunkChars)
        val failures = mutableListOf<String>()
        for (case in fixture.chunkCases) {
            val actual = chunkForSpeech(case.input, fixture.maxChunkChars)
            if (actual != case.expected) {
                failures += "${case.id}: chunk lengths ${actual.map { it.length }} vs expected ${case.expected.map { it.length }}"
            }
            if (actual.any { it.length > fixture.maxChunkChars }) {
                failures += "${case.id}: a chunk exceeds ${fixture.maxChunkChars} characters"
            }
        }
        assertTrue("Chunk mismatches:\n" + failures.joinToString("\n"), failures.isEmpty())
    }

    @Test
    fun `default verse regex also speaks references and leaves chapter-only text alone`() {
        assertEquals(
            "Read John chapter 3, verse 16 today.",
            normalizeForSpeech("Read **John 3:16** today.", "en"),
        )
        assertEquals("Psalm 23 is comforting.", normalizeForSpeech("Psalm 23 is comforting.", "en"))
    }

    @Test
    fun `unknown and regional language tags fall back sensibly`() {
        val regex = verseRegex()
        assertEquals("John chapter 3, verse 16", normalizeForSpeech("John 3:16", "xx", regex))
        assertEquals("João capítulo 3, versículo 16", normalizeForSpeech("João 3:16", "pt_BR", regex))
        assertEquals("约翰福音第3章第16节", normalizeForSpeech("约翰福音 3:16", "zh-CN", regex))
    }

    @Test
    fun `chunking never splits a surrogate pair`() {
        val text = "x".repeat(199) + "😊😊😊"
        val chunks = chunkForSpeech(text, 200)
        assertEquals(text, chunks.joinToString(""))
        for (chunk in chunks) {
            assertTrue(!Character.isHighSurrogate(chunk.last()))
            assertTrue(!Character.isLowSurrogate(chunk.first()))
        }
    }

    @Test
    fun `cjkBookNamesFrom includes both Han and Hangul names so Korean references still match`() {
        val names = cjkBookNamesFrom(LOCALIZED_BOOK_TO_ENGLISH)
        assertTrue("约翰福音" in names)
        assertTrue("요한복음" in names)
        assertEquals(names.sortedByDescending { it.length }, names)
        // The production regex (as built by ChatScreen) must still find a Korean reference.
        val regex = verseRegex()
        assertTrue(regex.containsMatchIn("요한복음 3:16"))
        assertEquals(
            "요한복음 3장 16절",
            normalizeForSpeech("요한복음 3:16", "ko", regex),
        )
    }

    @Test
    fun `markup-only input yields no chunks`() {
        assertTrue(speakableChunks("---\n\n```\n", "en").isEmpty())
    }
}

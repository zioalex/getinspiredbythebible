package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithText
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.data.remote.models.ChapterResponseDto
import org.voxquieta.app.data.remote.models.ChapterVerseDto
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [VerseDetailContent] (BITB-040).
 *
 * Verifies that the verse-detail header uses the localized book name (e.g. "Esodo 30:22")
 * instead of the English canonical name ("Exodus 30:22") when [Verse.localizedBook] is set,
 * and that the chapter-section header (line 184 of VerseDetailBottomSheet.kt) does likewise.
 *
 * Mounts [VerseDetailContent] instead of [VerseDetailBottomSheet] to avoid [ModalBottomSheet]
 * rendering caveats under Robolectric — same pattern as [VersesPanelComposeTest].
 * Uses [ChapterSheetState.Error] / [ChapterSheetState.Success] (not Idle/Loading) to avoid
 * [CircularProgressIndicator]'s infinite animation keeping ComposeIdlingResource permanently
 * busy (see build.gradle.kts spinner caveat).
 */
class VerseDetailBottomSheetComposeTest : ComposeTestHarness() {

    private fun mountContent(
        verse: Verse,
        chapterState: ChapterSheetState = ChapterSheetState.Error("load failed"),
    ) = setContentThemed {
        VerseDetailContent(
            verse = verse,
            preferredTranslation = verse.translation,
            chapterState = chapterState,
            onLoadChapter = { _, _, _ -> },
        )
    }

    @Test
    fun `top header shows localized book name when localizedBook is set`() {
        mountContent(
            verse = Verse(
                book = "Exodus",
                chapter = 30,
                verse = 22,
                text = "Take the finest spices.",
                translation = "ita1927",
                localizedBook = "Esodo",
            ),
        )
        composeRule.onNodeWithText("Esodo 30:22").assertIsDisplayed()
    }

    @Test
    fun `top header shows English book name when localizedBook is null`() {
        mountContent(
            verse = Verse(
                book = "Exodus",
                chapter = 3,
                verse = 14,
                text = "I AM WHO I AM.",
                translation = "kjv",
            ),
        )
        composeRule.onNodeWithText("Exodus 3:14").assertIsDisplayed()
    }

    @Test
    fun `top header shows non-Latin localizedBook name`() {
        mountContent(
            verse = Verse(
                book = "John",
                chapter = 3,
                verse = 16,
                text = "Ибо так возлюбил Бог мир.",
                translation = "synodal",
                localizedBook = "Иоанна",
            ),
        )
        composeRule.onNodeWithText("Иоанна 3:16").assertIsDisplayed()
    }

    @Test
    fun `chapter section shows localized book header on success`() {
        val verse = Verse(
            book = "Exodus",
            chapter = 30,
            verse = 22,
            text = "Take the finest spices.",
            translation = "ita1927",
            localizedBook = "Esodo",
        )
        mountContent(
            verse = verse,
            chapterState = ChapterSheetState.Success(
                ChapterResponseDto(
                    book = "Exodus",
                    chapter = 30,
                    verses = listOf(ChapterVerseDto(verseNumber = 22, text = "Take the finest spices.")),
                    translation = "ita1927",
                    localizedBook = "Esodo",
                ),
            ),
        )
        composeRule.onNodeWithText("Esodo 30:22").assertIsDisplayed()
        composeRule.onNodeWithText("Esodo 30").assertIsDisplayed()
    }

    @Test
    fun `chapter section falls back to English book name when response localizedBook is null`() {
        val verse = Verse(
            book = "John",
            chapter = 3,
            verse = 16,
            text = "For God so loved the world.",
            translation = "kjv",
        )
        mountContent(
            verse = verse,
            chapterState = ChapterSheetState.Success(
                ChapterResponseDto(
                    book = "John",
                    chapter = 3,
                    verses = listOf(ChapterVerseDto(verseNumber = 16, text = "For God so loved the world.")),
                    translation = "kjv",
                    localizedBook = null,
                ),
            ),
        )
        composeRule.onNodeWithText("John 3:16").assertIsDisplayed()
        composeRule.onNodeWithText("John 3").assertIsDisplayed()
    }

    // ── isPlaceholderVerseText unit tests ──────────────────────────────────

    @Test
    fun `isPlaceholderVerseText returns true for null`() {
        assertTrue(isPlaceholderVerseText(null))
    }

    @Test
    fun `isPlaceholderVerseText returns true for empty string`() {
        assertTrue(isPlaceholderVerseText(""))
    }

    @Test
    fun `isPlaceholderVerseText returns true for slash placeholder`() {
        assertTrue(isPlaceholderVerseText("////"))
    }

    @Test
    fun `isPlaceholderVerseText returns true for dash placeholder`() {
        assertTrue(isPlaceholderVerseText("----"))
    }

    @Test
    fun `isPlaceholderVerseText returns true for whitespace-only string`() {
        assertTrue(isPlaceholderVerseText("   "))
    }

    @Test
    fun `isPlaceholderVerseText returns false for real Latin verse text`() {
        assertFalse(isPlaceholderVerseText("For God so loved the world"))
    }

    @Test
    fun `isPlaceholderVerseText returns false for Cyrillic verse text`() {
        assertFalse(isPlaceholderVerseText("Ибо так возлюбил Бог мир"))
    }

    @Test
    fun `verse box is shown when text is real verse text`() {
        mountContent(
            verse = Verse(
                book = "John",
                chapter = 3,
                verse = 16,
                text = "For God so loved the world.",
                translation = "kjv",
            ),
        )
        composeRule.onNodeWithText("\"For God so loved the world.\"").assertIsDisplayed()
    }
}

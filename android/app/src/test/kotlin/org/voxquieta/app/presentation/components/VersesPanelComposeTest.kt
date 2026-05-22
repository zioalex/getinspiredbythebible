package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotSelected
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.testing.ComposeTestHarness
import java.util.UUID

/**
 * Robolectric-backed Compose UI tests for [VersesPanelContent] (BITB-034).
 *
 * These run under the dedicated `testDebugCompose` Gradle task and the separate
 * `android-compose-tests.yml` workflow. They are NOT part of the required
 * `unit-tests` CI lane so they cannot block releases while the harness stabilises.
 *
 * See also: [VersesPanelDefaultsTest] — a plain JVM test that asserts
 * [DEFAULT_SHOW_REFERENCED] without needing the Compose runtime.
 */
class VersesPanelComposeTest : ComposeTestHarness() {

    private fun verse(book: String, chapter: Int, verseNum: Int) = Verse(
        book = book,
        chapter = chapter,
        verse = verseNum,
        text = "Sample text for $book $chapter:$verseNum",
        translation = "kjv",
    )

    private fun assistantMsg(content: String) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.ASSISTANT,
        content = content,
    )

    private fun mountPanel(
        allVerses: List<Verse>,
        messages: List<Message>,
    ) = setContentThemed {
        VersesPanelContent(
            allVerses = allVerses,
            messages = messages,
            chapterSheetState = ChapterSheetState.Idle,
            preferredTranslation = "kjv",
            onLoadChapter = { _, _, _ -> },
            onDismissSheet = {},
        )
    }

    // 1. Default filter is "Cited" — guards DEFAULT_SHOW_REFERENCED = true
    @Test
    fun `panel opens with Cited filter selected by default`() {
        mountPanel(
            allVerses = listOf(verse("John", 3, 16)),
            messages = listOf(assistantMsg("See John 3:16 for hope.")),
        )

        composeRule.onNodeWithText("Cited").assertIsSelected()
        composeRule.onNodeWithText("All Related (1)").assertIsNotSelected()
    }

    // 2. Empty state shown when no cited verses match
    @Test
    fun `empty state shown when no verses match the Cited filter`() {
        mountPanel(
            allVerses = listOf(verse("John", 3, 16)),
            // Assistant message does not cite any verse → Referenced list is empty
            messages = listOf(assistantMsg("Reflect on the love of God.")),
        )

        composeRule.onNodeWithText("No verses found for this filter.").assertIsDisplayed()
    }

    // 3. Clicking "All Related" reveals all backend verses
    @Test
    fun `toggling to All Related shows every verse`() {
        val john = verse("John", 3, 16)
        val psalm = verse("Psalms", 23, 1)
        mountPanel(
            allVerses = listOf(john, psalm),
            // Only John is cited; Psalms is in the backend response but not cited
            messages = listOf(assistantMsg("See John 3:16 for hope.")),
        )

        composeRule.onNodeWithText("All Related (2)").performClick()

        composeRule.onNodeWithText("All Related (2)").assertIsSelected()
        composeRule.onNodeWithText("Cited").assertIsNotSelected()
        // Both verse refs are visible in "All Related" mode
        composeRule.onNodeWithText("John 3:16").assertIsDisplayed()
        composeRule.onNodeWithText("Psalms 23:1").assertIsDisplayed()
    }

    // 4. Panel title is rendered (smoke test confirming the composable mounts)
    @Test
    fun `panel title Related Verses is displayed`() {
        mountPanel(allVerses = emptyList(), messages = emptyList())

        composeRule.onNodeWithText("Related Verses").assertIsDisplayed()
    }
}

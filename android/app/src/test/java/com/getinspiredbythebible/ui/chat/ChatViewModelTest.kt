package com.getinspiredbythebible.ui.chat

import app.cash.turbine.test
import com.getinspiredbythebible.data.model.ChatResponse
import com.getinspiredbythebible.data.model.VerseResult
import com.getinspiredbythebible.data.repository.ChatRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var chatRepository: ChatRepository
    private lateinit var viewModel: ChatViewModel

    // ── Test fixtures ─────────────────────────────────────────────────────────

    private val sampleVerse = VerseResult(
        book = "Philippians",
        chapter = 4,
        verse = 6,
        text = "Be careful for nothing; but in every thing by prayer...",
        similarity = 0.87,
    )

    private val sampleResponse = ChatResponse(
        response = "Here is some encouragement from scripture.",
        verses = listOf(sampleVerse),
        sessionId = "test-session-uuid",
    )

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        chatRepository = mockk()
        viewModel = ChatViewModel(chatRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // ── Tests ─────────────────────────────────────────────────────────────────

    @Test
    fun `initial state has empty messages, no loading, no error`() = runTest {
        val state = viewModel.uiState.value
        assertTrue(state.messages.isEmpty())
        assertFalse(state.isLoading)
        assertNull(state.errorMessage)
        assertEquals("", state.inputText)
    }

    @Test
    fun `onInputChanged updates inputText and clears errorMessage`() = runTest {
        // Arrange — put an error in state first
        viewModel.onSendMessage() // send with empty text is a no-op, but set error via mock
        viewModel.onInputChanged("I'm worried")

        val state = viewModel.uiState.value
        assertEquals("I'm worried", state.inputText)
    }

    @Test
    fun `onSendMessage with blank text does not call repository`() = runTest {
        viewModel.onInputChanged("   ")
        viewModel.onSendMessage()

        coVerify(exactly = 0) { chatRepository.sendMessage(any(), any()) }
        assertTrue(viewModel.uiState.value.messages.isEmpty())
    }

    @Test
    fun `onSendMessage adds user message immediately then shows assistant response`() = runTest {
        // Arrange
        coEvery { chatRepository.sendMessage(any(), any()) } returns Result.success(sampleResponse)

        // Act
        viewModel.onInputChanged("I'm feeling anxious")
        viewModel.onSendMessage()

        // User message should be appended and input cleared before coroutine resumes
        val stateAfterSend = viewModel.uiState.value
        assertEquals(1, stateAfterSend.messages.size)
        assertTrue(stateAfterSend.messages[0] is ChatMessage.User)
        assertEquals("", stateAfterSend.inputText)
        assertTrue(stateAfterSend.isLoading)

        // Let coroutine finish
        advanceUntilIdle()

        val finalState = viewModel.uiState.value
        assertEquals(2, finalState.messages.size)
        val assistantMsg = finalState.messages[1] as ChatMessage.Assistant
        assertEquals(sampleResponse.response, assistantMsg.text)
        assertEquals(1, assistantMsg.verses.size)
        assertEquals("Philippians", assistantMsg.verses[0].book)
        assertFalse(finalState.isLoading)
        assertEquals("test-session-uuid", finalState.sessionId)
    }

    @Test
    fun `onSendMessage sets errorMessage when repository returns failure`() = runTest {
        // Arrange
        val exception = Exception("Network error")
        coEvery { chatRepository.sendMessage(any(), any()) } returns Result.failure(exception)

        // Act
        viewModel.onInputChanged("Test message")
        viewModel.onSendMessage()
        advanceUntilIdle()

        // Assert
        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertNotNull(state.errorMessage)
        assertEquals("Network error", state.errorMessage)
    }

    @Test
    fun `onSendMessage passes sessionId on subsequent requests`() = runTest {
        // First request — returns a session ID
        coEvery { chatRepository.sendMessage(any(), isNull()) } returns
            Result.success(sampleResponse)

        viewModel.onInputChanged("First message")
        viewModel.onSendMessage()
        advanceUntilIdle()

        assertEquals("test-session-uuid", viewModel.uiState.value.sessionId)

        // Second request — should pass the stored session ID
        val secondResponse = sampleResponse.copy(response = "Second response")
        coEvery { chatRepository.sendMessage(any(), eq("test-session-uuid")) } returns
            Result.success(secondResponse)

        viewModel.onInputChanged("Second message")
        viewModel.onSendMessage()
        advanceUntilIdle()

        coVerify { chatRepository.sendMessage("Second message", "test-session-uuid") }
    }

    @Test
    fun `onErrorDismissed clears errorMessage`() = runTest {
        coEvery { chatRepository.sendMessage(any(), any()) } returns
            Result.failure(Exception("Error"))

        viewModel.onInputChanged("msg")
        viewModel.onSendMessage()
        advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.errorMessage)

        viewModel.onErrorDismissed()

        assertNull(viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `uiState flow emits loading true then false after send`() = runTest {
        coEvery { chatRepository.sendMessage(any(), any()) } returns Result.success(sampleResponse)

        viewModel.uiState.test {
            // Initial state
            val initial = awaitItem()
            assertFalse(initial.isLoading)

            viewModel.onInputChanged("hello")
            skipItems(1) // input change emission

            viewModel.onSendMessage()

            // Loading = true
            val loading = awaitItem()
            assertTrue(loading.isLoading)

            // Loading = false after response
            val done = awaitItem()
            assertFalse(done.isLoading)
            assertEquals(2, done.messages.size)

            cancelAndIgnoreRemainingEvents()
        }
    }
}

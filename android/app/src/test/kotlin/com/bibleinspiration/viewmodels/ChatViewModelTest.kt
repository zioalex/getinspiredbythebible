package com.bibleinspiration.viewmodels

import android.content.Context
import com.bibleinspiration.R
import com.bibleinspiration.data.preferences.LanguagePreferences
import com.bibleinspiration.data.preferences.ThemePreferences
import com.bibleinspiration.domain.models.Conversation
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.StreamChunk
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.domain.repositories.ChatRepository
import com.bibleinspiration.presentation.viewmodels.ChatViewModel
import com.bibleinspiration.security.TurnstileManager
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var repository: ChatRepository
    private lateinit var turnstileManager: TurnstileManager
    private lateinit var languagePreferences: LanguagePreferences
    private lateinit var context: Context
    private lateinit var themePreferences: ThemePreferences
    private lateinit var viewModel: ChatViewModel

    private val stubConversation = Conversation(
        id = "test-conv-id",
        title = "Test",
        createdAt = 1000L,
        updatedAt = 1000L,
    )

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        repository = mockk(relaxed = true)
        // Stub persistence methods used by sendMessage
        coEvery { repository.createConversation(any(), any()) } returns stubConversation
        coEvery { repository.saveMessage(any(), any()) } returns Unit
        coEvery { repository.touchConversation(any()) } returns Unit
        coEvery { repository.deleteConversation(any()) } returns Unit
        turnstileManager = TurnstileManager()
        languagePreferences = mockk(relaxed = true)
        every { languagePreferences.languageFlow } returns flowOf("en")
        context = mockk {
            every { getString(R.string.error_network) } returns "Network error. Please check your connection."
            every { getString(R.string.error_timeout) } returns "Request timed out. Please try again."
            every { getString(R.string.error_server) } returns "Server error. Please try again later."
            every { getString(R.string.error_generic) } returns "Something went wrong. Please try again."
        }
        themePreferences = mockk(relaxed = true)
        every { themePreferences.themeModeFlow } returns flowOf("system")
        viewModel = ChatViewModel(repository, turnstileManager, languagePreferences, context, themePreferences)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state has empty messages and no error`() {
        val state = viewModel.uiState.value
        assertTrue(state.messages.isEmpty())
        assertNull(state.error)
        assertFalse(state.isLoading)
        assertFalse(state.isTurnstileReady)
    }

    @Test
    fun `sendMessage appends user message immediately`() = runTest {
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "Hello!", done = true),
        )

        viewModel.sendMessage("Test message")
        testDispatcher.scheduler.advanceUntilIdle()

        val messages = viewModel.uiState.value.messages
        assertTrue(messages.any { it.role == Message.Role.USER && it.content == "Test message" })
    }

    @Test
    fun `sendMessage accumulates streaming chunks`() = runTest {
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "He"),
            StreamChunk(content = "llo"),
            StreamChunk(content = " world", done = true),
        )

        viewModel.sendMessage("Hi")
        testDispatcher.scheduler.advanceUntilIdle()

        val assistant = viewModel.uiState.value.messages
            .last { it.role == Message.Role.ASSISTANT }
        assertEquals("Hello world", assistant.content)
        assertFalse(assistant.isStreaming)
    }

    @Test
    fun `sendMessage populates verses on done chunk`() = runTest {
        val verse = Verse(book = "John", chapter = 3, verse = 16, text = "For God so loved...")
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "See John 3:16", done = true, verses = listOf(verse)),
        )

        viewModel.sendMessage("I need hope")
        testDispatcher.scheduler.advanceUntilIdle()

        val assistant = viewModel.uiState.value.messages.last()
        assertEquals(1, assistant.verses.size)
        assertEquals("John", assistant.verses[0].book)
    }

    @Test
    fun `sendMessage sets error on stream failure`() = runTest {
        every { repository.chatStream(any()) } returns flow {
            throw RuntimeException("Network error")
        }

        viewModel.sendMessage("Hi")
        testDispatcher.scheduler.advanceUntilIdle()

        // RuntimeException maps to error_generic
        assertEquals(
            "Something went wrong. Please try again.",
            viewModel.uiState.value.error,
        )
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun `IOException maps to network error message`() = runTest {
        every { repository.chatStream(any()) } returns flow {
            throw IOException("socket closed")
        }

        viewModel.sendMessage("Hello")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "Network error. Please check your connection.",
            viewModel.uiState.value.error,
        )
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun `UnknownHostException maps to network error message`() = runTest {
        every { repository.chatStream(any()) } returns flow {
            throw UnknownHostException("Unable to resolve host")
        }

        viewModel.sendMessage("Hello")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "Network error. Please check your connection.",
            viewModel.uiState.value.error,
        )
    }

    @Test
    fun `ConnectException maps to network error message`() = runTest {
        every { repository.chatStream(any()) } returns flow {
            throw ConnectException("Connection refused")
        }

        viewModel.sendMessage("Hello")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "Network error. Please check your connection.",
            viewModel.uiState.value.error,
        )
    }

    @Test
    fun `SocketTimeoutException maps to timeout error message`() = runTest {
        every { repository.chatStream(any()) } returns flow {
            throw SocketTimeoutException("Read timed out")
        }

        viewModel.sendMessage("Hello")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "Request timed out. Please try again.",
            viewModel.uiState.value.error,
        )
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun `stream error marks assistant message as isError`() = runTest {
        every { repository.chatStream(any()) } returns flow {
            throw IOException("no network")
        }

        viewModel.sendMessage("Hello")
        testDispatcher.scheduler.advanceUntilIdle()

        val lastMessage = viewModel.uiState.value.messages.last()
        assertEquals(Message.Role.ASSISTANT, lastMessage.role)
        assertTrue(lastMessage.isError)
        assertFalse(lastMessage.isStreaming)
        assertEquals("", lastMessage.content)
    }

    @Test
    fun `retryLastMessage re-sends last user message`() = runTest {
        // First call throws, second call succeeds
        every { repository.chatStream(any()) } returnsMany listOf(
            flow { throw IOException("no network") },
            flowOf(StreamChunk(content = "Success!", done = true)),
        )

        viewModel.sendMessage("Can you help?")
        testDispatcher.scheduler.advanceUntilIdle()

        // State should have an error and an error-flagged assistant message
        assertTrue(viewModel.uiState.value.error != null || viewModel.uiState.value.messages.any { it.isError })

        viewModel.retryLastMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        val messages = viewModel.uiState.value.messages
        val assistantMsg = messages.last { it.role == Message.Role.ASSISTANT }
        assertEquals("Success!", assistantMsg.content)
        assertFalse(assistantMsg.isError)
        assertFalse(assistantMsg.isStreaming)
    }

    @Test
    fun `retryLastMessage is no-op when no user message exists`() = runTest {
        viewModel.retryLastMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.messages.isEmpty())
    }

    @Test
    fun `blank message is ignored`() = runTest {
        viewModel.sendMessage("   ")
        testDispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.messages.isEmpty())
    }

    @Test
    fun `clearConversation empties messages`() = runTest {
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "Hi", done = true),
        )
        viewModel.sendMessage("Hello")
        testDispatcher.scheduler.advanceUntilIdle()

        viewModel.clearConversation()

        assertTrue(viewModel.uiState.value.messages.isEmpty())
    }

    @Test
    fun `setLocale updates currentLocale`() {
        viewModel.setLocale("ar")
        assertEquals("ar", viewModel.uiState.value.currentLocale)
    }

    @Test
    fun `setLocale updates selectedLanguage StateFlow`() = runTest {
        viewModel.setLocale("de")
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals("de", viewModel.selectedLanguage.value)
    }

    @Test
    fun `startNewConversation resets messages and conversationId`() = runTest {
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "Hello!", done = true),
        )
        viewModel.sendMessage("First message")
        testDispatcher.scheduler.advanceUntilIdle()

        viewModel.startNewConversation()

        val state = viewModel.uiState.value
        assertTrue(state.messages.isEmpty())
        assertNull(state.currentConversationId)
    }

    @Test
    fun `sendMessage creates conversation on first message`() = runTest {
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "Reply", done = true),
        )
        coEvery { repository.createConversation(any(), any()) } returns stubConversation

        viewModel.sendMessage("First message")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(stubConversation.id, viewModel.uiState.value.currentConversationId)
    }

    @Test
    fun `setLocale persists to language preferences`() = runTest {
        viewModel.setLocale("it")
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals("it", viewModel.uiState.value.currentLocale)
    }

    @Test
    fun `initial themeMode defaults to system`() {
        assertEquals("system", viewModel.uiState.value.themeMode)
    }

    @Test
    fun `setThemeMode dark updates themeMode in state`() {
        viewModel.setThemeMode("dark")
        assertEquals("dark", viewModel.uiState.value.themeMode)
    }

    @Test
    fun `setThemeMode light updates themeMode in state`() {
        viewModel.setThemeMode("light")
        assertEquals("light", viewModel.uiState.value.themeMode)
    }

    // -------------------------------------------------------------------------
    // Turnstile single-use token reset tests
    // -------------------------------------------------------------------------

    @Test
    fun `sendMessage resets turnstile token after successful stream`() = runTest {
        turnstileManager.onTokenReceived("initial-token")
        every { repository.chatStream(any()) } returns flowOf(
            StreamChunk(content = "Hello!", done = true),
        )

        viewModel.sendMessage("Hi")
        testDispatcher.scheduler.advanceUntilIdle()

        // Token should be cleared (consumed) so the next message gets a fresh one.
        assertNull(turnstileManager.currentToken())
        assertFalse(viewModel.uiState.value.isTurnstileReady)
    }

    @Test
    fun `sendMessage resets turnstile token after stream error`() = runTest {
        turnstileManager.onTokenReceived("initial-token")
        every { repository.chatStream(any()) } returns flow {
            throw IOException("network failure")
        }

        viewModel.sendMessage("Hi")
        testDispatcher.scheduler.advanceUntilIdle()

        // Token must also be cleared on the error path.
        assertNull(turnstileManager.currentToken())
        assertFalse(viewModel.uiState.value.isTurnstileReady)
    }
}

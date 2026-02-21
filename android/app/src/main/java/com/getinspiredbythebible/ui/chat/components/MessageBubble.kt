package com.getinspiredbythebible.ui.chat.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.getinspiredbythebible.data.model.VerseResult
import com.getinspiredbythebible.ui.chat.ChatMessage
import com.getinspiredbythebible.ui.theme.GetInspiredByTheBibleTheme

private val UserBubbleShape = RoundedCornerShape(
    topStart = 18.dp,
    topEnd = 4.dp,
    bottomStart = 18.dp,
    bottomEnd = 18.dp,
)

private val AssistantBubbleShape = RoundedCornerShape(
    topStart = 4.dp,
    topEnd = 18.dp,
    bottomStart = 18.dp,
    bottomEnd = 18.dp,
)

/**
 * Renders a single chat turn: either a user message bubble (right-aligned) or an AI response
 * (left-aligned) with optional verse reference cards below it.
 */
@Composable
fun MessageBubble(
    message: ChatMessage,
    modifier: Modifier = Modifier,
) {
    when (message) {
        is ChatMessage.User -> UserBubble(message = message, modifier = modifier)
        is ChatMessage.Assistant -> AssistantBubble(message = message, modifier = modifier)
    }
}

@Composable
private fun UserBubble(
    message: ChatMessage.User,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.End,
    ) {
        Surface(
            shape = UserBubbleShape,
            color = MaterialTheme.colorScheme.secondary,
            modifier = Modifier.widthIn(max = 300.dp),
        ) {
            Text(
                text = message.text,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSecondary,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
            )
        }
    }
}

@Composable
private fun AssistantBubble(
    message: ChatMessage.Assistant,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.Start,
    ) {
        Surface(
            shape = AssistantBubbleShape,
            color = MaterialTheme.colorScheme.surfaceVariant,
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Text(
                text = message.text,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
            )
        }

        if (message.verses.isNotEmpty()) {
            Spacer(modifier = Modifier.height(6.dp))
            Column(
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.widthIn(max = 320.dp),
            ) {
                message.verses.forEach { verse ->
                    VerseCard(verse = verse)
                }
            }
        }
    }
}

// ── Previews ──────────────────────────────────────────────────────────────────

@Preview(showBackground = true)
@Composable
private fun UserBubblePreview() {
    GetInspiredByTheBibleTheme {
        MessageBubble(
            message = ChatMessage.User(id = 0, text = "I'm feeling anxious about my future."),
            modifier = Modifier.padding(8.dp),
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun AssistantBubblePreview() {
    GetInspiredByTheBibleTheme {
        MessageBubble(
            message = ChatMessage.Assistant(
                id = 1,
                text = "It's natural to feel anxious, but God's word reminds us to cast all our " +
                    "anxieties on Him. Here are some verses that may bring you comfort:",
                verses = listOf(
                    VerseResult(
                        book = "Philippians",
                        chapter = 4,
                        verse = 6,
                        text = "Be careful for nothing; but in every thing by prayer...",
                        similarity = 0.87,
                    ),
                ),
            ),
            modifier = Modifier.padding(8.dp),
        )
    }
}

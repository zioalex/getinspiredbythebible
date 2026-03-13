package com.bibleinspiration.presentation.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.outlined.ThumbDown
import androidx.compose.material.icons.outlined.ThumbUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.app.ShareCompat
import com.bibleinspiration.R
import com.bibleinspiration.domain.models.FeedbackRating
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.presentation.viewmodels.ChapterSheetState
import dev.jeziellago.compose.markdowntext.MarkdownText

@Composable
fun ChatMessageItem(
    message: Message,
    chapterSheetState: ChapterSheetState,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismissSheet: () -> Unit,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null,
    onFeedback: ((messageId: String, rating: FeedbackRating) -> Unit)? = null,
) {
    val isUser = message.role == Message.Role.USER
    val arrangement = if (isUser) Arrangement.End else Arrangement.Start
    val bubbleColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.surfaceVariant
    }
    val textColor = if (isUser) {
        MaterialTheme.colorScheme.onPrimary
    } else {
        MaterialTheme.colorScheme.onSurfaceVariant
    }

    // Show the retry button when:
    //  - this is an assistant message
    //  - it is NOT currently streaming
    //  - it was flagged as an error (blank content + error flag)
    val showRetry = !isUser && !message.isStreaming && message.isError

    // Show the share button only for finished (non-streaming) assistant messages with content.
    val showShare = !isUser && !message.isStreaming && !message.isError && message.content.isNotBlank()

    // Show feedback buttons only when:
    //  - it's a finished (non-streaming, non-error) assistant message with content
    //  - the message has a backend-assigned messageId (can't link feedback without it)
    //  - the onFeedback callback is wired (non-null)
    val showFeedback = showShare && message.messageId.isNotBlank() && onFeedback != null

    val context = LocalContext.current

    // Blinking cursor alpha — always created to respect Composable call order.
    // The value is only read inside the streaming branch (case b), but the
    // rememberInfiniteTransition + animateFloat calls must remain unconditional
    // so the Compose runtime can track them across recompositions.
    val infiniteTransition = rememberInfiniteTransition(label = "cursor_blink")
    val cursorAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 500),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "cursor_alpha",
    )

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = arrangement,
    ) {
        Column(
            modifier = Modifier.widthIn(max = 320.dp),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start,
        ) {
            if (!showRetry) {
                Box(
                    modifier = Modifier
                        .background(
                            color = bubbleColor,
                            shape = RoundedCornerShape(
                                topStart = 16.dp,
                                topEnd = 16.dp,
                                bottomStart = if (isUser) 16.dp else 4.dp,
                                bottomEnd = if (isUser) 4.dp else 16.dp,
                            ),
                        )
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                ) {
                    when {
                        // (a) Waiting for the first chunk — show animated typing dots
                        !isUser && message.isStreaming && message.content.isEmpty() -> {
                            TypingIndicator()
                        }

                        // (b) Streaming with partial content — show text + blinking cursor
                        !isUser && message.isStreaming && message.content.isNotEmpty() -> {
                            Row(verticalAlignment = Alignment.Bottom) {
                                Text(
                                    text = message.content,
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = textColor,
                                )
                                Text(
                                    text = "▌",
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = textColor,
                                    modifier = Modifier.alpha(cursorAlpha),
                                )
                            }
                        }

                        // (c) Finished assistant message — render as Markdown.
                        // Use the non-deprecated MarkdownText overload: pass color via style.
                        !isUser -> {
                            val bodyMedium = MaterialTheme.typography.bodyMedium
                            MarkdownText(
                                markdown = message.content,
                                style = bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
                            )
                        }

                        // (d) User message — plain text bubble
                        else -> {
                            Text(
                                text = message.content,
                                style = MaterialTheme.typography.bodyLarge,
                                color = textColor,
                            )
                        }
                    }
                }
            }

            // Share button + feedback buttons — shown below finished assistant message bubbles.
            if (showShare) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    // Share button
                    IconButton(
                        onClick = {
                            ShareCompat.IntentBuilder(context)
                                .setType("text/plain")
                                .setText(message.content)
                                .startChooser()
                        },
                    ) {
                        Icon(
                            imageVector = Icons.Default.Share,
                            contentDescription = stringResource(R.string.action_share_message),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    // Feedback buttons — only when messageId is available
                    if (showFeedback) {
                        val feedbackGiven = message.feedbackRating != null

                        // 👍 Thumbs-up button
                        IconButton(
                            onClick = { onFeedback!!(message.messageId, FeedbackRating.POSITIVE) },
                            enabled = !feedbackGiven,
                        ) {
                            Icon(
                                imageVector = if (message.feedbackRating == FeedbackRating.POSITIVE) {
                                    Icons.Filled.ThumbUp
                                } else {
                                    Icons.Outlined.ThumbUp
                                },
                                contentDescription = stringResource(R.string.action_feedback_positive),
                                tint = if (message.feedbackRating == FeedbackRating.POSITIVE) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                },
                            )
                        }

                        // 👎 Thumbs-down button
                        IconButton(
                            onClick = { onFeedback!!(message.messageId, FeedbackRating.NEGATIVE) },
                            enabled = !feedbackGiven,
                        ) {
                            Icon(
                                imageVector = if (message.feedbackRating == FeedbackRating.NEGATIVE) {
                                    Icons.Filled.ThumbDown
                                } else {
                                    Icons.Outlined.ThumbDown
                                },
                                contentDescription = stringResource(R.string.action_feedback_negative),
                                tint = if (message.feedbackRating == FeedbackRating.NEGATIVE) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                },
                            )
                        }
                    }
                }
            }

            // Inline Retry button for error assistant messages
            if (showRetry && onRetry != null) {
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedButton(
                    onClick = onRetry,
                ) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.padding(end = 4.dp),
                    )
                    Text(text = stringResource(R.string.action_retry))
                }
            }

            // Show verse references below assistant messages
            if (!isUser && message.verses.isNotEmpty()) {
                Column(
                    modifier = Modifier.padding(top = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    message.verses.forEach { verse ->
                        VerseChip(
                            verse = verse,
                            preferredTranslation = preferredTranslation,
                            chapterState = chapterSheetState,
                            onLoadChapter = onLoadChapter,
                            onDismissSheet = onDismissSheet,
                        )
                    }
                }
            }
        }
    }
}

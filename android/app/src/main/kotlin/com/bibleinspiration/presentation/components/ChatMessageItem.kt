package com.bibleinspiration.presentation.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material3.LocalContentColor
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
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.presentation.viewmodels.ChapterSheetState
import dev.jeziellago.compose.markdowntext.MarkdownText
import java.net.URLDecoder
import java.net.URLEncoder

/**
 * Regex matching standalone Bible verse references in message text.
 * Captures: group 1 = book name, group 2 = chapter number, group 3 = verse (may include range).
 *
 * Examples matched: "John 3:16", "1 Corinthians 13:4", "Song of Solomon 2:1", "Rev 22:21-22"
 *
 * We exclude references already inside a markdown link by checking the character before the
 * match in the replace lambda (if preceded by '[', the ref is already a link display text).
 */
private val VERSE_REF_REGEX = Regex(
    // Optional numeric prefix: "1 ", "2 ", "3 "
    "((?:[1-3]\\s)?" +
        // Book name: one or two capitalised words
        "[A-Z][a-zA-Z]+(?:\\s[A-Z][a-zA-Z]+)*)\\s" +
        // Chapter:verse (with optional verse range)
        "(\\d+):(\\d+(?:-\\d+)?)\\b",
)

private const val VERSE_SCHEME = "verse://"

/**
 * Rewrites verse references in [markdown] as markdown links using the `verse://` scheme.
 *
 * E.g. "John 3:16" → "[John 3:16](verse://John/3/16)"
 *
 * The book name is URL-encoded so that spaces survive the round-trip through the Markwon
 * link renderer.  References already inside a markdown link (e.g. `[John 3:16](verse://…)`)
 * are left unchanged by checking that the character before the match is not `[`.
 */
internal fun injectVerseLinks(markdown: String): String =
    VERSE_REF_REGEX.replace(markdown) { result ->
        // If the match is immediately preceded by '[', it is already the display text of a
        // markdown link — skip it to avoid double-wrapping.
        val before = if (result.range.first > 0) markdown[result.range.first - 1] else '\u0000'
        if (before == '[') {
            result.value
        } else {
            val book = result.groupValues[1]
            val chapter = result.groupValues[2]
            val verse = result.groupValues[3]
            val encodedBook = URLEncoder.encode(book, "UTF-8")
            val display = "$book $chapter:$verse"
            "[$display]($VERSE_SCHEME$encodedBook/$chapter/$verse)"
        }
    }

/**
 * Parses a `verse://` URL and calls [onLoadChapter] if the URL is well-formed.
 *
 * URL format: `verse://<encoded-book>/<chapter>/<verse>`
 */
internal fun handleVerseLink(
    url: String,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
) {
    if (!url.startsWith(VERSE_SCHEME)) return
    val path = url.removePrefix(VERSE_SCHEME)
    val parts = path.split("/")
    if (parts.size < 2) return
    val book = runCatching { URLDecoder.decode(parts[0], "UTF-8") }.getOrNull() ?: return
    val chapter = parts[1].toIntOrNull() ?: return
    onLoadChapter(book, chapter, preferredTranslation)
}

@Composable
fun ChatMessageItem(
    message: Message,
    chapterSheetState: ChapterSheetState,
    preferredTranslation: String?,
    onLoadChapter: (book: String, chapter: Int, translation: String?) -> Unit,
    onDismissSheet: () -> Unit,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null,
    onFeedback: ((messageLocalId: String, rating: String) -> Unit)? = null,
    feedbackGiven: String? = null,
) {
    val isUser = message.role == Message.Role.USER
    val arrangement = if (isUser) Arrangement.End else Arrangement.Start

    // User bubble: primary colour (matches web's bg-primary-600 for user messages)
    // Assistant bubble: white surface with a subtle border (matches web's bg-white border)
    val bubbleColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.surface
    }
    val textColor = if (isUser) {
        MaterialTheme.colorScheme.onPrimary
    } else {
        MaterialTheme.colorScheme.onSurface
    }

    // Show the retry button when:
    //  - this is an assistant message
    //  - it is NOT currently streaming
    //  - it was flagged as an error (blank content + error flag)
    val showRetry = !isUser && !message.isStreaming && message.isError

    // Show the share button only for finished (non-streaming) assistant messages with content.
    val showShare = !isUser && !message.isStreaming && !message.isError && message.content.isNotBlank()

    val context = LocalContext.current

    // Blinking cursor alpha — always created to respect Composable call order.
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
                val bubbleModifier = if (isUser) {
                    // User bubble: filled primary, no border
                    Modifier
                        .background(
                            color = bubbleColor,
                            shape = RoundedCornerShape(
                                topStart = 18.dp,
                                topEnd = 18.dp,
                                bottomStart = 18.dp,
                                bottomEnd = 4.dp,
                            ),
                        )
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                } else {
                    // Assistant bubble: white surface with primary border — matches web card style
                    Modifier
                        .background(
                            color = bubbleColor,
                            shape = RoundedCornerShape(
                                topStart = 4.dp,
                                topEnd = 18.dp,
                                bottomStart = 18.dp,
                                bottomEnd = 18.dp,
                            ),
                        )
                        .border(
                            width = 1.dp,
                            color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                            shape = RoundedCornerShape(
                                topStart = 4.dp,
                                topEnd = 18.dp,
                                bottomStart = 18.dp,
                                bottomEnd = 18.dp,
                            ),
                        )
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                }

                Box(modifier = bubbleModifier) {
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

                        // (c) Finished assistant message — render as Markdown with tappable verse refs.
                        !isUser -> {
                            val bodyMedium = MaterialTheme.typography.bodyMedium
                            // Amber colour for verse links — matches web's amber-600 link colour
                            val amberColor = MaterialTheme.colorScheme.tertiary
                            MarkdownText(
                                markdown = injectVerseLinks(message.content),
                                style = bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
                                linkColor = amberColor,
                                onLinkClicked = { url ->
                                    handleVerseLink(url, preferredTranslation, onLoadChapter)
                                },
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

            // Share button — shown below finished assistant message bubbles.
            if (showShare) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                ) {
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
                }
            }

            // Feedback buttons — only for finished assistant messages with a backend message_id.
            if (message.role == Message.Role.ASSISTANT
                && !message.isStreaming
                && message.messageId.isNotBlank()
                && onFeedback != null
            ) {
                val alreadyVoted = feedbackGiven != null

                IconButton(
                    onClick = { if (!alreadyVoted) onFeedback(message.id, "positive") },
                    enabled = !alreadyVoted,
                ) {
                    Icon(
                        imageVector = if (feedbackGiven == "positive") Icons.Filled.ThumbUp else Icons.Outlined.ThumbUp,
                        contentDescription = stringResource(R.string.action_feedback_helpful),
                        tint = if (feedbackGiven == "positive") MaterialTheme.colorScheme.primary else LocalContentColor.current,
                    )
                }
                IconButton(
                    onClick = { if (!alreadyVoted) onFeedback(message.id, "negative") },
                    enabled = !alreadyVoted,
                ) {
                    Icon(
                        imageVector = if (feedbackGiven == "negative") Icons.Filled.ThumbDown else Icons.Outlined.ThumbDown,
                        contentDescription = stringResource(R.string.action_feedback_not_helpful),
                        tint = if (feedbackGiven == "negative") MaterialTheme.colorScheme.error else LocalContentColor.current,
                    )
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

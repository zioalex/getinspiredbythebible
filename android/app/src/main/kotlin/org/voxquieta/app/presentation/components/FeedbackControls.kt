package org.voxquieta.app.presentation.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.outlined.ThumbDown
import androidx.compose.material.icons.outlined.ThumbUp
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntRect
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupPositionProvider
import androidx.compose.ui.window.PopupProperties
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.voxquieta.app.R

/**
 * Length of the "rethink" window after a thumb is tapped, before the rating is
 * actually sent. Single named constant so it is easy to tune. Mirrors the web's
 * `FEEDBACK_RETHINK_MS`.
 */
const val FEEDBACK_RETHINK_MS = 10_000L

/**
 * Inline, non-blocking feedback controls — Android parity with the web.
 *
 * Tapping a thumb does not send immediately: the choice is shown as *pending*
 * with a quiet progress bar and an Undo for ~10s ([FEEDBACK_RETHINK_MS]). When
 * it elapses the rating is sent. Opening the optional comment pauses the
 * countdown and shows an explicit Send, so there is exactly one request per
 * rating — never a "rating now, comment later" double-send. On thumbs-down a
 * short notice states the message will be shared with the app's maintainer.
 *
 * The commit is driven by [delay], not by the bar animation, so it is unaffected
 * by the system "remove animations" setting (which would otherwise complete a
 * Compose animation instantly and skip the rethink window).
 *
 * The pending affordance renders in a [Popup] floating **above** the thumbs (see
 * [FeedbackPendingPanel] + [AbovePopupPositionProvider]) so it is visible the
 * instant a thumb is tapped — it does not push chat content down or land below
 * the fold for the last message in the list.
 *
 * @param feedbackGiven Rating already recorded for this message ("positive" /
 *   "negative"), or null. Locks the controls once set.
 * @param onSubmit Called exactly once per rating, with the trimmed comment.
 * @param trailing Rendered at the trailing edge of the thumbs row (copy/share).
 */
@Composable
fun FeedbackControls(
    feedbackGiven: String?,
    onSubmit: (rating: String, comment: String) -> Unit,
    modifier: Modifier = Modifier,
    trailing: @Composable RowScope.() -> Unit = {},
) {
    var pending by remember { mutableStateOf<String?>(null) }
    var comment by remember { mutableStateOf("") }
    var commentOpen by remember { mutableStateOf(false) }
    var localGiven by remember { mutableStateOf<String?>(null) }
    var committed by remember { mutableStateOf(false) }

    // The recorded rating drives the final UI; until the parent confirms we show
    // an optimistic local copy so the "thanks" state appears instantly.
    val effectiveGiven = feedbackGiven ?: localGiven

    val progress = remember { Animatable(1f) }

    fun doCommit(rating: String, text: String) {
        if (committed) return
        committed = true
        localGiven = rating
        pending = null
        commentOpen = false
        onSubmit(rating, text.trim())
    }

    fun startPending(rating: String) {
        committed = false
        comment = ""
        commentOpen = false
        pending = rating
    }

    fun cancel() {
        pending = null
        comment = ""
        commentOpen = false
    }

    // Countdown → commit. Re-keys on (pending, commentOpen): undo/switch/open-comment
    // cancel the previous coroutine, so no stray commit fires.
    LaunchedEffect(pending, commentOpen) {
        val rating = pending
        if (rating != null && !commentOpen) {
            progress.snapTo(1f)
            val animJob = launch {
                progress.animateTo(
                    targetValue = 0f,
                    animationSpec = tween(
                        durationMillis = FEEDBACK_RETHINK_MS.toInt(),
                        easing = LinearEasing,
                    ),
                )
            }
            delay(FEEDBACK_RETHINK_MS)
            animJob.cancel()
            doCommit(rating, "")
        }
    }

    val spacingPx = with(LocalDensity.current) { 4.dp.roundToPx() }
    val positionProvider = remember(spacingPx) { AbovePopupPositionProvider(spacingPx) }

    Column(modifier = modifier.fillMaxWidth()) {
        // The thumbs Row is the Popup's anchor: the popover positions itself
        // relative to this Box's bounds in the window.
        Box {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                val locked = effectiveGiven != null
                val upActive = effectiveGiven == "positive" || pending == "positive"
                val downActive = effectiveGiven == "negative" || pending == "negative"

                IconButton(
                    onClick = { if (!locked) if (pending == "positive") cancel() else startPending("positive") },
                    enabled = !locked,
                ) {
                    Icon(
                        imageVector = if (upActive) Icons.Filled.ThumbUp else Icons.Outlined.ThumbUp,
                        contentDescription = stringResource(R.string.action_feedback_helpful),
                        tint = if (upActive) MaterialTheme.colorScheme.primary else LocalContentColor.current,
                    )
                }
                IconButton(
                    onClick = { if (!locked) if (pending == "negative") cancel() else startPending("negative") },
                    enabled = !locked,
                ) {
                    Icon(
                        imageVector = if (downActive) Icons.Filled.ThumbDown else Icons.Outlined.ThumbDown,
                        contentDescription = stringResource(R.string.action_feedback_not_helpful),
                        tint = if (downActive) MaterialTheme.colorScheme.error else LocalContentColor.current,
                    )
                }
                if (effectiveGiven != null) {
                    Text(
                        text = stringResource(R.string.feedback_thanks),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                trailing()
            }

            val pendingRating = pending
            if (pendingRating != null && effectiveGiven == null) {
                Popup(
                    popupPositionProvider = positionProvider,
                    // Tap-outside / back press is a non-destructive cancel: nothing
                    // is sent and the countdown coroutine is torn down cleanly.
                    onDismissRequest = { cancel() },
                    // Focusable so the comment OutlinedTextField can receive the keyboard.
                    properties = PopupProperties(focusable = true),
                ) {
                    Surface(
                        modifier = Modifier.width(320.dp),
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.surface,
                        tonalElevation = 3.dp,
                        shadowElevation = 6.dp,
                    ) {
                        FeedbackPendingPanel(
                            rating = pendingRating,
                            comment = comment,
                            commentOpen = commentOpen,
                            progress = { progress.value },
                            onOpenComment = { commentOpen = true },
                            onCommentChange = { comment = it },
                            onUndo = { cancel() },
                            onSend = { doCommit(pendingRating, comment) },
                        )
                    }
                }
            }
        }
    }
}

/**
 * Stateless content of the pending-feedback affordance: maintainer notice (on
 * thumbs-down), the quiet progress bar with Undo / Add-comment, and the optional
 * comment field with Send. Hoisted out of [FeedbackControls] so it can be mounted
 * and asserted directly in Robolectric tests — `Popup` content is unreliable
 * under Robolectric (see `COMPOSE_TESTS.md`), so behaviour is tested here, on the
 * content composable, rather than through the popover wrapper.
 */
@Composable
internal fun FeedbackPendingPanel(
    rating: String,
    comment: String,
    commentOpen: Boolean,
    progress: () -> Float,
    onOpenComment: () -> Unit,
    onCommentChange: (String) -> Unit,
    onUndo: () -> Unit,
    onSend: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.padding(12.dp)) {
        // Maintainer-sharing notice is always shown on thumbs-down, even before a
        // comment is written.
        if (rating == "negative") {
            Row(verticalAlignment = Alignment.Top) {
                Icon(
                    imageVector = Icons.Filled.Info,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.tertiary,
                    modifier = Modifier.size(16.dp),
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = stringResource(R.string.feedback_maintainer_notice),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
        }

        if (!commentOpen) {
            val sendingDesc = stringResource(R.string.feedback_sending)
            Row(verticalAlignment = Alignment.CenterVertically) {
                LinearProgressIndicator(
                    progress = progress,
                    modifier = Modifier
                        .weight(1f)
                        .semantics { contentDescription = sendingDesc },
                )
                TextButton(onClick = onOpenComment) {
                    Text(stringResource(R.string.feedback_add_comment))
                }
                TextButton(onClick = onUndo) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.Undo,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(stringResource(R.string.feedback_undo))
                }
            }
        } else {
            OutlinedTextField(
                value = comment,
                onValueChange = onCommentChange,
                placeholder = { Text(stringResource(R.string.feedback_comment_hint)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = onUndo) {
                    Text(stringResource(R.string.feedback_undo))
                }
                Spacer(modifier = Modifier.width(8.dp))
                Button(onClick = onSend) {
                    Text(stringResource(R.string.feedback_send))
                }
            }
        }
    }
}

/**
 * Positions a [Popup] just **above** its anchor (the thumbs row), left-aligned and
 * clamped within the window. Falls back to below the anchor when there isn't room
 * above; in the pathological case where neither fits, pins to the top edge so the
 * controls stay reachable. Opening above also keeps the panel clear of the
 * on-screen keyboard when the comment field is focused.
 *
 * LTR left-alignment; [spacingPx] is the gap between the anchor and the popover.
 */
private class AbovePopupPositionProvider(
    private val spacingPx: Int,
) : PopupPositionProvider {
    override fun calculatePosition(
        anchorBounds: IntRect,
        windowSize: IntSize,
        layoutDirection: LayoutDirection,
        popupContentSize: IntSize,
    ): IntOffset {
        val maxX = (windowSize.width - popupContentSize.width).coerceAtLeast(0)
        val x = anchorBounds.left.coerceIn(0, maxX)

        val above = anchorBounds.top - popupContentSize.height - spacingPx
        val below = anchorBounds.bottom + spacingPx
        val y = when {
            above >= 0 -> above
            below + popupContentSize.height <= windowSize.height -> below
            else -> above.coerceAtLeast(0)
        }
        return IntOffset(x, y)
    }
}

package org.voxquieta.app.presentation.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
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

    Column(modifier = modifier.fillMaxWidth()) {
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

        if (pending != null && effectiveGiven == null) {
            Spacer(modifier = Modifier.height(4.dp))
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                        shape = RoundedCornerShape(12.dp),
                    )
                    .padding(12.dp),
            ) {
                // Maintainer-sharing notice is always shown on thumbs-down, even
                // before a comment is written.
                if (pending == "negative") {
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
                            progress = { progress.value },
                            modifier = Modifier
                                .weight(1f)
                                .semantics { contentDescription = sendingDesc },
                        )
                        TextButton(onClick = { commentOpen = true }) {
                            Text(stringResource(R.string.feedback_add_comment))
                        }
                        TextButton(onClick = { cancel() }) {
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
                        onValueChange = { comment = it },
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
                        TextButton(onClick = { cancel() }) {
                            Text(stringResource(R.string.feedback_undo))
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(onClick = { pending?.let { doCommit(it, comment) } }) {
                            Text(stringResource(R.string.feedback_send))
                        }
                    }
                }
            }
        }
    }
}

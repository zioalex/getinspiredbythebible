package org.voxquieta.app.presentation.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp

/**
 * Animated 3-dot typing indicator used while the assistant is preparing its first chunk.
 *
 * Each dot performs a vertical "wave" bounce with a 150 ms stagger between dots,
 * giving a natural left-to-right ripple effect.
 */
@Composable
fun TypingIndicator(modifier: Modifier = Modifier) {
    val infiniteTransition = rememberInfiniteTransition(label = "typing_indicator")

    val totalDuration = 900 // ms for a full bounce cycle per dot

    // Animate three independent fractions with staggered delays.
    val fraction0 by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = totalDuration, delayMillis = 0, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "dot0",
    )
    val fraction1 by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = totalDuration, delayMillis = 150, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "dot1",
    )
    val fraction2 by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = totalDuration, delayMillis = 300, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "dot2",
    )

    val fractions = listOf(fraction0, fraction1, fraction2)

    Row(
        modifier = modifier.padding(horizontal = 4.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        fractions.forEach { fraction ->
            // Map the 0→1 fraction to a vertical translation using a sine wave:
            // - First half of the cycle (0→0.5): bounce up by 6dp and back
            // - Second half (0.5→1): rest at baseline (gives a "bounce then pause" feel)
            val translationYDp = if (fraction < 0.5f) {
                val angle = (fraction / 0.5f * Math.PI).toFloat() // 0 → π
                -kotlin.math.sin(angle) * 6f // 0 → -6 → 0  (dp)
            } else {
                0f
            }

            Box(
                modifier = Modifier
                    .size(8.dp)
                    .graphicsLayer { translationY = translationYDp.dp.toPx() }
                    .background(
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        shape = CircleShape,
                    ),
            )
        }
    }
}

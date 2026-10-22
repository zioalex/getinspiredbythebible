package org.voxquieta.app.presentation.components

import android.graphics.Rect as AndroidRect
import androidx.compose.foundation.background
import androidx.compose.foundation.canvas.Canvas
import androidx.compose.foundation.canvas.drawPath
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathOperation
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.offset
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.voxquieta.app.R

/**
 * Shape of the spotlight highlight cutout.
 */
sealed class SpotlightShape {
    data class RoundedRect(val cornerRadius: Float) : SpotlightShape()
    object Circle : SpotlightShape()
}

/**
 * Target for a single spotlight step.
 *
 * @param bounds The bounds of the target element in window coordinates (Compose Rect).
 * @param captionRes String resource ID for the caption text.
 * @param autoOpenDrawer Optional callback to open the drawer for step 0 (drawer icon).
 * @param shape The shape of the highlight cutout.
 */
data class SpotlightTarget(
    val bounds: Rect,
    val captionRes: Int,
    val autoOpenDrawer: (() -> Unit)? = null,
    val shape: SpotlightShape = SpotlightShape.RoundedRect(12f) // ~8dp on mdpi
)

/**
 * Composable overlay that renders a coach-mark / feature spotlight tour.
 *
 * Shows a full-screen scrim with a cutout highlighting the current target,
 * a caption with step number, and Next/Skip/Done controls.
 *
 * @param targets List of [SpotlightTarget] in order (typically 4).
 * @param onComplete Called when Done/Skip tapped or last step Next.
 * @param onStepChange Called when the step changes (for auto-open drawer on step 0).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeatureSpotlight(
    targets: List<SpotlightTarget>,
    onComplete: () -> Unit,
    onStepChange: (Int) -> Unit = {},
) {
    require(targets.isNotEmpty()) { "FeatureSpotlight requires at least one target" }

    var currentStep by remember { mutableStateOf(0) }
    var isDrawerOpen by remember { mutableStateOf(false) }

    val currentTarget = targets[currentStep]

    // Auto-open drawer on step 0 when step changes to 0
    LaunchedEffect(currentStep) {
        if (currentStep == 0 && !isDrawerOpen) {
            currentTarget.autoOpenDrawer?.invoke()
            isDrawerOpen = true
        } else if (currentStep > 0 && isDrawerOpen) {
            isDrawerOpen = false
        }
        onStepChange(currentStep)
    }

    val scrimColor = MaterialTheme.colorScheme.surfaceContainerHighest.copy(alpha = 0.92f)
    val captionBackgroundColor = MaterialTheme.colorScheme.surfaceContainer
    val buttonColor = MaterialTheme.colorScheme.primaryContainer
    val buttonContentColor = MaterialTheme.colorScheme.onPrimaryContainer

    Box(
        modifier = Modifier.fillMaxSize(),
    ) {
        // Full-screen scrim with cutout
        Canvas(modifier = Modifier.fillMaxSize()) {
            val width = size.width
            val height = size.height
            val density = LocalDensity.current

            // Create the full screen rect
            val screenPath = Path().apply { addRect(Rect(0f, 0f, width, height)) }

            // Create the highlight cutout path based on target bounds and shape
            val highlightPath = Path()
            val bounds = currentTarget.bounds
            val left = bounds.left
            val top = bounds.top
            val right = bounds.right
            val bottom = bounds.bottom

            when (currentTarget.shape) {
                is SpotlightShape.RoundedRect -> {
                    val cornerRadius = currentTarget.shape.cornerRadius
                    val roundRect = RoundRect(
                        left = left,
                        top = top,
                        right = right,
                        bottom = bottom,
                        cornerRadius = CornerRadius(cornerRadius, cornerRadius)
                    )
                    highlightPath.addRoundRect(roundRect, Path.Direction.CW)
                }
                SpotlightShape.Circle -> {
                    val centerX = (left + right) / 2f
                    val centerY = (top + bottom) / 2f
                    val radius = maxOf(right - left, bottom - top) / 2f + 12f // ~8dp
                    highlightPath.addCircle(centerX, centerY, radius, Path.Direction.CW)
                }
            }

            // Cut out the highlight area from the scrim
            val scrimPath = Path()
            scrimPath.op(screenPath, highlightPath, PathOperation.Difference)

            drawPath(
                path = scrimPath,
                color = scrimColor,
            )
        }

        // Caption card positioned near the highlight
        CaptionCard(
            target = currentTarget,
            stepNumber = currentStep + 1,
            totalSteps = targets.size,
            captionBackgroundColor = captionBackgroundColor,
        )

        // Controls at bottom
        ControlsBar(
            currentStep = currentStep,
            totalSteps = targets.size,
            onNext = {
                if (currentStep < targets.size - 1) {
                    currentStep++
                } else {
                    onComplete()
                }
            },
            onSkip = onComplete,
            onDone = onComplete,
            buttonColor = buttonColor,
            buttonContentColor = buttonContentColor,
        )
    }
}

/**
 * Caption card showing the step number and description.
 * Positioned above or below the highlight cutout depending on available space.
 */
@Composable
private fun CaptionCard(
    target: SpotlightTarget,
    stepNumber: Int,
    totalSteps: Int,
    captionBackgroundColor: Color,
) {
    val bounds = target.bounds
    val screenHeight = LocalConfiguration.current.screenHeightDp.dp
    val screenWidth = LocalConfiguration.current.screenWidthDp.dp
    val density = LocalDensity.current

    // Decide whether to show caption above or below the highlight
    val highlightCenterY = (bounds.top + bounds.bottom) / 2f
    val showAbove = highlightCenterY > density.run { screenHeight.toPx() } * 0.6f

    val captionX = ((bounds.left + bounds.right) / 2f).coerceIn(
        density.run { 24.dp.toPx() },
        density.run { screenWidth.toPx() } - density.run { 24.dp.toPx() } - density.run { 280.dp.toPx() }, // approximate card width
    )

    val captionY = if (showAbove) {
        bounds.top - density.run { 160.dp.toPx() } // card height + margin
    } else {
        bounds.bottom + density.run { 16.dp.toPx() }
    }.coerceIn(
        density.run { 24.dp.toPx() },
        density.run { screenHeight.toPx() } - density.run { 24.dp.toPx() } - density.run { 140.dp.toPx() },
    )

    Box(
        modifier = Modifier.fillMaxSize(),
    ) {
        Card(
            modifier = Modifier
                .offset(x = captionX.dp, y = captionY.dp)
                .width(280.dp)
                .padding(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = captionBackgroundColor,
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
            shape = RoundedCornerShape(16.dp),
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                // Step indicator
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = stringResource(R.string.tour_step_indicator, stepNumber, totalSteps),
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(Modifier.weight(1f))
                    Text(
                        text = stringResource(R.string.tour_title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                    )
                }

                // Caption text
                Text(
                    text = stringResource(target.captionRes),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}

/**
 * Bottom controls bar with Next/Skip/Done buttons.
 */
@Composable
private fun ControlsBar(
    currentStep: Int,
    totalSteps: Int,
    onNext: () -> Unit,
    onSkip: () -> Unit,
    onDone: () -> Unit,
    buttonColor: Color,
    buttonContentColor: Color,
) {
    val isLastStep = currentStep == totalSteps - 1

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp)
            .padding(bottom = 32.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .align(Alignment.BottomCenter),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Skip button (only on non-last steps)
            if (!isLastStep) {
                TextButton(
                    onClick = onSkip,
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                ) {
                    Text(
                        text = stringResource(R.string.tour_skip),
                        style = MaterialTheme.typography.labelLarge,
                    )
                }
            } else {
                Spacer(Modifier.width(0.dp))
            }

            // Next / Done button
            Button(
                onClick = if (isLastStep) onDone else onNext,
                colors = ButtonDefaults.buttonColors(
                    containerColor = buttonColor,
                    contentColor = buttonContentColor,
                ),
            ) {
                Text(
                    text = stringResource(if (isLastStep) R.string.tour_done else R.string.tour_next),
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
    }
}

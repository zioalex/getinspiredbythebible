package com.bibleinspiration.presentation.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.absoluteOffset
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bibleinspiration.R
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class SplashPhrase(
    val text: String,
    val isRtl: Boolean = false,
    /** Fraction of screen height (0f–1f) */
    val topFraction: Float,
    /** Fraction of screen width from the left edge; -1 means use rightFraction */
    val leftFraction: Float = -1f,
    /** Fraction of screen width from the right edge; used when leftFraction == -1 */
    val rightFraction: Float = -1f,
    /** Maximum width as fraction of screen width */
    val maxWidthFraction: Float = 0.45f,
    val targetAlpha: Float = 0.70f,
    val floatDurationMs: Int = 3500,
    val floatDelayMs: Long = 0L,
    val staggerDelayMs: Long = 0L,
    val fontSize: Int = 12,
)

private val PHRASES = listOf(
    SplashPhrase("What does the Bible say about love?",       topFraction = 0.07f, leftFraction  = 0.04f,  maxWidthFraction = 0.50f, targetAlpha = 0.75f, floatDurationMs = 4000, floatDelayMs =    0, staggerDelayMs =    0, fontSize = 13),
    SplashPhrase("Cosa dice la Bibbia sul perdono?",          topFraction = 0.12f, leftFraction  = 0.28f,  maxWidthFraction = 0.40f, targetAlpha = 0.60f, floatDurationMs = 3500, floatDelayMs =  600, staggerDelayMs =  150, fontSize = 12),
    SplashPhrase("¿Qué dice la Biblia sobre la esperanza?",  topFraction = 0.08f, rightFraction = 0.04f,  maxWidthFraction = 0.48f, targetAlpha = 0.70f, floatDurationMs = 4800, floatDelayMs = 1100, staggerDelayMs =  300, fontSize = 13),
    SplashPhrase("Was sagt die Bibel über Frieden?",         topFraction = 0.28f, leftFraction  = 0.02f,  maxWidthFraction = 0.44f, targetAlpha = 0.65f, floatDurationMs = 3200, floatDelayMs =  300, staggerDelayMs =  450, fontSize = 12),
    SplashPhrase("Que dit la Bible sur la foi?",             topFraction = 0.30f, rightFraction = 0.03f,  maxWidthFraction = 0.42f, targetAlpha = 0.72f, floatDurationMs = 4300, floatDelayMs =  900, staggerDelayMs =  600, fontSize = 12),
    SplashPhrase("O que a Bíblia diz sobre a graça?",        topFraction = 0.68f, leftFraction  = 0.03f,  maxWidthFraction = 0.44f, targetAlpha = 0.60f, floatDurationMs = 3800, floatDelayMs =  500, staggerDelayMs =  750, fontSize = 12),
    SplashPhrase("Что говорит Библия о надежде?",            topFraction = 0.65f, rightFraction = 0.02f,  maxWidthFraction = 0.46f, targetAlpha = 0.68f, floatDurationMs = 4500, floatDelayMs = 1400, staggerDelayMs =  900, fontSize = 12),
    SplashPhrase("圣经怎么说关于智慧？",                       topFraction = 0.82f, leftFraction  = 0.05f,  maxWidthFraction = 0.38f, targetAlpha = 0.80f, floatDurationMs = 3000, floatDelayMs =  200, staggerDelayMs = 1050, fontSize = 14),
    SplashPhrase("प्यार के बारे में बाइबल क्या कहती है?",    topFraction = 0.87f, leftFraction  = 0.30f,  maxWidthFraction = 0.40f, targetAlpha = 0.58f, floatDurationMs = 4200, floatDelayMs =  800, staggerDelayMs = 1200, fontSize = 11),
    SplashPhrase("성경은 용서에 대해 뭐라고 하나요?",          topFraction = 0.80f, rightFraction = 0.04f,  maxWidthFraction = 0.44f, targetAlpha = 0.72f, floatDurationMs = 3600, floatDelayMs = 1200, staggerDelayMs = 1350, fontSize = 12),
    SplashPhrase("ماذا يقول الكتاب المقدس عن الصلاة؟", isRtl = true,
                                                         topFraction = 0.14f, rightFraction = 0.22f,  maxWidthFraction = 0.42f, targetAlpha = 0.62f, floatDurationMs = 4000, floatDelayMs =  400, staggerDelayMs = 1500, fontSize = 12),
)

private const val SPLASH_DURATION_MS = 5500L
private const val SPLASH_EXIT_MS = 700

@Composable
fun SplashScreen(onComplete: () -> Unit) {
    var isExiting by remember { mutableStateOf(false) }
    var centerVisible by remember { mutableStateOf(false) }

    // Per-phrase alpha animatables (stagger fade-in)
    val phraseAlphas = remember { PHRASES.map { Animatable(0f) } }
    // Per-phrase vertical float offset in dp
    val phraseFloats = remember { PHRASES.map { Animatable(0f) } }

    val screenAlpha by animateFloatAsState(
        targetValue = if (isExiting) 0f else 1f,
        animationSpec = tween(SPLASH_EXIT_MS),
        label = "screenAlpha",
    )
    val centerAlpha by animateFloatAsState(
        targetValue = if (centerVisible) 1f else 0f,
        animationSpec = tween(700),
        label = "centerAlpha",
    )
    val centerOffsetY by animateDpAsState(
        targetValue = if (centerVisible) 0.dp else 12.dp,
        animationSpec = tween(700),
        label = "centerOffsetY",
    )

    // Stagger fade-in for each phrase
    PHRASES.forEachIndexed { i, phrase ->
        LaunchedEffect(i) {
            delay(phrase.staggerDelayMs)
            phraseAlphas[i].animateTo(phrase.targetAlpha, tween(600))
        }
    }

    // Float loop for each phrase (independent speed & phase)
    PHRASES.forEachIndexed { i, phrase ->
        LaunchedEffect(i) {
            delay(phrase.floatDelayMs)
            while (true) {
                phraseFloats[i].animateTo(-8f, tween(phrase.floatDurationMs, easing = FastOutSlowInEasing))
                phraseFloats[i].animateTo(0f,  tween(phrase.floatDurationMs, easing = FastOutSlowInEasing))
            }
        }
    }

    // Center content entrance + exit sequence
    LaunchedEffect(Unit) {
        delay(800)
        centerVisible = true
        delay(SPLASH_DURATION_MS - 800)
        isExiting = true
        delay(SPLASH_EXIT_MS.toLong())
        onComplete()
    }

    val configuration = LocalConfiguration.current
    val screenWidthDp  = configuration.screenWidthDp.dp
    val screenHeightDp = configuration.screenHeightDp.dp

    Box(
        modifier = Modifier
            .fillMaxSize()
            .alpha(screenAlpha)
            .background(
                Brush.linearGradient(
                    colors = listOf(Color(0xFF3A5F96), Color(0xFF4A6FA5), Color(0xFF5A7FB5)),
                    start = Offset(0f, 0f),
                    end = Offset(Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY),
                ),
            ),
    ) {
        // Scattered multilingual phrases
        PHRASES.forEachIndexed { i, phrase ->
            val xOffset = if (phrase.leftFraction >= 0f) {
                screenWidthDp * phrase.leftFraction
            } else {
                screenWidthDp - screenWidthDp * phrase.rightFraction - screenWidthDp * phrase.maxWidthFraction
            }
            val yOffset = screenHeightDp * phrase.topFraction + phraseFloats[i].value.dp

            CompositionLocalProvider(
                LocalLayoutDirection provides
                    if (phrase.isRtl) LayoutDirection.Rtl else LayoutDirection.Ltr,
            ) {
                Text(
                    text = "\u201C${phrase.text}\u201D",
                    modifier = Modifier
                        .absoluteOffset(x = xOffset, y = yOffset)
                        .widthIn(max = screenWidthDp * phrase.maxWidthFraction)
                        .alpha(phraseAlphas[i].value),
                    style = MaterialTheme.typography.bodySmall.copy(
                        fontStyle = FontStyle.Italic,
                        fontSize = phrase.fontSize.sp,
                        lineHeight = (phrase.fontSize * 1.5).sp,
                    ),
                    color = Color.White,
                    textAlign = if (phrase.isRtl) TextAlign.End else TextAlign.Start,
                )
            }
        }

        // Center content: cross + title + subtitle
        Column(
            modifier = Modifier
                .align(Alignment.Center)
                .alpha(centerAlpha)
                .absoluteOffset(y = centerOffsetY),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Icon(
                painter = painterResource(id = R.drawable.ic_splash_icon),
                contentDescription = null,
                tint = Color.White.copy(alpha = 0.9f),
                modifier = Modifier.size(64.dp),
            )

            Spacer(Modifier.height(24.dp))

            Text(
                text = stringResource(R.string.app_name),
                style = MaterialTheme.typography.headlineMedium,
                color = Color.White,
                fontWeight = FontWeight.SemiBold,
            )

            Text(
                text = "Find encouragement through Scripture",
                style = MaterialTheme.typography.labelSmall,
                color = Color.White.copy(alpha = 0.6f),
                letterSpacing = 1.5.sp,
            )
        }
    }
}

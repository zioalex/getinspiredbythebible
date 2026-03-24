package com.bibleinspiration.presentation.screens

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
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

private data class SplashQuestion(val text: String, val isRtl: Boolean = false)

private val QUESTIONS = listOf(
    SplashQuestion("What does the Bible say about love?"),
    SplashQuestion("Cosa dice la Bibbia sul perdono?"),
    SplashQuestion("¿Qué dice la Biblia sobre la esperanza?"),
    SplashQuestion("Was sagt die Bibel über Frieden?"),
    SplashQuestion("Que dit la Bible sur la foi?"),
    SplashQuestion("O que a Bíblia diz sobre a graça?"),
    SplashQuestion("Что говорит Библия о надежде?"),
    SplashQuestion("圣经怎么说关于智慧？"),
    SplashQuestion("प्यार के बारे में बाइबल क्या कहती है?"),
    SplashQuestion("성경은 용서에 대해 뭐라고 하나요?"),
    SplashQuestion("ماذا يقول الكتاب المقدس عن الصلاة؟", isRtl = true),
)

private const val PHRASE_INTERVAL_MS = 2200L
private const val PHRASE_FADE_MS = 500
private const val SPLASH_DURATION_MS = 4200L
private const val SPLASH_EXIT_MS = 700

@Composable
fun SplashScreen(onComplete: () -> Unit) {
    var currentIndex by remember { mutableIntStateOf(0) }
    var phraseVisible by remember { mutableStateOf(true) }
    var isExiting by remember { mutableStateOf(false) }

    val phraseAlpha by animateFloatAsState(
        targetValue = if (phraseVisible) 1f else 0f,
        animationSpec = tween(PHRASE_FADE_MS),
        label = "phraseAlpha",
    )
    val phraseOffsetY by animateDpAsState(
        targetValue = if (phraseVisible) 0.dp else 8.dp,
        animationSpec = tween(PHRASE_FADE_MS),
        label = "phraseOffsetY",
    )
    val screenAlpha by animateFloatAsState(
        targetValue = if (isExiting) 0f else 1f,
        animationSpec = tween(SPLASH_EXIT_MS),
        label = "screenAlpha",
    )

    // Cycle through phrases
    LaunchedEffect(Unit) {
        repeat(QUESTIONS.size) {
            delay(PHRASE_INTERVAL_MS)
            phraseVisible = false
            delay(PHRASE_FADE_MS.toLong())
            currentIndex = (currentIndex + 1) % QUESTIONS.size
            phraseVisible = true
        }
    }

    // Exit after splash duration
    LaunchedEffect(Unit) {
        delay(SPLASH_DURATION_MS)
        isExiting = true
        delay(SPLASH_EXIT_MS.toLong())
        onComplete()
    }

    val question = QUESTIONS[currentIndex]

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
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(horizontal = 32.dp),
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
                modifier = Modifier.padding(top = 4.dp, bottom = 48.dp),
            )

            CompositionLocalProvider(
                LocalLayoutDirection provides
                    if (question.isRtl) LayoutDirection.Rtl else LayoutDirection.Ltr,
            ) {
                Text(
                    text = "\u201C${question.text}\u201D",
                    style = MaterialTheme.typography.bodyLarge.copy(fontStyle = FontStyle.Italic),
                    color = Color.White.copy(alpha = phraseAlpha),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.offset(y = phraseOffsetY),
                )
            }

            Spacer(Modifier.height(40.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                QUESTIONS.forEachIndexed { i, _ ->
                    Box(
                        modifier = Modifier
                            .animateContentSize(tween(300))
                            .height(6.dp)
                            .width(if (i == currentIndex) 20.dp else 6.dp)
                            .clip(RoundedCornerShape(3.dp))
                            .background(
                                if (i == currentIndex) Color.White.copy(alpha = 0.9f)
                                else Color.White.copy(alpha = 0.35f),
                            ),
                    )
                }
            }
        }
    }
}

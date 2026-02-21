package com.getinspiredbythebible.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val LightColorScheme = lightColorScheme(
    primary = GoldPrimary,
    onPrimary = NavyPrimary,
    primaryContainer = AmberSurface,
    onPrimaryContainer = NavyPrimary,
    secondary = NavyMedium,
    onSecondary = TextOnDark,
    secondaryContainer = NavySurface,
    onSecondaryContainer = NavyPrimary,
    tertiary = GoldDark,
    onTertiary = OffWhite,
    background = OffWhite,
    onBackground = TextPrimary,
    surface = OffWhite,
    onSurface = TextPrimary,
    surfaceVariant = AmberSurface,
    onSurfaceVariant = TextSecondary,
    error = ErrorRed,
    onError = OffWhite,
    errorContainer = ErrorContainer,
    onErrorContainer = ErrorRed,
)

private val DarkColorScheme = darkColorScheme(
    primary = GoldLight,
    onPrimary = NavyPrimary,
    primaryContainer = GoldDark,
    onPrimaryContainer = OffWhite,
    secondary = NavyLight,
    onSecondary = TextOnDark,
    secondaryContainer = NavyMedium,
    onSecondaryContainer = TextOnDark,
    tertiary = GoldPrimary,
    onTertiary = NavyPrimary,
    background = NavyPrimary,
    onBackground = TextOnDark,
    surface = NavyMedium,
    onSurface = TextOnDark,
    surfaceVariant = NavyLight,
    onSurfaceVariant = GoldLight,
    error = ErrorRed,
    onError = OffWhite,
    errorContainer = ErrorContainer,
    onErrorContainer = ErrorRed,
)

/**
 * Application-wide Material 3 theme with a warm gold/amber and deep navy palette.
 *
 * Dynamic color (Material You) is used on Android 12+ when available, with the
 * custom palette as fallback for older devices.
 */
@Composable
fun GetInspiredByTheBibleTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = BibleTypography,
        content = content,
    )
}

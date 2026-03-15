package com.bibleinspiration.presentation.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

// ── Web service palette reference ────────────────────────────────────────────
// Primary blue:   #4A6FA5  (primary-600 in the web Tailwind theme)
// Primary light:  #D0E4FF  (primary-100)
// Amber accent:   #D97706  (amber-600) used for verse link highlights
// Background:     #F8F5F0  (warm off-white, scripture-paper feel)
// Surface:        #FFFFFF
// Dark background:#121212
// ─────────────────────────────────────────────────────────────────────────────

private val LightColorScheme = lightColorScheme(
    // Primary — matches web primary-600 (#4A6FA5)
    primary = Color(0xFF4A6FA5),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD0E4FF),       // primary-100
    onPrimaryContainer = Color(0xFF003258),

    // Secondary — warm amber to match verse highlight chips
    secondary = Color(0xFF8B6914),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFDEA8),
    onSecondaryContainer = Color(0xFF2B1D00),

    // Tertiary — amber accent for verse link colour
    tertiary = Color(0xFFD97706),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFF3CD),
    onTertiaryContainer = Color(0xFF3B1F00),

    // Backgrounds — warm parchment feel matching web #F8F5F0
    background = Color(0xFFF8F5F0),
    onBackground = Color(0xFF1C1B1F),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1C1B1F),

    // Variants
    surfaceVariant = Color(0xFFEFEBE5),
    onSurfaceVariant = Color(0xFF49454F),
    outline = Color(0xFF79747E),
    outlineVariant = Color(0xFFCAC4D0),

    // Errors
    error = Color(0xFFB3261E),
    onError = Color.White,
    errorContainer = Color(0xFFF9DEDC),
    onErrorContainer = Color(0xFF410E0B),
)

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF90CAF9),                // light blue — readable on dark
    onPrimary = Color(0xFF0D47A1),
    primaryContainer = Color(0xFF1565C0),
    onPrimaryContainer = Color(0xFFE3F2FD),

    // Secondary — warm amber/gold matching the parchment feel (replaces unrelated green)
    secondary = Color(0xFFD4A853),
    onSecondary = Color(0xFF3B1F00),
    secondaryContainer = Color(0xFF4A2C00),
    onSecondaryContainer = Color(0xFFFFDEA8),

    // Tertiary — amber for verse links (consistent with light theme)
    tertiary = Color(0xFFFFCC80),               // amber for verse links
    onTertiary = Color(0xFF3B1F00),
    tertiaryContainer = Color(0xFF4A2C00),
    onTertiaryContainer = Color(0xFFFFDEA8),

    background = Color(0xFF121212),
    onBackground = Color(0xFFE0E0E0),
    surface = Color(0xFF1E1E1E),
    onSurface = Color(0xFFE0E0E0),
    surfaceVariant = Color(0xFF2C2C2C),
    onSurfaceVariant = Color(0xFFBDBDBD),

    error = Color(0xFFEF9A9A),
    onError = Color(0xFF7F0000),
    errorContainer = Color(0xFF4A0000),
    onErrorContainer = Color(0xFFFFDAD6),

    outline = Color(0xFF938F99),
    outlineVariant = Color(0xFF49454F),
)

/**
 * The app-wide Material 3 theme.
 *
 * Dynamic colour (Material You) is disabled so the app always uses the brand
 * palette above, matching the web service's visual identity on all devices.
 *
 * @param darkTheme Whether to use the dark colour scheme. Defaults to the system setting.
 * @param content   The composable content tree.
 */
@Composable
fun BibleInspirationTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
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
        typography = Typography,
        content = content,
    )
}

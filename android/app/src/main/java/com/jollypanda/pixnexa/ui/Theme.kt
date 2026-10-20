package com.jollypanda.pixnexa.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.Color

// The same dark-and-orange palette as PixNexa Desktop.
val Orange = Color(0xFFF97316)
val OrangeLight = Color(0xFFFB923C)
val OrangeDark = Color(0xFFEA580C)
val Ink = Color(0xFF1A0E05)

private val DarkColors = darkColorScheme(
    primary = Orange,
    onPrimary = Ink,
    primaryContainer = Color(0xFF3B2213),
    onPrimaryContainer = Color(0xFFFED7AA),
    secondary = OrangeLight,
    onSecondary = Ink,
    secondaryContainer = Color(0xFF2B221B),
    onSecondaryContainer = Color(0xFFF5EEE8),
    tertiary = Color(0xFF4ADE80),
    background = Color(0xFF110D0A),
    onBackground = Color(0xFFF5EEE8),
    surface = Color(0xFF110D0A),
    onSurface = Color(0xFFF5EEE8),
    surfaceVariant = Color(0xFF2A211A),
    onSurfaceVariant = Color(0xFFA99B8E),
    surfaceContainerLowest = Color(0xFF0C0907),
    surfaceContainerLow = Color(0xFF16110D),
    surfaceContainer = Color(0xFF1F1813),
    surfaceContainerHigh = Color(0xFF2B221B),
    surfaceContainerHighest = Color(0xFF342920),
    outline = Color(0xFF5A4A3D),
    outlineVariant = Color(0xFF3A2E24),
    error = Color(0xFFF87171),
    onError = Ink,
)

private val LightColors = lightColorScheme(
    primary = OrangeDark,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFEDD5),
    onPrimaryContainer = Color(0xFF431407),
    secondary = Color(0xFFC2410C),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFCE3CF),
    onSecondaryContainer = Color(0xFF3B1A06),
    tertiary = Color(0xFF15803D),
    background = Color(0xFFFFF8F3),
    onBackground = Color(0xFF1F1410),
    surface = Color(0xFFFFF8F3),
    onSurface = Color(0xFF1F1410),
    surfaceVariant = Color(0xFFF6E7DB),
    onSurfaceVariant = Color(0xFF6E5A4C),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFFFF1E6),
    surfaceContainer = Color(0xFFFBEADD),
    surfaceContainerHigh = Color(0xFFF6E2D2),
    surfaceContainerHighest = Color(0xFFF0DAC8),
    outline = Color(0xFFB8A08D),
    outlineVariant = Color(0xFFE5D2C2),
    error = Color(0xFFDC2626),
    onError = Color.White,
)

/** Follows the night mode set through AppCompat (System / Light / Dark in Settings). */
@Composable
fun PixNexaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}

/** Green for "smaller than before", used next to the file sizes. */
val successColor: Color
    @Composable @ReadOnlyComposable get() = MaterialTheme.colorScheme.tertiary

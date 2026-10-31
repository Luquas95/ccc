package io.github.luquas95.ccc.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** ccc's colours, as in the TUI (src/ccc/tui/theme.py): green (#00aa00) on black. */
object CccColors {
    val Background = Color(0xFF000000)
    val Surface = Color(0xFF0E0E0E)
    val SurfaceHigh = Color(0xFF1A1A1A)
    val Line = Color(0xFF3A3A3A)
    val Title = Color(0xFF00AA00)
    val Selection = Color(0xFF1E4D2B)
    val Accent = Color(0xFFFFA62B)
    val Human = Color(0xFF00AA00)
    val Claude = Color(0xFF5FAF5F)
    val Muted = Color(0xFF9E9E9E)
    val Running = Color(0xFF5FAF5F)
    val Waiting = Color(0xFFFFA62B)
    val Error = Color(0xFFE5534B)
    val Approval = Color(0xFFFFD75F)
}

private val scheme = darkColorScheme(
    primary = CccColors.Title,
    onPrimary = Color.Black,
    primaryContainer = CccColors.Selection,
    onPrimaryContainer = Color.White,
    secondary = CccColors.Accent,
    onSecondary = Color.Black,
    tertiary = CccColors.Claude,
    background = CccColors.Background,
    onBackground = Color(0xFFE6E6E6),
    surface = CccColors.Background,
    onSurface = Color(0xFFE6E6E6),
    surfaceVariant = CccColors.SurfaceHigh,
    onSurfaceVariant = CccColors.Muted,
    surfaceContainer = CccColors.Surface,
    surfaceContainerHigh = CccColors.SurfaceHigh,
    surfaceContainerHighest = CccColors.SurfaceHigh,
    surfaceContainerLow = CccColors.Surface,
    surfaceContainerLowest = CccColors.Background,
    outline = CccColors.Line,
    outlineVariant = CccColors.Line,
    error = CccColors.Error,
)

/** Always dark and black, like ccc in the terminal. */
@Composable
fun CccTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = scheme, content = content)
}

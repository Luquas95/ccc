package io.github.luquas95.ccc.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.Ansi
import io.github.luquas95.ccc.ui.theme.CccColors

private val FOREGROUND = Color(0xFFD0D0D0)

/** Keys for Claude Code's menus and editing, as tmux names. */
private val KEYS = listOf(
    "Esc" to "Escape", "Tab" to "Tab", "⇧Tab" to "BTab", "↑" to "Up", "↓" to "Down", "←" to "Left", "→" to "Right",
    "Enter" to "Enter", "Ctrl+C" to "C-c", "Ctrl+R" to "C-r", "Ctrl+O" to "C-o", "⌫" to "BSpace",
)

/** Quick answers to Claude Code's questions and menus, typed as they are. */
private val ANSWERS = listOf("y", "n", "1", "2", "3")

/** The screen of the terminal with its colours. */
fun screenText(screen: String): AnnotatedString = buildAnnotatedString {
    for (segment in Ansi.parse(screen.trimEnd('\n'))) {
        val style = segment.style
        var fg = style.fg?.let { Color(it) } ?: FOREGROUND
        var bg = style.bg?.let { Color(it) } ?: Color.Transparent
        if (style.reverse) {
            val swapped = fg
            fg = if (bg == Color.Transparent) CccColors.Background else bg
            bg = swapped
        }
        withStyle(
            SpanStyle(
                color = if (style.dim) fg.copy(alpha = 0.6f) else fg,
                background = bg,
                fontWeight = if (style.bold) FontWeight.Bold else null,
                fontStyle = if (style.italic) FontStyle.Italic else null,
                textDecoration = if (style.underline) TextDecoration.Underline else null,
            ),
        ) { append(segment.text) }
    }
}

/** What the terminal screen can do. */
class TerminalActions(
    val back: () -> Unit,
    val paste: (String, Boolean) -> Unit,
    val keys: (List<String>) -> Unit,
    val type: (String) -> Unit,
)

/** A conversation's Claude Code, live: its screen every second, keys and text into it. */
@Composable
fun TerminalScreen(state: TerminalState, name: String, snackbar: SnackbarHostState, actions: TerminalActions) {
    var draft by rememberSaveable { mutableStateOf("") }
    val vertical = rememberScrollState()
    val shown = state.terminal
    LaunchedEffect(shown?.screen) { vertical.scrollTo(vertical.maxValue) }
    Scaffold(
        topBar = { Bar(stringResource(R.string.terminal), name, actions.back) },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            Column(Modifier.bottomBarInsets().padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    KEYS.forEach { (label, key) -> AssistChip(onClick = { actions.keys(listOf(key)) }, label = { Text(label) }) }
                    ANSWERS.forEach { answer -> AssistChip(onClick = { actions.type(answer) }, label = { Text(answer) }) }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(draft, { draft = it }, Modifier.weight(1f),
                        placeholder = { Text(stringResource(R.string.terminal_hint)) }, maxLines = 4)
                    IconButton(onClick = { actions.paste(draft, true); draft = "" }, enabled = draft.isNotBlank()) {
                        Icon(Icons.AutoMirrored.Filled.Send, stringResource(R.string.send), tint = CccColors.Title)
                    }
                }
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            state.error?.let {
                Text(it, color = CccColors.Waiting, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(8.dp))
            }
            if (shown == null) {
                if (state.error == null) LinearProgressIndicator(Modifier.fillMaxWidth())
                return@Column
            }
            val sideways = rememberScrollState()
            // The terminal is wider than the phone: say so (the lines are cut at the edge, not wrapped).
            if (sideways.maxValue > 0) {
                Text(stringResource(R.string.terminal_scroll_hint, shown.width), color = CccColors.Muted,
                    style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp))
            }
            Box(
                Modifier
                    .fillMaxSize()
                    .background(CccColors.Background)
                    .verticalScroll(vertical)
                    .horizontalScroll(sideways)
                    .padding(6.dp),
            ) {
                Text(
                    remember(shown.screen) { screenText(shown.screen) },
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    lineHeight = 13.sp,
                    softWrap = false,
                    modifier = Modifier.width((shown.width * 6.7).dp),
                )
            }
        }
    }
}

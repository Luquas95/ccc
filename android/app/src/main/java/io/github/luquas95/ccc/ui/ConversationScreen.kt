package io.github.luquas95.ccc.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.ConversationStatus
import io.github.luquas95.ccc.data.Message
import io.github.luquas95.ccc.ui.theme.CccColors

private const val PREVIEW_LINES = 3

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(
    state: ConversationState,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onSend: (String, () -> Unit) -> Unit,
    onRetry: () -> Unit,
    onLoadOlder: () -> Unit,
    onDecide: (io.github.luquas95.ccc.data.Permission, String) -> Unit,
) {
    val detail = state.detail
    var draft by rememberSaveable(state.id) { mutableStateOf("") }
    val list = rememberLazyListState()
    // reverseLayout: item 0 is the newest, at the bottom; keep it in view when one arrives.
    val newest = state.messages.lastOrNull()?.index
    LaunchedEffect(newest) {
        if (list.firstVisibleItemIndex <= 1) list.animateScrollToItem(0)
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(detail?.name.orEmpty(), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        detail?.let {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                StatusDot(statusColor(it.state, it.permissions.isNotEmpty()))
                                Spacer(Modifier.width(6.dp))
                                Text(
                                    statusLabel(it.state),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = CccColors.Muted,
                                )
                            }
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back))
                    }
                },
                actions = {
                    if (detail != null && detail.state in RETRYABLE) {
                        IconButton(onClick = onRetry) { Icon(Icons.Filled.Refresh, stringResource(R.string.retry)) }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CccColors.Background),
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            Column(Modifier.imePadding().padding(8.dp)) {
                detail?.permissions?.forEach { permission ->
                    ApprovalCard(
                        permission,
                        detail.name,
                        onDecide = { onDecide(permission, it) },
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = draft,
                        onValueChange = { draft = it },
                        placeholder = { Text(stringResource(R.string.message_hint)) },
                        modifier = Modifier.weight(1f).heightIn(max = 160.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            unfocusedBorderColor = CccColors.Line,
                            focusedBorderColor = CccColors.Title,
                        ),
                    )
                    Spacer(Modifier.width(4.dp))
                    if (state.sending) {
                        CircularProgressIndicator(Modifier.padding(12.dp).width(24.dp))
                    } else {
                        IconButton(
                            onClick = { onSend(draft) { draft = "" } },
                            enabled = draft.isNotBlank(),
                        ) { Icon(Icons.AutoMirrored.Filled.Send, stringResource(R.string.send), tint = CccColors.Title) }
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            state = list,
            reverseLayout = true,
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.Bottom),
        ) {
            detail?.queued?.reversed()?.let { queued ->
                items(queued, key = { "queued:${it.id}" }) { QueuedBubble(it.text) }
            }
            items(state.messages.reversed(), key = { it.index }) { MessageItem(it) }
            if (detail != null && state.messages.isEmpty() && detail.queued.isEmpty()) {
                item(key = "empty") {
                    Text(stringResource(R.string.no_messages), color = CccColors.Muted, modifier = Modifier.padding(16.dp))
                }
            }
            if (state.hasOlder) {
                item(key = "older") {
                    LaunchedEffect(state.messages.firstOrNull()?.index) { onLoadOlder() }
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        TextButton(onClick = onLoadOlder) { Text(stringResource(R.string.load_older)) }
                    }
                }
            }
            detail?.let { header ->
                item(key = "header") { Header(header) }
            }
        }
    }
}

private val RETRYABLE = setOf(ConversationStatus.BLOCKED_ERROR, ConversationStatus.PAUSED_LIMIT, ConversationStatus.WAITING_RETRY)

@Composable
private fun Header(detail: io.github.luquas95.ccc.data.ConversationDetail) {
    Column(Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
        Text(detail.path, style = MaterialTheme.typography.bodySmall, color = CccColors.Muted, fontFamily = FontFamily.Monospace)
        if (detail.flags.isNotEmpty()) {
            Text(detail.flags, style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
        }
        detail.remoteControlUrl?.let {
            Text("${stringResource(R.string.remote_control_link)}: $it", style = MaterialTheme.typography.bodySmall,
                color = CccColors.Title)
        }
        detail.lastError?.takeIf { detail.state == ConversationStatus.BLOCKED_ERROR }?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = CccColors.Error)
        }
    }
}

@Composable
private fun MessageItem(message: Message) {
    when (message.kind) {
        "human" -> Bubble(stringResource(R.string.you), message.text, shortTime(message.time), CccColors.Human, end = true)
        "assistant_text" -> Bubble(stringResource(R.string.claude), message.text, shortTime(message.time), CccColors.Claude)
        else -> ToolLine(message)
    }
}

@Composable
private fun Bubble(who: String, text: String, time: String?, color: androidx.compose.ui.graphics.Color, end: Boolean = false) {
    Box(Modifier.fillMaxWidth(), contentAlignment = if (end) Alignment.CenterEnd else Alignment.CenterStart) {
        Card(
            modifier = Modifier.fillMaxWidth(if (end) 0.88f else 1f),
            shape = RoundedCornerShape(10.dp),
            colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
            border = BorderStroke(1.dp, color),
        ) {
            Column(Modifier.padding(10.dp)) {
                Row {
                    Text(who, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelLarge, color = color)
                    time?.let {
                        Spacer(Modifier.width(8.dp))
                        Text(it, style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
                    }
                }
                SelectionContainer { Text(text, style = MaterialTheme.typography.bodyMedium) }
            }
        }
    }
}

@Composable
private fun QueuedBubble(text: String) {
    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
        Card(
            modifier = Modifier.fillMaxWidth(0.88f),
            shape = RoundedCornerShape(10.dp),
            colors = CardDefaults.cardColors(containerColor = CccColors.Background),
            border = BorderStroke(1.dp, CccColors.Line),
        ) {
            Column(Modifier.padding(10.dp)) {
                Row {
                    Text(stringResource(R.string.you), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelLarge)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.queued), style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
                }
                Text(text, style = MaterialTheme.typography.bodyMedium, color = CccColors.Muted)
            }
        }
    }
}

/** A tool call or its result: one muted line, the whole of it on a tap. */
@Composable
private fun ToolLine(message: Message) {
    var open by rememberSaveable(message.index) { mutableStateOf(false) }
    val call = message.kind == "tool_call"
    val text = if (open) message.detail ?: message.text else message.text
    Row(
        Modifier.fillMaxWidth().clickable { open = !open }.padding(horizontal = 4.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(if (call) "⚙" else "↳", color = CccColors.Muted, modifier = Modifier.width(20.dp))
        Text(
            text,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            color = CccColors.Muted,
            maxLines = if (open) Int.MAX_VALUE else PREVIEW_LINES,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

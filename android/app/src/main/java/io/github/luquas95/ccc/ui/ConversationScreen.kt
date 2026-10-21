package io.github.luquas95.ccc.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.RadioButton
import androidx.compose.runtime.remember
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import io.github.luquas95.ccc.data.Permission
import io.github.luquas95.ccc.data.PromptPreset
import io.github.luquas95.ccc.data.mentionAt
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

/** What a conversation can do, besides showing [ConversationState]. */
class ConversationActions(
    val back: () -> Unit,
    val send: (String, () -> Unit) -> Unit,
    val retry: () -> Unit,
    val loadOlder: () -> Unit,
    val decide: (Permission, String) -> Unit,
    val archive: (Boolean) -> Unit,
    val delete: () -> Unit,
    val setGroup: (String?) -> Unit,
    val export: () -> Unit,
    val usePreset: (PromptPreset, (String) -> Unit) -> Unit,
    val mention: (String?) -> Unit,
    val tasks: () -> Unit,
    val runs: () -> Unit,
    val agents: () -> Unit,
    val terminal: () -> Unit,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(
    state: ConversationState,
    presets: List<PromptPreset>,
    ownGroups: List<String>,
    snackbar: SnackbarHostState,
    actions: ConversationActions,
) {
    val detail = state.detail
    var draft by rememberSaveable(state.id, stateSaver = TextFieldValue.Saver) { mutableStateOf(TextFieldValue("")) }
    var menu by remember { mutableStateOf(false) }
    var dialog by remember { mutableStateOf<String?>(null) }
    val archived = detail?.archived == true
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
                    IconButton(onClick = actions.back) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back))
                    }
                },
                actions = {
                    if (detail != null && detail.state in RETRYABLE && !archived) {
                        IconButton(onClick = actions.retry) { Icon(Icons.Filled.Refresh, stringResource(R.string.retry)) }
                    }
                    if (detail != null) {
                        IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, stringResource(R.string.more)) }
                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                            if (detail.deliveryMode == "interactive" || detail.deliveryMode == "remote_control") {
                                DropdownMenuItem(text = { Text(stringResource(R.string.terminal)) },
                                    onClick = { menu = false; actions.terminal() })
                            }
                            DropdownMenuItem(text = { Text(stringResource(R.string.tasks) + " (${detail.pending})") },
                                onClick = { menu = false; actions.tasks() })
                            DropdownMenuItem(text = { Text(stringResource(R.string.runs)) },
                                onClick = { menu = false; actions.runs() })
                            DropdownMenuItem(text = { Text(stringResource(R.string.agents)) },
                                onClick = { menu = false; actions.agents() })
                            DropdownMenuItem(text = { Text(stringResource(R.string.group_put)) },
                                onClick = { menu = false; dialog = "group" })
                            DropdownMenuItem(text = { Text(stringResource(R.string.export)) },
                                onClick = { menu = false; actions.export() })
                            DropdownMenuItem(
                                text = { Text(stringResource(if (archived) R.string.restore else R.string.archive_it)) },
                                onClick = { menu = false; actions.archive(!archived) },
                            )
                            DropdownMenuItem(text = { Text(stringResource(R.string.delete), color = CccColors.Error) },
                                onClick = { menu = false; dialog = "delete" })
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CccColors.Background),
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            Column(Modifier.imePadding().padding(8.dp)) {
                if (archived) {
                    Button(onClick = { actions.archive(false) }, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.restore))
                    }
                    return@Column
                }
                detail?.permissions?.forEach { permission ->
                    ApprovalCard(
                        permission,
                        detail.name,
                        onDecide = { actions.decide(permission, it) },
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                }
                Mentions(state.mentions) { path ->
                    val at = mentionAt(draft.text)?.first ?: return@Mentions
                    val text = draft.text.substring(0, at) + "@$path "
                    draft = TextFieldValue(text, TextRange(text.length))
                    actions.mention(null)
                }
                if (presets.isNotEmpty()) {
                    Row(
                        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(bottom = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        presets.forEach { preset ->
                            AssistChip(
                                onClick = {
                                    actions.usePreset(preset) { text ->
                                        val joined = if (draft.text.isBlank()) text else draft.text.trimEnd() + " " + text
                                        draft = TextFieldValue(joined, TextRange(joined.length))
                                    }
                                },
                                label = { Text((if (preset.sendNow) "⏎ " else "✎ ") + preset.name) },
                            )
                        }
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = draft,
                        onValueChange = {
                            draft = it
                            actions.mention(mentionAt(it.text.substring(0, it.selection.end))?.second)
                        },
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
                            onClick = { actions.send(draft.text) { draft = TextFieldValue("") } },
                            enabled = draft.text.isNotBlank(),
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
                    LaunchedEffect(state.messages.firstOrNull()?.index) { actions.loadOlder() }
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        TextButton(onClick = actions.loadOlder) { Text(stringResource(R.string.load_older)) }
                    }
                }
            }
            detail?.let { header ->
                item(key = "header") { Header(header) }
            }
        }
    }
    when (dialog) {
        "group" -> GroupPicker(detail?.group?.title, ownGroups, actions.setGroup) { dialog = null }
        "delete" -> AlertDialog(
            onDismissRequest = { dialog = null },
            title = { Text(stringResource(R.string.delete_title)) },
            text = { Text(stringResource(R.string.delete_text, detail?.name.orEmpty())) },
            confirmButton = {
                TextButton(onClick = { dialog = null; actions.delete() }) {
                    Text(stringResource(R.string.delete), color = CccColors.Error)
                }
            },
            dismissButton = { TextButton(onClick = { dialog = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

@Composable
private fun Mentions(files: List<String>, onPick: (String) -> Unit) {
    if (files.isEmpty()) return
    Card(
        Modifier.fillMaxWidth().padding(bottom = 4.dp),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Line),
    ) {
        files.forEach { path ->
            Text(
                "@$path",
                Modifier.fillMaxWidth().clickable { onPick(path) }.padding(horizontal = 12.dp, vertical = 8.dp),
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** Put the conversation into one of your own groups, a new one, or none. */
@Composable
private fun GroupPicker(current: String?, ownGroups: List<String>, onPick: (String?) -> Unit, onClose: () -> Unit) {
    var name by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text(stringResource(R.string.group_put)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                (listOf<String?>(null) + ownGroups).forEach { group ->
                    Row(
                        Modifier.fillMaxWidth().clickable { onPick(group); onClose() },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = group == current, onClick = { onPick(group); onClose() })
                        Text(group ?: stringResource(R.string.group_none))
                    }
                }
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text(stringResource(R.string.group_new)) },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onPick(name.trim()); onClose() }, enabled = name.isNotBlank()) {
                Text(stringResource(R.string.save))
            }
        },
        dismissButton = { TextButton(onClick = onClose) { Text(stringResource(R.string.cancel)) } },
    )
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

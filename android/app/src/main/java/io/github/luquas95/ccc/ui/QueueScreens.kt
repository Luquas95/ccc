package io.github.luquas95.ccc.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.DiffLine
import io.github.luquas95.ccc.data.Run
import io.github.luquas95.ccc.data.Task
import io.github.luquas95.ccc.ui.theme.CccColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Bar(title: String, subtitle: String?, onBack: () -> Unit, actions: @Composable () -> Unit = {}) {
    TopAppBar(
        title = {
            Column {
                Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                subtitle?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = CccColors.Muted, maxLines = 1) }
            }
        },
        navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) }
        },
        actions = { actions() },
        colors = TopAppBarDefaults.topAppBarColors(containerColor = CccColors.Background),
    )
}

/** What the task queue screen can do. */
class TasksActions(
    val back: () -> Unit,
    val add: (String, String) -> Unit,
    val edit: (Int, String, String) -> Unit,
    val remove: (Int) -> Unit,
    val move: (Int, Int) -> Unit,
    val paused: (Boolean) -> Unit,
    val autoContinue: (Boolean) -> Unit,
)

/** The conversation's task queue (t in ccc): add, edit, reorder, remove; pause it, auto-continue. */
@Composable
fun TasksScreen(state: TasksState, name: String, snackbar: SnackbarHostState, actions: TasksActions) {
    var editing by remember { mutableStateOf<Task?>(null) }
    var adding by remember { mutableStateOf(false) }
    val queue = state.tasks
    Scaffold(
        topBar = { Bar(stringResource(R.string.tasks), name, actions.back) },
        floatingActionButton = {
            FloatingActionButton(onClick = { adding = true }, containerColor = CccColors.Claude, contentColor = Color.Black) {
                Icon(Icons.Filled.Add, stringResource(R.string.task_add))
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 12.dp, end = 12.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (queue == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                return@LazyColumn
            }
            item {
                Column {
                    SwitchLine(stringResource(R.string.task_paused), queue.paused, actions.paused)
                    SwitchLine(stringResource(R.string.auto_continue), queue.autoContinue, actions.autoContinue)
                }
            }
            if (queue.tasks.isEmpty()) {
                item { Text(stringResource(R.string.tasks_empty), color = CccColors.Muted, modifier = Modifier.padding(16.dp)) }
            }
            itemsIndexed(queue.tasks, key = { _, task -> task.id }) { position, task ->
                TaskCard(position, task, last = position == queue.tasks.lastIndex, actions) { editing = task }
            }
        }
    }
    editing?.let { task ->
        TaskDialog(task, onClose = { editing = null }) { text, whenText ->
            actions.edit(task.id, text, whenText)
            editing = null
        }
    }
    if (adding) {
        TaskDialog(null, onClose = { adding = false }) { text, whenText ->
            actions.add(text, whenText)
            adding = false
        }
    }
}

@Composable
private fun SwitchLine(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun TaskCard(position: Int, task: Task, last: Boolean, actions: TasksActions, onEdit: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onEdit),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Line),
    ) {
        Row(Modifier.padding(start = 12.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("${position + 1}.", color = CccColors.Title, fontWeight = FontWeight.Bold, modifier = Modifier.width(28.dp))
            Column(Modifier.weight(1f)) {
                Text(task.text, maxLines = 3, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium)
                val notes = listOfNotNull(
                    shortTime(task.notBefore)?.let { stringResource(R.string.task_at, it) },
                    stringResource(R.string.task_by_routine).takeIf { task.byRoutine },
                )
                if (notes.isNotEmpty()) {
                    Text(notes.joinToString(" · "), style = MaterialTheme.typography.labelMedium, color = CccColors.Waiting)
                }
            }
            Column {
                IconButton(onClick = { actions.move(task.id, -1) }, enabled = position > 0) {
                    Icon(Icons.Filled.KeyboardArrowUp, stringResource(R.string.move_up))
                }
                IconButton(onClick = { actions.move(task.id, 1) }, enabled = !last) {
                    Icon(Icons.Filled.KeyboardArrowDown, stringResource(R.string.move_down))
                }
            }
            Column {
                IconButton(onClick = onEdit) { Icon(Icons.Filled.Edit, stringResource(R.string.edit)) }
                IconButton(onClick = { actions.remove(task.id) }) {
                    Icon(Icons.Filled.Delete, stringResource(R.string.delete), tint = CccColors.Error)
                }
            }
        }
    }
}

/** A task's text and when it may start (empty: as soon as possible; HH:MM, YYYY-MM-DD HH:MM, reset). */
@Composable
private fun TaskDialog(task: Task?, onClose: () -> Unit = {}, onSave: (String, String) -> Unit) {
    var text by rememberSaveable(task?.id) { mutableStateOf(task?.text.orEmpty()) }
    var whenText by rememberSaveable(task?.id) {
        mutableStateOf(task?.notBefore?.take(16)?.replace('T', ' ').orEmpty())
    }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text(stringResource(if (task == null) R.string.task_add else R.string.task_edit)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = text, onValueChange = { text = it }, minLines = 4, maxLines = 10,
                    modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    value = whenText,
                    onValueChange = { whenText = it },
                    label = { Text(stringResource(R.string.task_when)) },
                    placeholder = { Text(stringResource(R.string.task_when_hint)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(text.trim(), whenText.trim()) }, enabled = text.isNotBlank()) {
                Text(stringResource(R.string.save))
            }
        },
        dismissButton = { TextButton(onClick = onClose) { Text(stringResource(R.string.cancel)) } },
    )
}

/** The conversation's runs (queue detail in ccc): state, tokens, commit; a commit opens its diff. */
@Composable
fun RunsScreen(
    state: RunsState,
    name: String,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onDiff: (Int) -> Unit,
    onRevert: (Int, Boolean) -> Unit,
) {
    var reverting by remember { mutableStateOf<Run?>(null) }
    Scaffold(
        topBar = { Bar(stringResource(R.string.runs), name, onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            val runs = state.runs
            if (runs == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                return@LazyColumn
            }
            if (runs.isEmpty()) {
                item { Text(stringResource(R.string.runs_empty), color = CccColors.Muted, modifier = Modifier.padding(16.dp)) }
            }
            items(runs, key = { it.id }) { run -> RunCard(run, { onDiff(run.id) }, { reverting = run }) }
        }
    }
    reverting?.let { run ->
        var tell by rememberSaveable { mutableStateOf(true) }
        AlertDialog(
            onDismissRequest = { reverting = null },
            title = { Text(stringResource(R.string.revert_title)) },
            text = {
                Column {
                    Text(stringResource(R.string.revert_text, run.commit.orEmpty().take(7), run.task.lineSequence().first().take(80)))
                    Row(Modifier.clickable { tell = !tell }, verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = tell, onCheckedChange = { tell = it })
                        Text(stringResource(R.string.revert_tell))
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { onRevert(run.id, tell); reverting = null }) {
                    Text(stringResource(R.string.revert), color = CccColors.Error)
                }
            },
            dismissButton = { TextButton(onClick = { reverting = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

@Composable
private fun RunCard(run: Run, onDiff: () -> Unit, onRevert: () -> Unit) {
    val color = when (run.status) {
        "success" -> CccColors.Running
        "rate_limited" -> CccColors.Waiting
        else -> CccColors.Error
    }
    Card(
        Modifier.fillMaxWidth().clickable(enabled = run.commit != null, onClick = onDiff),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Line),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusDot(color)
                Spacer(Modifier.width(8.dp))
                Text(
                    listOfNotNull(shortTime(run.startedAt), runStatusLabel(run.status), "%,d tok".format(run.tokens))
                        .joinToString(" · "),
                    style = MaterialTheme.typography.labelMedium,
                    color = CccColors.Muted,
                    modifier = Modifier.weight(1f),
                )
                run.commit?.let { commit ->
                    Text(
                        commit.take(7) + if (run.revertedBy != null) " ↺" else "",
                        fontFamily = FontFamily.Monospace,
                        color = if (run.revertedBy != null) CccColors.Muted else CccColors.Title,
                        textDecoration = if (run.revertedBy != null) TextDecoration.LineThrough else null,
                    )
                }
            }
            Text(run.task.lineSequence().first(), maxLines = 2, overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp))
            (run.error ?: run.result)?.let {
                Text(it, maxLines = 3, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall,
                    color = if (run.error != null) CccColors.Error else CccColors.Muted)
            }
            if (run.commit == null && run.gitNote != null) {
                Text(run.gitNote, style = MaterialTheme.typography.labelSmall, color = CccColors.Muted)
            }
            if (run.commit != null && run.revertedBy == null) {
                Row {
                    TextButton(onClick = onDiff) { Text(stringResource(R.string.diff_show)) }
                    TextButton(onClick = onRevert) { Text(stringResource(R.string.revert), color = CccColors.Error) }
                }
            }
        }
    }
}

@Composable
private fun runStatusLabel(status: String): String = stringResource(
    when (status) {
        "success" -> R.string.run_success
        "rate_limited" -> R.string.run_rate_limited
        else -> R.string.run_error
    },
)

/** A run's commit line by line; tap a changed line to comment, send them all to Claude. */
@Composable
fun DiffScreen(
    state: DiffState,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onComment: (Int, String) -> Unit,
    onSend: () -> Unit,
) {
    var commenting by remember { mutableStateOf<DiffLine?>(null) }
    var leaving by remember { mutableStateOf(false) }
    BackHandler(enabled = state.comments.isNotEmpty()) { leaving = true }
    val diff = state.diff
    Scaffold(
        topBar = {
            Bar(
                stringResource(R.string.diff_title, diff?.commit?.take(7).orEmpty()),
                diff?.task,
                { if (state.comments.isEmpty()) onBack() else leaving = true },
            )
        },
        bottomBar = {
            if (state.comments.isNotEmpty()) {
                Button(
                    onClick = onSend,
                    enabled = !state.sending,
                    modifier = Modifier.fillMaxWidth().imePadding().padding(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CccColors.Claude, contentColor = Color.Black),
                ) { Text(stringResource(R.string.comments_send, state.comments.size)) }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (diff == null) {
            LinearProgressIndicator(Modifier.fillMaxWidth().padding(padding))
            return@Scaffold
        }
        // One horizontal scroll for the whole diff: code lines keep their shape.
        val scroll = rememberScrollState()
        LazyColumn(Modifier.fillMaxSize().padding(padding).horizontalScroll(scroll)) {
            items(diff.lines, key = { it.index }) { line ->
                DiffRow(line, state.comments[line.index]) { if (line.commentable) commenting = line }
            }
        }
    }
    commenting?.let { line ->
        var text by rememberSaveable(line.index) { mutableStateOf(state.comments[line.index].orEmpty()) }
        AlertDialog(
            onDismissRequest = { commenting = null },
            title = { Text(listOfNotNull(line.path, line.newLine ?: line.oldLine).joinToString(":")) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(line.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall,
                        color = CccColors.Muted, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    OutlinedTextField(value = text, onValueChange = { text = it }, minLines = 3,
                        placeholder = { Text(stringResource(R.string.comment_hint)) }, modifier = Modifier.fillMaxWidth())
                }
            },
            confirmButton = {
                TextButton(onClick = { onComment(line.index, text); commenting = null }) { Text(stringResource(R.string.save)) }
            },
            dismissButton = { TextButton(onClick = { commenting = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
    if (leaving) {
        AlertDialog(
            onDismissRequest = { leaving = false },
            title = { Text(stringResource(R.string.comments_discard)) },
            text = { Text(stringResource(R.string.comments_discard_text, state.comments.size)) },
            confirmButton = {
                TextButton(onClick = { leaving = false; onBack() }) { Text(stringResource(R.string.discard), color = CccColors.Error) }
            },
            dismissButton = { TextButton(onClick = { leaving = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

@Composable
private fun DiffRow(line: DiffLine, comment: String?, onTap: () -> Unit) {
    val (color, background) = when (line.kind) {
        "added" -> CccColors.Claude to Color(0xFF0B2A0B)
        "removed" -> CccColors.Error to Color(0xFF2E0E0E)
        "hunk" -> CccColors.Title to Color.Transparent
        "meta", "header" -> CccColors.Muted to Color.Transparent
        else -> Color(0xFFD0D0D0) to Color.Transparent
    }
    val screen = LocalConfiguration.current.screenWidthDp.dp
    Column(
        Modifier.widthIn(min = screen).clickable(enabled = line.commentable, onClick = onTap).background(background),
    ) {
        Row(Modifier.padding(horizontal = 8.dp)) {
            Text(
                (line.newLine ?: line.oldLine)?.toString().orEmpty(),
                fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall, color = CccColors.Line,
                modifier = Modifier.width(36.dp),
            )
            Text(if (comment != null) "●" else " ", color = CccColors.Approval, modifier = Modifier.width(14.dp),
                style = MaterialTheme.typography.bodySmall)
            Text(line.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall, color = color,
                softWrap = false)
        }
        comment?.let {
            Text(
                "💬 $it",
                style = MaterialTheme.typography.bodySmall,
                color = CccColors.Approval,
                modifier = Modifier.padding(start = 58.dp, end = 8.dp, bottom = 4.dp).widthIn(max = 360.dp),
            )
        }
    }
}

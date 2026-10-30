package io.github.luquas95.ccc.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.Conversation
import io.github.luquas95.ccc.data.ConversationStatus
import io.github.luquas95.ccc.data.Group
import io.github.luquas95.ccc.data.ListDetail
import io.github.luquas95.ccc.data.ListFilter
import io.github.luquas95.ccc.data.UpdateInfo
import io.github.luquas95.ccc.data.shortPath
import io.github.luquas95.ccc.ui.theme.CccColors

/** What the list can do, besides showing [HomeState]. */
class ConversationsActions(
    val open: (Int) -> Unit,
    val approvals: () -> Unit,
    val settings: () -> Unit,
    val new: () -> Unit,
    val refresh: () -> Unit,
    val search: () -> Unit,
    val showArchive: (Boolean) -> Unit,
    val filter: (String) -> Unit,
    val nextWaiting: () -> Unit,
    val renameGroup: (String, String) -> Unit,
    val deleteGroup: (String) -> Unit,
    val routines: () -> Unit,
    val sessions: () -> Unit,
    val analytics: () -> Unit,
    val applyUpdate: () -> Unit = {},
)

private val MARKERS = listOf(ListFilter.WORKING, ListFilter.APPROVAL, ListFilter.ERROR, ListFilter.UNSEEN)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationsScreen(
    state: HomeState,
    listDetails: Set<String>,
    appBuild: Int,
    snackbar: SnackbarHostState,
    actions: ConversationsActions,
) {
    var groupMenu by remember { mutableStateOf<String?>(null) }
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("ccc", color = CccColors.Accent, fontWeight = FontWeight.Bold)
                        DaemonLine(state)
                    }
                },
                actions = {
                    IconButton(onClick = actions.search) { Icon(Icons.Filled.Search, stringResource(R.string.search)) }
                    IconButton(onClick = actions.approvals) {
                        BadgedBox(badge = {
                            if (state.permissions.isNotEmpty()) Badge { Text(state.permissions.size.toString()) }
                        }) { Icon(Icons.Filled.Notifications, stringResource(R.string.approvals)) }
                    }
                    var menu by remember { mutableStateOf(false) }
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, stringResource(R.string.more)) }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        listOf(
                            R.string.routines to actions.routines,
                            R.string.live_sessions to actions.sessions,
                            R.string.analytics to actions.analytics,
                            R.string.ccc_settings to actions.settings,
                        ).forEach { (label, go) ->
                            DropdownMenuItem(text = { Text(stringResource(label)) }, onClick = { menu = false; go() })
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CccColors.Background),
            )
        },
        floatingActionButton = {
            if (!state.showArchive) {
                ExtendedFloatingActionButton(
                    onClick = actions.new,
                    icon = { Icon(Icons.Filled.Add, null) },
                    text = { Text(stringResource(R.string.new_conversation)) },
                    containerColor = CccColors.Claude,
                    contentColor = Color.Black,
                )
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            PrimaryTabRow(
                selectedTabIndex = if (state.showArchive) 1 else 0,
                containerColor = CccColors.Background,
                contentColor = CccColors.Title,
            ) {
                Tab(selected = !state.showArchive, onClick = { actions.showArchive(false) },
                    text = { Text("${stringResource(R.string.conversations)} (${state.conversations.size})") })
                Tab(selected = state.showArchive, onClick = { actions.showArchive(true) },
                    text = { Text("${stringResource(R.string.archive)} (${state.archived.size})") })
            }
            PullToRefreshBox(
                isRefreshing = state.refreshing,
                onRefresh = actions.refresh,
                modifier = Modifier.fillMaxSize(),
            ) {
                ConversationList(state, listDetails, appBuild, actions) { groupMenu = it }
            }
        }
    }
    groupMenu?.let { name -> GroupDialog(name, actions, onClose = { groupMenu = null }) }
}

@Composable
private fun ConversationList(
    state: HomeState,
    listDetails: Set<String>,
    appBuild: Int,
    actions: ConversationsActions,
    onGroupMenu: (String) -> Unit,
) {
    val filter = ListFilter.parse(state.filter)
    val shown = (if (state.showArchive) state.archived else state.conversations).filter(filter::matches)
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 8.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (!state.showArchive) {
            state.usage?.let { usage ->
                item(key = "usage") {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
                        border = BorderStroke(1.dp, CccColors.Line),
                    ) { UsageCard(usage, Modifier.padding(12.dp)) }
                }
            }
            if (state.waiting.isNotEmpty()) {
                item(key = "waiting") { WaitingBanner(state, actions.nextWaiting) }
            }
            state.status?.update?.takeIf { it.available }?.let { update ->
                item(key = "update") { UpdateBanner(update, actions.applyUpdate) }
            }
            state.status?.androidBuild?.takeIf { appBuild in 1 until it }?.let { newest ->
                item(key = "app-older") { AppOlderBanner(appBuild, newest) }
            }
        }
        item(key = "filter") { FilterField(state.filter, actions.filter) }
        if (state.loaded && shown.isEmpty()) {
            item(key = "empty") {
                Text(
                    stringResource(
                        when {
                            filter.active -> R.string.filter_nothing
                            state.showArchive -> R.string.archive_empty
                            else -> R.string.conversations_empty
                        },
                    ),
                    Modifier.fillMaxWidth().padding(32.dp),
                    color = CccColors.Muted,
                )
            }
        }
        var group: String? = null
        shown.forEach { conversation ->
            val heading = conversation.group
            if (heading != null && heading.key != group) {
                item(key = "group:${heading.key}") { GroupHeader(heading, onGroupMenu) }
            }
            group = heading?.key
            item(key = conversation.id) { ConversationRow(conversation, listDetails) { actions.open(conversation.id) } }
        }
    }
}

@Composable
private fun DaemonLine(state: HomeState) {
    val (text, color) = when {
        !state.live && state.loaded -> stringResource(R.string.offline) to CccColors.Waiting
        state.status?.daemonRunning == true -> stringResource(R.string.daemon_running) to CccColors.Running
        state.status != null -> stringResource(R.string.daemon_stopped) to CccColors.Error
        else -> "" to CccColors.Muted
    }
    if (text.isNotEmpty()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            StatusDot(color)
            Spacer(Modifier.width(6.dp))
            Text(text, style = MaterialTheme.typography.labelMedium, color = color)
        }
    }
}

/** Who needs you, most urgent first; a tap opens the first (Alt+N in ccc). */
/** A new ccc version on origin/main, with the button that updates it (after asking). */
@Composable
private fun UpdateBanner(update: UpdateInfo, onUpdate: () -> Unit) {
    var asking by remember { mutableStateOf(false) }
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Waiting),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.update_available, update.behind), color = CccColors.Waiting,
                    fontWeight = FontWeight.Bold)
                if (update.android) {
                    Text(stringResource(R.string.update_android), style = MaterialTheme.typography.bodySmall, color = CccColors.Title)
                }
            }
            TextButton(onClick = { asking = true }) { Text(stringResource(R.string.update_button)) }
        }
    }
    if (asking) {
        AlertDialog(
            onDismissRequest = { asking = false },
            title = { Text(stringResource(R.string.update_title)) },
            text = {
                Column {
                    update.commits.forEach { Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 2) }
                    if (update.behind > update.commits.size) Text("…", color = CccColors.Muted)
                    Spacer(Modifier.height(8.dp))
                    val reason = update.reason?.takeIf { !update.canApply }
                    if (reason != null) Text(reason, color = CccColors.Error)
                    else Text(stringResource(R.string.update_confirm_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                }
            },
            confirmButton = {
                TextButton(enabled = update.canApply, onClick = { asking = false; onUpdate() }) {
                    Text(stringResource(R.string.update_do))
                }
            },
            dismissButton = { TextButton(onClick = { asking = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

/** The installed app is older than the ccc it talks to (ccc's checkout has newer app sources). */
@Composable
private fun AppOlderBanner(build: Int, newest: Int) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Title),
    ) {
        Text(stringResource(R.string.app_older, build, newest), Modifier.padding(12.dp), color = CccColors.Title,
            style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun WaitingBanner(state: HomeState, onNext: () -> Unit) {
    val first = state.waiting.first()
    val color = when (first.kind) {
        "approval" -> CccColors.Approval
        "error" -> CccColors.Error
        "limit" -> CccColors.Waiting
        else -> CccColors.Title
    }
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onNext),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, color),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.needs_you, state.waiting.size), style = MaterialTheme.typography.labelMedium,
                    color = CccColors.Muted)
                Text("${first.name} — ${first.label}", color = color, fontWeight = FontWeight.Bold, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
            }
            TextButton(onClick = onNext) { Text(stringResource(R.string.open_next)) }
        }
    }
}

@Composable
private fun FilterField(text: String, onChange: (String) -> Unit) {
    Column {
        OutlinedTextField(
            value = text,
            onValueChange = onChange,
            placeholder = { Text(stringResource(R.string.filter_hint)) },
            trailingIcon = {
                if (text.isNotEmpty()) {
                    IconButton(onClick = { onChange("") }) { Icon(Icons.Filled.Clear, stringResource(R.string.clear)) }
                }
            },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        val parsed = ListFilter.parse(text)
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            MARKERS.zip(listOf(R.string.filter_working, R.string.filter_approval, R.string.filter_error, R.string.filter_unseen))
                .forEach { (marker, label) ->
                    FilterChip(
                        selected = marker in parsed.states,
                        onClick = { onChange(toggleMarker(text, marker)) },
                        label = { Text("$marker ${stringResource(label)}") },
                    )
                }
        }
    }
}

/** The filter text with [marker] added to / taken from its markers at the start. */
internal fun toggleMarker(text: String, marker: Char): String {
    val states = ListFilter.parse(text).states
    val markers = if (marker in states) states - marker else states + marker
    val words = text.split(Regex("\\s+")).filter { it.isNotEmpty() }
        .dropWhile { token -> token.lowercase().all { it in MARKERS } }
    val prefix = MARKERS.filter { it in markers }.joinToString("")
    return (listOf(prefix).filter { it.isNotEmpty() } + words).joinToString(" ")
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun GroupHeader(group: Group, onMenu: (String) -> Unit) {
    val own = group.key.removePrefix("own:").takeIf { group.key.startsWith("own:") }
    Column(
        Modifier
            .fillMaxWidth()
            .padding(top = 12.dp)
            .combinedClickable(onClick = { own?.let(onMenu) }, onLongClick = { own?.let(onMenu) }),
    ) {
        Text(group.title, style = MaterialTheme.typography.titleSmall, color = CccColors.Title, fontWeight = FontWeight.Bold)
        HorizontalDivider(Modifier.padding(top = 4.dp), color = CccColors.Line)
    }
}

/** An own group's heading tapped: rename it (into an existing one: they merge) or delete it. */
@Composable
private fun GroupDialog(name: String, actions: ConversationsActions, onClose: () -> Unit) {
    var newName by rememberSaveable(name) { mutableStateOf(name) }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text(stringResource(R.string.group_title, name)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = newName,
                    onValueChange = { newName = it },
                    label = { Text(stringResource(R.string.group_rename)) },
                    singleLine = true,
                )
                Text(stringResource(R.string.group_delete_hint), style = MaterialTheme.typography.bodySmall,
                    color = CccColors.Muted)
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    actions.renameGroup(name, newName.trim())
                    onClose()
                },
                enabled = newName.isNotBlank() && newName.trim() != name,
            ) { Text(stringResource(R.string.save)) }
        },
        dismissButton = {
            TextButton(onClick = {
                actions.deleteGroup(name)
                onClose()
            }) { Text(stringResource(R.string.group_delete), color = CccColors.Error) }
        },
    )
}

@Composable
private fun ConversationRow(conversation: Conversation, listDetails: Set<String>, onClick: () -> Unit) {
    val state = conversation.state
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, if (conversation.needsApproval) CccColors.Approval else CccColors.Line),
    ) {
        Row(Modifier.padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            StatusDot(statusColor(state, conversation.needsApproval))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        conversation.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = if (conversation.unseen) FontWeight.Bold else FontWeight.Normal,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    if (conversation.unseen) {
                        Spacer(Modifier.width(8.dp))
                        StatusDot(CccColors.Title)
                    }
                }
                val details = buildList {
                    add(if (conversation.needsApproval) stringResource(R.string.needs_approval) else statusLabel(state))
                    if (ListDetail.PENDING in listDetails && conversation.pending > 0) {
                        add(stringResource(R.string.pending_count, conversation.pending))
                    }
                    if (conversation.unseen) add(stringResource(R.string.new_reply))
                }
                val highlighted = state != ConversationStatus.IDLE || conversation.needsApproval
                Text(
                    details.joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (highlighted) statusColor(state, conversation.needsApproval) else CccColors.Muted,
                )
                val context = conversation.context.takeIf { ListDetail.CONTEXT in listDetails }
                val git = conversation.git?.text?.takeIf { ListDetail.GIT in listDetails && it.isNotEmpty() }
                if (context != null || git != null) {
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        if (context != null) {
                            Text(
                                stringResource(R.string.context_short, context.text),
                                style = MaterialTheme.typography.bodySmall,
                                color = when (context.level) {
                                    "danger" -> CccColors.Error
                                    "warn" -> CccColors.Waiting
                                    else -> CccColors.Muted
                                },
                            )
                        }
                        if (git != null) {
                            Text(
                                git,
                                style = MaterialTheme.typography.bodySmall,
                                color = CccColors.Title,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f, fill = false),
                            )
                        }
                    }
                }
                if (ListDetail.PATH in listDetails) {
                    Text(shortPath(conversation.path), style = MaterialTheme.typography.bodySmall,
                        color = CccColors.Muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                conversation.lastError?.takeIf { state == ConversationStatus.BLOCKED_ERROR }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = CccColors.Error, maxLines = 2,
                        overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}

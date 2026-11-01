package io.github.luquas95.ccc.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.materialIcon
import androidx.compose.material.icons.materialPath
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.ui.graphics.vector.ImageVector
import io.github.luquas95.ccc.data.LiveSession

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import io.github.luquas95.ccc.data.AppRelease
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
    val tab: (HomeTab) -> Unit,
    val filter: (String) -> Unit,
    val filterState: (Char) -> Unit,
    val nextWaiting: () -> Unit,
    val renameGroup: (String, String) -> Unit,
    val deleteGroup: (String) -> Unit,
    val routines: () -> Unit,
    val analytics: () -> Unit,
    /** A prompt for the live session (id, text). */
    val promptSession: (String, String) -> Unit = { _, _ -> },
    val applyUpdate: () -> Unit = {},
    val updateApp: () -> Unit = {},
    /** The queue (tasks) of a conversation: what Enter on the TUI Dashboard opens. */
    val openQueue: (Int) -> Unit = {},
)

private val MARKERS = listOf(ListFilter.WORKING, ListFilter.APPROVAL, ListFilter.ERROR, ListFilter.UNSEEN)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationsScreen(
    state: HomeState,
    listDetails: Set<String>,
    newVersion: AppRelease? = null,
    snackbar: SnackbarHostState,
    actions: ConversationsActions,
    sessions: List<LiveSession>? = null,
    appUpdate: AppUpdateState = AppUpdateState(),
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
            if (state.tab == HomeTab.DASHBOARD || state.tab == HomeTab.CONVERSATIONS) {
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
            PrimaryScrollableTabRow(
                selectedTabIndex = state.tab.ordinal,
                containerColor = CccColors.Background,
                contentColor = CccColors.Title,
                edgePadding = 0.dp,
            ) {
                listOf(
                    HomeTab.DASHBOARD to stringResource(R.string.dashboard),
                    HomeTab.CONVERSATIONS to "${stringResource(R.string.conversations)} (${state.conversations.size})",
                    HomeTab.ARCHIVE to "${stringResource(R.string.archive)} (${state.archived.size})",
                    HomeTab.SESSIONS to stringResource(R.string.live_sessions),
                ).forEach { (tab, title) ->
                    Tab(selected = state.tab == tab, onClick = { actions.tab(tab) }, text = { Text(title, maxLines = 1) })
                }
            }
            PullToRefreshBox(
                isRefreshing = state.refreshing,
                onRefresh = actions.refresh,
                modifier = Modifier.fillMaxSize(),
            ) {
                when (state.tab) {
                    HomeTab.DASHBOARD -> Dashboard(state, newVersion, actions, appUpdate)
                    HomeTab.SESSIONS -> LiveSessionsList(sessions, actions.promptSession)
                    else -> ConversationList(state, listDetails, newVersion, actions, appUpdate) { groupMenu = it }
                }
            }
        }
    }
    groupMenu?.let { name -> GroupDialog(name, actions, onClose = { groupMenu = null }) }
}

@Composable
private fun ConversationList(
    state: HomeState,
    listDetails: Set<String>,
    newVersion: AppRelease? = null,
    actions: ConversationsActions,
    appUpdate: AppUpdateState,
    onGroupMenu: (String) -> Unit,
) {
    val filter = ListFilter.of(state.filterStates, state.filter)
    val shown = (if (state.showArchive) state.archived else state.conversations).filter(filter::matches)
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 8.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (!state.showArchive) banners(state, newVersion, actions, appUpdate)
        item(key = "filter") { SearchField(state.filter, state.filterStates, actions.filter, actions.filterState) }
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

/** What may need you above the lists: the limits, who waits, a new ccc, a new app. */
private fun LazyListScope.banners(state: HomeState, newVersion: AppRelease?, actions: ConversationsActions, appUpdate: AppUpdateState) {
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
    newVersion?.let { release ->
        item(key = "app-newer") { NewAppBanner(release, appUpdate, actions.updateApp) }
    }
}

/** The TUI's Dashboard: the overview line, then every conversation with its status, queue, tokens today, context, git and folder. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Dashboard(state: HomeState, newVersion: AppRelease?, actions: ConversationsActions, appUpdate: AppUpdateState) {
    val all = state.conversations
    val blocked = all.count { it.state == ConversationStatus.BLOCKED_ERROR }
    val running = all.count { it.state == ConversationStatus.RUNNING }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 8.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        banners(state, newVersion, actions, appUpdate)
        item(key = "overview") {
            Card(
                Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
                border = BorderStroke(1.dp, CccColors.Line),
            ) {
                FlowRow(
                    Modifier.padding(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(20.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Stat(all.size.toString(), stringResource(R.string.dashboard_conversations), MaterialTheme.colorScheme.onSurface)
                    Stat(running.toString(), stringResource(R.string.dashboard_running),
                        if (running > 0) CccColors.Running else CccColors.Muted)
                    Stat(all.sumOf { it.pending }.toString(), stringResource(R.string.dashboard_pending), MaterialTheme.colorScheme.onSurface)
                    Stat(blocked.toString(), stringResource(R.string.dashboard_blocked),
                        if (blocked > 0) CccColors.Error else CccColors.Muted)
                    Stat(state.waiting.size.toString(), stringResource(R.string.dashboard_waiting),
                        if (state.waiting.isNotEmpty()) CccColors.Waiting else CccColors.Muted)
                    Stat(tokenText(all.sumOf { it.tokensToday }), stringResource(R.string.dashboard_tokens), MaterialTheme.colorScheme.onSurface)
                }
            }
        }
        if (state.loaded && all.isEmpty()) {
            item(key = "empty") {
                Text(stringResource(R.string.conversations_empty), Modifier.fillMaxWidth().padding(32.dp), color = CccColors.Muted)
            }
        }
        items(all, key = { "dash:${it.id}" }) { conversation -> DashboardRow(conversation) { actions.openQueue(conversation.id) } }
    }
}

@Composable
private fun Stat(value: String, label: String, color: Color) {
    Column {
        Text(value, style = MaterialTheme.typography.titleLarge, color = color, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = CccColors.Muted)
    }
}

/** 1 234 -> "1.2k", 3 400 000 -> "3.4M". */
internal fun tokenText(tokens: Long): String = when {
    tokens >= 1_000_000 -> "%.1fM".format(java.util.Locale.ROOT, tokens / 1_000_000.0)
    tokens >= 1_000 -> "%.1fk".format(java.util.Locale.ROOT, tokens / 1_000.0)
    else -> tokens.toString()
}

@Composable
private fun DashboardRow(conversation: Conversation, onClick: () -> Unit) {
    val state = conversation.state
    val color = statusColor(state, conversation.needsApproval)
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, if (conversation.needsApproval) CccColors.Approval else CccColors.Line),
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusDot(color)
                Spacer(Modifier.width(10.dp))
                Text(conversation.name, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.width(8.dp))
                Text(
                    if (conversation.needsApproval) stringResource(R.string.needs_approval) else statusLabel(state),
                    style = MaterialTheme.typography.labelMedium, color = color,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.pending_count, conversation.pending), style = MaterialTheme.typography.bodySmall,
                    color = CccColors.Muted)
                Text(stringResource(R.string.tokens_today_short, tokenText(conversation.tokensToday)),
                    style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                conversation.context?.let { context ->
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
            }
            conversation.git?.text?.takeIf { it.isNotEmpty() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = CccColors.Title, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Text(shortPath(conversation.path), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted, maxLines = 1,
                overflow = TextOverflow.Ellipsis)
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

/** A newer release of the app on GitHub: the button downloads it and hands it to the installer. */
@Composable
private fun NewAppBanner(release: AppRelease, update: AppUpdateState, onUpdate: () -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Title),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.app_new_version, release.version), color = CccColors.Title,
                        style = MaterialTheme.typography.bodyMedium)
                    if (update.busy) {
                        Text(stringResource(R.string.app_downloading), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                    }
                }
                TextButton(onClick = onUpdate, enabled = !update.busy) { Text(stringResource(R.string.app_update_button)) }
            }
            if (update.busy) {
                LinearProgressIndicator(progress = { update.progress }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    color = CccColors.Title)
            }
        }
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

/**
 * The search over the list (name and folder; case and diacritics don't matter) with, to its right, the
 * filter by state (ListFilter's markers).
 */
@Composable
private fun SearchField(words: String, states: Set<Char>, onChange: (String) -> Unit, onState: (Char) -> Unit) {
    var menu by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = words,
            onValueChange = onChange,
            placeholder = { Text(stringResource(R.string.filter_hint)) },
            leadingIcon = { Icon(Icons.Filled.Search, null) },
            trailingIcon = {
                if (words.isNotEmpty()) {
                    IconButton(onClick = { onChange("") }) {
                        Icon(Icons.Filled.Clear, stringResource(R.string.clear))
                    }
                }
            },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
        Box {
            IconButton(onClick = { menu = true }) {
                BadgedBox(badge = { if (states.isNotEmpty()) Badge { Text(states.size.toString()) } }) {
                    Icon(FilterListIcon, stringResource(R.string.filter_by_state),
                        tint = if (states.isNotEmpty()) CccColors.Title else LocalContentColor.current)
                }
            }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                MARKERS.zip(listOf(R.string.filter_working, R.string.filter_approval, R.string.filter_error, R.string.filter_unseen))
                    .forEach { (marker, label) ->
                        DropdownMenuItem(
                            text = { Text("$marker ${stringResource(label)}") },
                            leadingIcon = { if (marker in states) Icon(Icons.Filled.Check, null, tint = CccColors.Title) },
                            onClick = { onState(marker) },
                        )
                    }
            }
        }
    }
}

private val FilterListIcon: ImageVector = materialIcon("Filled.FilterList") {
    materialPath {
        moveTo(10f, 18f); horizontalLineToRelative(4f); verticalLineToRelative(-2f); horizontalLineToRelative(-4f); close()
        moveTo(3f, 6f); verticalLineToRelative(2f); horizontalLineToRelative(18f); verticalLineTo(6f); horizontalLineTo(3f); close()
        moveTo(6f, 13f); horizontalLineToRelative(12f); verticalLineToRelative(-2f); horizontalLineTo(6f); close()
    }
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

/** What "Update now" ended with — success, or why not — until the user closes it. */
@Composable
fun UpdateOutcomeDialog(outcome: AppViewModel.UpdateOutcome, onClose: () -> Unit) {
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text(stringResource(if (outcome.ok) R.string.update_done_title else R.string.update_failed_title)) },
        text = { Text(outcome.text) },
        confirmButton = { TextButton(onClick = onClose) { Text(stringResource(R.string.ok)) } },
    )
}

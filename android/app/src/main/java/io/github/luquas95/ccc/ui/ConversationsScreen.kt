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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.Conversation
import io.github.luquas95.ccc.ui.theme.CccColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationsScreen(
    state: HomeState,
    snackbar: SnackbarHostState,
    onOpen: (Int) -> Unit,
    onApprovals: () -> Unit,
    onSettings: () -> Unit,
    onNew: () -> Unit,
    onRefresh: () -> Unit,
) {
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
                    IconButton(onClick = onApprovals) {
                        BadgedBox(badge = {
                            if (state.permissions.isNotEmpty()) Badge { Text(state.permissions.size.toString()) }
                        }) { Icon(Icons.Filled.Notifications, stringResource(R.string.approvals)) }
                    }
                    IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, stringResource(R.string.settings)) }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CccColors.Background),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onNew,
                icon = { Icon(Icons.Filled.Add, null) },
                text = { Text(stringResource(R.string.new_conversation)) },
                containerColor = CccColors.Claude,
                contentColor = androidx.compose.ui.graphics.Color.Black,
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = onRefresh,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 12.dp, end = 12.dp, bottom = 96.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                state.usage?.let { usage ->
                    item(key = "usage") {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
                            border = BorderStroke(1.dp, CccColors.Line),
                        ) { UsageCard(usage, Modifier.padding(12.dp)) }
                    }
                }
                if (state.permissions.isNotEmpty()) {
                    item(key = "approvals") { ApprovalsBanner(state.permissions.size, onApprovals) }
                }
                if (state.loaded && state.conversations.isEmpty()) {
                    item(key = "empty") {
                        Text(
                            stringResource(R.string.conversations_empty),
                            Modifier.fillMaxWidth().padding(32.dp),
                            color = CccColors.Muted,
                        )
                    }
                }
                var group: String? = null
                state.conversations.forEach { conversation ->
                    val title = conversation.group?.title
                    if (title != null && title != group) {
                        item(key = "group:${conversation.group.key}") { GroupHeader(title) }
                    }
                    group = title
                    item(key = conversation.id) { ConversationRow(conversation) { onOpen(conversation.id) } }
                }
            }
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

@Composable
private fun ApprovalsBanner(count: Int, onClick: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Approval),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Notifications, null, tint = CccColors.Approval)
            Spacer(Modifier.width(12.dp))
            Text(
                "${stringResource(R.string.approvals)}: $count",
                color = CccColors.Approval,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
private fun GroupHeader(title: String) {
    Column(Modifier.padding(top = 12.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall, color = CccColors.Title, fontWeight = FontWeight.Bold)
        HorizontalDivider(Modifier.padding(top = 4.dp), color = CccColors.Line)
    }
}

@Composable
private fun ConversationRow(conversation: Conversation, onClick: () -> Unit) {
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
                        Box(Modifier) { StatusDot(CccColors.Title) }
                    }
                }
                val details = buildList {
                    add(if (conversation.needsApproval) stringResource(R.string.needs_approval) else statusLabel(state))
                    if (conversation.pending > 0) add(stringResource(R.string.pending_count, conversation.pending))
                    if (conversation.unseen) add(stringResource(R.string.new_reply))
                }
                Text(
                    details.joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = statusColor(state, conversation.needsApproval).takeIf {
                        state != io.github.luquas95.ccc.data.ConversationStatus.IDLE || conversation.needsApproval
                    } ?: CccColors.Muted,
                )
                conversation.lastError?.takeIf { state == io.github.luquas95.ccc.data.ConversationStatus.BLOCKED_ERROR }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = CccColors.Error, maxLines = 2,
                        overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}

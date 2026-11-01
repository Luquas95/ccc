package io.github.luquas95.ccc.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import io.github.luquas95.ccc.PortraitCaptureActivity
import com.journeyapps.barcodescanner.ScanContract
import io.github.luquas95.ccc.data.Pairing
import io.github.luquas95.ccc.data.PairingInvite
import com.journeyapps.barcodescanner.ScanOptions
import io.github.luquas95.ccc.data.Device
import io.github.luquas95.ccc.data.Language
import androidx.compose.ui.res.stringResource
import androidx.core.content.ContextCompat
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import kotlinx.coroutines.delay
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.LaunchGroup
import io.github.luquas95.ccc.data.ListDetail
import io.github.luquas95.ccc.data.NewConversation
import io.github.luquas95.ccc.data.Permission
import io.github.luquas95.ccc.ui.theme.CccColors

private const val FROM_PR = "session_from_pr"
private const val RESUME = "session_resume"
private const val SESSION_NEW = "session_new"
private const val FORK = "fork"
private const val MCP_SELECT = "mcp_select"
private const val MCP_PREFIX = "mcp:"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TopBar(title: String, onBack: (() -> Unit)?) {
    TopAppBar(
        title = { Text(title) },
        navigationIcon = {
            if (onBack != null) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(containerColor = CccColors.Background),
    )
}

@Composable
fun ApprovalsScreen(
    permissions: List<Permission>,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onOpen: (Int) -> Unit,
    onDecide: (Permission, String) -> Unit,
) {
    Scaffold(
        topBar = { TopBar(stringResource(R.string.approvals), onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (permissions.isEmpty()) {
                item { Text(stringResource(R.string.no_approvals), color = CccColors.Muted, modifier = Modifier.padding(16.dp)) }
            }
            items(permissions, key = { it.id }) { permission ->
                Column {
                    ApprovalCard(permission, permission.conversation, onDecide = { onDecide(permission, it) })
                    androidx.compose.material3.TextButton(onClick = { onOpen(permission.conversationId) }) {
                        Text(permission.conversation ?: "#${permission.conversationId}")
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun NewConversationScreen(
    state: NewConversationState,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onLoadSessions: (String) -> Unit,
    onLoadMcpServers: (String) -> Unit,
    onCreate: (NewConversation) -> Unit,
) {
    var sessionId by rememberSaveable { mutableStateOf("") }
    var path by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("") }
    var pr by rememberSaveable { mutableStateOf("") }
    var prompt by rememberSaveable { mutableStateOf("") }
    var remote by rememberSaveable { mutableStateOf(false) }
    var autoContinue by rememberSaveable { mutableStateOf(true) }
    var selection by rememberSaveable { mutableStateOf(emptyList<String>()) }
    val options = state.options
    // As ccc's window: the last choice first, else the defaults.
    LaunchedEffect(options, state.presets) {
        if (options != null && selection.isEmpty()) {
            val last = state.presets?.last
            selection = last?.options ?: options.default
            last?.let { remote = it.remoteControl; autoContinue = it.autoContinue }
        }
    }
    val resume = RESUME in selection
    LaunchedEffect(path, resume) {
        if (resume) {
            delay(FOLDER_DELAY_MS)  // the path is typed letter by letter: ask once it rests
            onLoadSessions(path.trim())
        }
    }
    val mcpOn = MCP_SELECT in selection
    LaunchedEffect(path, mcpOn) {
        if (mcpOn) {
            delay(FOLDER_DELAY_MS)
            onLoadMcpServers(path.trim())
        }
    }
    Scaffold(
        topBar = { TopBar(stringResource(R.string.new_conversation), onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = path,
                onValueChange = { path = it },
                label = { Text(stringResource(R.string.folder)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
            )
            if (state.projects.isNotEmpty()) {
                // As the TUI's "Recent directories": whole paths, one tap fills the folder.
                Text(stringResource(R.string.recent_folders), style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
                Column {
                    state.projects.forEach { project ->
                        Text(
                            project,
                            Modifier.fillMaxWidth().clickable { path = project }.padding(vertical = 8.dp, horizontal = 4.dp),
                            fontFamily = FontFamily.Monospace,
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (path == project) CccColors.Title else MaterialTheme.colorScheme.onSurface,
                            fontWeight = if (path == project) FontWeight.Bold else FontWeight.Normal,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        HorizontalDivider(color = CccColors.Line)
                    }
                }
            }
            val presets = state.presets?.presets.orEmpty()
            if (presets.isNotEmpty()) {
                Text(stringResource(R.string.launch_presets), style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    presets.forEach { preset ->
                        FilterChip(
                            selected = false,
                            onClick = {
                                selection = preset.options
                                remote = preset.remoteControl
                                autoContinue = preset.autoContinue
                            },
                            label = { Text(preset.name.orEmpty()) },
                            colors = chipColors(),
                        )
                    }
                }
            }
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text(stringResource(R.string.name_optional)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            if (state.folderDenied.isNotEmpty() && state.deniedFor == path.trim()) {
                Text(state.folderDenied, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            options?.groups?.forEach { group ->
                OptionGroup(group, selection) { selection = toggle(group, selection, it, options.groups) }
                if (group.key == "mcp" && mcpOn) {
                    McpServers(state, path.trim(), selection) { selection = toggle(group, selection, MCP_PREFIX + it, options.groups) }
                }
            }
            if (resume) {
                SessionList(state, path.trim(), sessionId) { sessionId = it }
            }
            if (FROM_PR in selection) {
                OutlinedTextField(
                    value = pr,
                    onValueChange = { pr = it },
                    label = { Text(stringResource(R.string.pull_request)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            SwitchRow(stringResource(R.string.remote_control), remote) { remote = it }
            SwitchRow(stringResource(R.string.auto_continue), autoContinue) { autoContinue = it }
            OutlinedTextField(
                value = prompt,
                onValueChange = { prompt = it },
                label = { Text(stringResource(R.string.first_message)) },
                minLines = 3,
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    onCreate(NewConversation(path.trim(), name.trim(), selection, pr.trim(),
                        if (resume) sessionId else "", remote, autoContinue, prompt))
                },
                enabled = path.isNotBlank() && !state.creating && (!resume || sessionId.isNotEmpty()),
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = CccColors.Claude, contentColor = Color.Black),
            ) {
                if (state.creating) CircularProgressIndicator(Modifier.height(24.dp)) else Text(stringResource(R.string.start))
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun OptionGroup(group: LaunchGroup, selection: List<String>, onToggle: (String) -> Unit) {
    val shown = group.options
    if (group.key == "session_extra" && SESSION_NEW in selection) return  // nothing to copy from
    Column {
        if (group.title.isNotEmpty()) {
            Text(group.title, style = MaterialTheme.typography.titleSmall, color = CccColors.Title, fontWeight = FontWeight.Bold)
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            shown.forEach { option ->
                FilterChip(
                    selected = option.key in selection,
                    onClick = { onToggle(option.key) },
                    label = { Text(option.label) },
                    colors = chipColors(),
                )
            }
        }
    }
}

/** How long the typed folder must rest before the app asks the server about it. */
private const val FOLDER_DELAY_MS = 700L

/** The MCP servers configured for the folder (plus ticked ones that are gone): tick those the conversation may use. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun McpServers(state: NewConversationState, path: String, selection: List<String>, onToggle: (String) -> Unit) {
    val chosen = selection.filter { it.startsWith(MCP_PREFIX) }.map { it.removePrefix(MCP_PREFIX) }
    val names = (if (state.mcpFor == path) state.mcpServers else emptyList()).union(chosen).sorted()
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        names.forEach { name ->
            FilterChip(
                selected = name in chosen,
                onClick = { onToggle(name) },
                label = { Text(name) },
                colors = chipColors(),
            )
        }
    }
}

/**
 * As launch_options.toggle in ccc: one per exclusive group, required groups never empty.
 * A server key ("mcp:<name>") is not in the catalogue: ticking one turns "only selected
 * MCP servers" on, unticking that mode forgets the servers.
 */
internal fun toggle(group: LaunchGroup, selection: List<String>, key: String, groups: List<LaunchGroup>): List<String> {
    val keys = group.options.map { it.key }.toSet()
    val result = selection.toMutableList()
    if (key.startsWith(MCP_PREFIX)) {
        if (key in result) result.remove(key) else result.add(key)
        if (MCP_SELECT !in result) result.add(MCP_SELECT)
        return ordered(result, groups)
    }
    if (key == MCP_SELECT && key in result) result.removeAll { it.startsWith(MCP_PREFIX) }
    if (key in result) {
        if (!group.required) result.remove(key)
    } else {
        if (group.exclusive) result.removeAll(keys)
        result.add(key)
    }
    if (SESSION_NEW in result) result.remove(FORK)
    return ordered(result, groups)
}

/** In catalogue order, then the MCP servers. */
private fun ordered(result: List<String>, groups: List<LaunchGroup>): List<String> =
    groups.flatMap { g -> g.options.map { it.key } }.filter { it in result } + result.filter { it.startsWith(MCP_PREFIX) }.sorted()

/** The folder's Claude Code sessions, newest first, to resume one. */
@Composable
private fun SessionList(state: NewConversationState, path: String, chosen: String, onChoose: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(R.string.sessions), style = MaterialTheme.typography.titleSmall, color = CccColors.Title,
            fontWeight = FontWeight.Bold)
        if (state.sessionsFor == path && state.sessions.isEmpty()) {
            Text(stringResource(R.string.sessions_none), color = CccColors.Muted, style = MaterialTheme.typography.bodySmall)
        }
        state.sessions.take(20).forEach { session ->
            Row(
                Modifier.fillMaxWidth().clickable { onChoose(session.sessionId) },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = session.sessionId == chosen, onClick = { onChoose(session.sessionId) })
                Column {
                    Text(session.firstPrompt, maxLines = 2, overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.bodyMedium)
                    Text(
                        listOfNotNull(shortTime(session.modified), stringResource(R.string.session_messages, session.messages))
                            .joinToString(" · "),
                        style = MaterialTheme.typography.labelSmall, color = CccColors.Muted,
                    )
                }
            }
        }
    }
}

@Composable
fun SearchScreen(
    state: SearchState,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onSearch: (String) -> Unit,
    onOpen: (Int) -> Unit,
) {
    Scaffold(
        topBar = { TopBar(stringResource(R.string.search), onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp)) {
            OutlinedTextField(
                value = state.query,
                onValueChange = onSearch,
                placeholder = { Text(stringResource(R.string.search_hint)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            if (state.searching) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 4.dp))
            LazyColumn(contentPadding = PaddingValues(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.query.isNotBlank() && !state.searching && state.hits.isEmpty()) {
                    item { Text(stringResource(R.string.search_nothing), color = CccColors.Muted, modifier = Modifier.padding(16.dp)) }
                }
                items(state.hits) { hit ->
                    Column(
                        Modifier.fillMaxWidth().clickable { onOpen(hit.conversationId) }.padding(vertical = 6.dp),
                    ) {
                        Row {
                            Text(hit.name, color = CccColors.Title, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                listOfNotNull(
                                    stringResource(if (hit.kind == "human") R.string.you else R.string.claude),
                                    shortTime(hit.time),
                                ).joinToString(" · "),
                                color = CccColors.Muted,
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                        Text(hit.snippet, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun chipColors() = FilterChipDefaults.filterChipColors(
    selectedContainerColor = CccColors.Selection,
    selectedLabelColor = Color.White,
)

@Composable
private fun SwitchRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

/** A phone signed out before: when it joined and was last seen, and when and how it was signed out. Read only. */
@Composable
private fun DeviceHistoryRow(device: Device) {
    val how = stringResource(
        when (device.revokedBy) {
            "app" -> R.string.revoked_app
            "computer" -> R.string.revoked_computer
            "token" -> R.string.revoked_token
            else -> R.string.revoked_unknown
        },
    )
    val seen = shortTime(device.lastSeenAt) ?: stringResource(R.string.device_never)
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(device.name)
        Text(stringResource(R.string.history_signed_out, shortTime(device.revokedAt).orEmpty(), how),
            style = MaterialTheme.typography.bodySmall, color = CccColors.Error)
        Text(
            stringResource(R.string.history_joined, shortTime(device.createdAt).orEmpty()) + " · " +
                listOf(seen, device.lastIp).filter { it.isNotBlank() }.joinToString(" · "),
            style = MaterialTheme.typography.bodySmall, color = CccColors.Muted,
        )
    }
}

/** A phone signed in to ccc: its name, when and from where it was last seen, and a way to sign it out. */
@Composable
private fun DeviceRow(device: Device, onSignOut: (Device) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(
                if (device.current) stringResource(R.string.device_this, device.name) else device.name,
                fontWeight = if (device.current) FontWeight.Bold else FontWeight.Normal,
            )
            val seen = shortTime(device.lastSeenAt) ?: stringResource(R.string.device_never)
            Text(listOf(seen, device.lastIp).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
        }
        TextButton(onClick = { onSignOut(device) }) {
            Text(stringResource(R.string.setup_sign_out), color = CccColors.Error)
        }
    }
}

/** Where this phone is connected: the computer's address and what ccc knows of this phone, with the way out. */
@Composable
private fun ConnectionCard(server: String, device: Device?, onDisconnect: () -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Line),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(stringResource(R.string.connection_connected), color = CccColors.Title, fontWeight = FontWeight.Bold)
            Text(server, style = MaterialTheme.typography.bodyLarge)
            if (device != null) {
                val never = stringResource(R.string.device_never)
                listOf(
                    R.string.connection_device to device.name,
                    R.string.connection_since to (shortTime(device.createdAt) ?: never),
                    R.string.connection_last_seen to (shortTime(device.lastSeenAt) ?: never),
                    R.string.connection_ip to device.lastIp,
                ).filter { it.second.isNotBlank() }.forEach { (label, value) ->
                    Row {
                        Text(stringResource(label), Modifier.width(110.dp), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                        Text(value, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            OutlinedButton(onClick = onDisconnect, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text(stringResource(R.string.setup_disconnect), color = CccColors.Error)
            }
        }
    }
}

/** The app's own language, apart from the phone's, the computer's and ccc's: a drop-down menu. */
@Composable
fun LanguageChoice(language: String, onLanguage: (String) -> Unit) {
    Picker(
        stringResource(R.string.app_language), language,
        listOf("" to stringResource(R.string.language_system)) + Language.CHOICES,
    ) { if (it != language) onLanguage(it) }
    Text(stringResource(R.string.app_language_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
}

@Composable
fun SetupScreen(
    server: String,
    signedIn: Boolean,
    notifications: Boolean,
    listDetails: Set<String>,
    onListDetail: (String, Boolean) -> Unit,
    snackbar: SnackbarHostState,
    onBack: (() -> Unit)?,
    onConnect: (String, String, (Boolean) -> Unit) -> Unit,
    onNotifications: (Boolean) -> Unit,
    onSignOut: () -> Unit,
    devices: List<Device>? = null,
    deviceHistory: List<Device> = emptyList(),
    onDevices: () -> Unit = {},
    onSignOutDevice: (Device) -> Unit = {},
    invite: PairingInvite? = null,
    currentServer: String = "",
    onScan: (String) -> Unit = {},
    onPair: ((Boolean) -> Unit) -> Unit = {},
    onInviteDismissed: () -> Unit = {},
    language: String = "",
    onLanguage: (String) -> Unit = {},
) {
    val context = LocalContext.current
    var address by rememberSaveable { mutableStateOf(server) }
    var token by rememberSaveable { mutableStateOf("") }
    var busy by rememberSaveable { mutableStateOf(false) }
    val focus = LocalFocusManager.current
    // Signing out is one tap away from a slip: ask first (this phone: a stronger question).
    var signOutAsk by remember { mutableStateOf<Device?>(null) }
    var signOutSelfAsk by remember { mutableStateOf(false) }
    val connect = {
        if (address.isNotBlank() && token.isNotBlank() && !busy) {
            focus.clearFocus()
            busy = true
            onConnect(address, token) { busy = false }
        }
    }
    // The QR code of `ccc api pair`: the library's own screen asks for the camera and reads it.
    val scan = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let(onScan)
    }
    signOutAsk?.let { device ->
        AlertDialog(
            onDismissRequest = { signOutAsk = null },
            title = { Text(stringResource(R.string.sign_out_title)) },
            text = {
                Text(stringResource(if (device.current) R.string.sign_out_this else R.string.sign_out_other, device.name))
            },
            confirmButton = {
                TextButton(onClick = { signOutAsk = null; onSignOutDevice(device) }) {
                    Text(stringResource(R.string.setup_sign_out), color = CccColors.Error)
                }
            },
            dismissButton = { TextButton(onClick = { signOutAsk = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
    if (signOutSelfAsk) {
        AlertDialog(
            onDismissRequest = { signOutSelfAsk = false },
            title = { Text(stringResource(R.string.sign_out_title)) },
            text = { Text(stringResource(R.string.sign_out_this_phone)) },
            confirmButton = {
                TextButton(onClick = { signOutSelfAsk = false; onSignOut() }) {
                    Text(stringResource(R.string.setup_sign_out), color = CccColors.Error)
                }
            },
            dismissButton = { TextButton(onClick = { signOutSelfAsk = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
    if (invite != null) {
        val origin = remember(invite) { Pairing.origin(invite.server).orEmpty() }
        val other = signedIn && Pairing.origin(currentServer) != origin
        AlertDialog(
            onDismissRequest = onInviteDismissed,
            title = { Text(stringResource(R.string.pair_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(R.string.pair_text, origin), fontWeight = FontWeight.Bold)
                    if (other) Text(stringResource(R.string.pair_other, currentServer), color = CccColors.Error)
                }
            },
            confirmButton = {
                TextButton(onClick = { busy = true; onPair { busy = false } }) { Text(stringResource(R.string.pair_yes)) }
            },
            dismissButton = { TextButton(onClick = onInviteDismissed) { Text(stringResource(R.string.cancel)) } },
        )
    }
    LaunchedEffect(signedIn) { if (signedIn) onDevices() }
    // Android 13+ asks before an app may notify; on a yes, watching starts.
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) onNotifications(true)
    }
    Scaffold(
        topBar = { TopBar(stringResource(if (signedIn) R.string.connection else R.string.setup_title), onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (!signedIn) {
                Text("ccc", style = MaterialTheme.typography.displaySmall, color = CccColors.Accent, fontWeight = FontWeight.Bold)
            } else {
                ConnectionCard(server, devices?.firstOrNull { it.current }) { signOutSelfAsk = true }
            }
            LanguageChoice(language, onLanguage)
            if (!signedIn) {
            Text(stringResource(R.string.setup_intro), style = MaterialTheme.typography.bodyMedium, color = CccColors.Muted)
            Button(
                onClick = {
                    scan.launch(ScanOptions().apply {
                        setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                        setPrompt(context.getString(R.string.scan_prompt))
                        setBeepEnabled(false)
                        setOrientationLocked(true)
                        setCaptureActivity(PortraitCaptureActivity::class.java)
                    })
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) { Text(stringResource(R.string.scan_qr)) }
            Text(stringResource(R.string.scan_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
            Text(stringResource(R.string.setup_manual), style = MaterialTheme.typography.titleSmall,
                color = CccColors.Title, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = address,
                onValueChange = { address = it },
                label = { Text(stringResource(R.string.setup_server)) },
                placeholder = { Text(stringResource(R.string.setup_server_hint)) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = token,
                onValueChange = { token = it },
                label = { Text(stringResource(R.string.setup_token)) },
                placeholder = { Text(stringResource(R.string.setup_token_hint)) },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { connect() }),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = { connect() },
                enabled = address.isNotBlank() && token.isNotBlank() && !busy,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                if (busy) CircularProgressIndicator(Modifier.height(24.dp)) else Text(stringResource(R.string.setup_connect))
            }
            }
            if (signedIn) {
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.devices), style = MaterialTheme.typography.titleSmall,
                    color = CccColors.Title, fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.devices_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                devices?.forEach { device -> DeviceRow(device) { signOutAsk = it } }
                var showHistory by rememberSaveable { mutableStateOf(false) }
                TextButton(onClick = { showHistory = !showHistory }) {
                    Text(stringResource(if (showHistory) R.string.history_hide else R.string.history_show, deviceHistory.size))
                }
                if (showHistory) {
                    Text(stringResource(R.string.history_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                    if (deviceHistory.isEmpty()) Text(stringResource(R.string.history_empty), color = CccColors.Muted)
                    deviceHistory.forEach { DeviceHistoryRow(it) }
                }
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.notifications), style = MaterialTheme.typography.titleSmall,
                    color = CccColors.Title, fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.notifications_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.notifications_on), Modifier.weight(1f))
                    Switch(checked = notifications, onCheckedChange = { on ->
                        val allowed = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                            PackageManager.PERMISSION_GRANTED
                        if (on && !allowed) ask.launch(Manifest.permission.POST_NOTIFICATIONS) else onNotifications(on)
                    })
                }
                OutlinedButton(
                    onClick = { context.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.battery)) }
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.list_details), style = MaterialTheme.typography.titleSmall,
                    color = CccColors.Title, fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.list_details_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                listOf(
                    ListDetail.PENDING to R.string.detail_pending,
                    ListDetail.CONTEXT to R.string.detail_context,
                    ListDetail.GIT to R.string.detail_git,
                    ListDetail.PATH to R.string.detail_path,
                ).forEach { (key, label) ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(label), Modifier.weight(1f))
                        Switch(checked = key in listDetails, onCheckedChange = { on -> onListDetail(key, on) })
                    }
                }
            }
        }
    }
}

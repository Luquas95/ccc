package io.github.luquas95.ccc.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.LaunchGroup
import io.github.luquas95.ccc.data.NewConversation
import io.github.luquas95.ccc.data.Permission
import io.github.luquas95.ccc.ui.theme.CccColors

/** Options the phone doesn't offer: resuming needs a list of the folder's sessions. */
private val HIDDEN_OPTIONS = setOf("session_resume")
private const val FROM_PR = "session_from_pr"
private const val SESSION_NEW = "session_new"
private const val FORK = "fork"

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
    onCreate: (NewConversation) -> Unit,
) {
    var path by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("") }
    var pr by rememberSaveable { mutableStateOf("") }
    var prompt by rememberSaveable { mutableStateOf("") }
    var remote by rememberSaveable { mutableStateOf(false) }
    var autoContinue by rememberSaveable { mutableStateOf(true) }
    var selection by rememberSaveable { mutableStateOf(emptyList<String>()) }
    val options = state.options
    LaunchedEffect(options) {
        if (options != null && selection.isEmpty()) selection = options.default
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
                Text(stringResource(R.string.recent_folders), style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.projects.forEach { project ->
                        FilterChip(
                            selected = path == project,
                            onClick = { path = project },
                            label = { Text(project.substringAfterLast('/').ifEmpty { project }) },
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
            options?.groups?.forEach { group ->
                OptionGroup(group, selection) { selection = toggle(group, selection, it, options.groups) }
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
                    onCreate(NewConversation(path.trim(), name.trim(), selection, pr.trim(), remote, autoContinue, prompt))
                },
                enabled = path.isNotBlank() && !state.creating,
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
    val shown = group.options.filter { it.key !in HIDDEN_OPTIONS }
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

/** As launch_options.toggle in ccc: one per exclusive group, required groups never empty. */
internal fun toggle(group: LaunchGroup, selection: List<String>, key: String, groups: List<LaunchGroup>): List<String> {
    val keys = group.options.map { it.key }.toSet()
    val result = selection.toMutableList()
    if (key in result) {
        if (!group.required) result.remove(key)
    } else {
        if (group.exclusive) result.removeAll(keys)
        result.add(key)
    }
    if (SESSION_NEW in result) result.remove(FORK)
    return groups.flatMap { g -> g.options.map { it.key } }.filter { it in result }
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

@Composable
fun SetupScreen(
    server: String,
    signedIn: Boolean,
    snackbar: SnackbarHostState,
    onBack: (() -> Unit)?,
    onConnect: (String, String, (Boolean) -> Unit) -> Unit,
    onSignOut: () -> Unit,
) {
    var address by rememberSaveable { mutableStateOf(server) }
    var token by rememberSaveable { mutableStateOf("") }
    var busy by rememberSaveable { mutableStateOf(false) }
    Scaffold(
        topBar = { TopBar(stringResource(if (signedIn) R.string.settings else R.string.setup_title), onBack) },
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
                Text(stringResource(R.string.setup_connected_to, server), color = CccColors.Muted)
            }
            Text(stringResource(R.string.setup_intro), style = MaterialTheme.typography.bodyMedium, color = CccColors.Muted)
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
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    busy = true
                    onConnect(address, token) { busy = false }
                },
                enabled = address.isNotBlank() && token.isNotBlank() && !busy,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                if (busy) CircularProgressIndicator(Modifier.height(24.dp)) else Text(stringResource(R.string.setup_connect))
            }
            if (signedIn) {
                Spacer(Modifier.height(24.dp))
                OutlinedButton(onClick = onSignOut, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.setup_sign_out), color = CccColors.Error)
                }
            }
        }
    }
}

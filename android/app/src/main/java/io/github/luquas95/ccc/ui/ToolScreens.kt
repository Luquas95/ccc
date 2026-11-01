package io.github.luquas95.ccc.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.Analytics
import io.github.luquas95.ccc.data.CccSettings
import io.github.luquas95.ccc.data.Conversation
import io.github.luquas95.ccc.data.LiveSession
import io.github.luquas95.ccc.data.NotifyCategory
import io.github.luquas95.ccc.data.PromptPreset
import io.github.luquas95.ccc.data.Routine
import io.github.luquas95.ccc.data.Routines
import io.github.luquas95.ccc.ui.theme.CccColors
import java.time.YearMonth
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

private fun tokens(n: Long): String = "%,d".format(n)

// --- routines --------------------------------------------------------------------------------

/** What the routines screen can do. */
class RoutinesActions(
    val back: () -> Unit,
    val save: (Routine) -> Unit,
    val delete: (Int) -> Unit,
    val enable: (Int, Boolean) -> Unit,
    val run: (Int) -> Unit,
)

/** Prompts queued on a schedule (o in ccc). */
@Composable
fun RoutinesScreen(state: Routines?, conversations: List<Conversation>, snackbar: SnackbarHostState, actions: RoutinesActions) {
    var editing by remember { mutableStateOf<Routine?>(null) }
    Scaffold(
        topBar = { Bar(stringResource(R.string.routines), null, actions.back) },
        floatingActionButton = {
            FloatingActionButton(
                onClick = { editing = Routine(0, conversations.firstOrNull()?.id ?: 0, "", "", "", "daily", "09:00") },
                containerColor = CccColors.Claude, contentColor = Color.Black,
            ) { Icon(Icons.Filled.Add, stringResource(R.string.routine_add)) }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 12.dp, end = 12.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (state == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                return@LazyColumn
            }
            if (state.routines.isEmpty()) {
                item { Text(stringResource(R.string.routines_empty), color = CccColors.Muted, modifier = Modifier.padding(8.dp)) }
            }
            items(state.routines, key = { it.id }) { routine ->
                Section(routine.name) {
                    Text("${routine.schedule} · ${routine.conversation}" + if (routine.fresh) " · ${stringResource(R.string.routine_fresh_short)}" else "",
                        style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                    Text(routine.prompt, maxLines = 3, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium)
                    val next = shortTime(routine.nextRunAt)?.takeIf { routine.enabled }
                    Text(listOfNotNull(next?.let { stringResource(R.string.routine_next, it) }, routine.lastStatus.ifEmpty { null })
                        .joinToString(" · "), style = MaterialTheme.typography.labelMedium, color = CccColors.Waiting)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Switch(checked = routine.enabled, onCheckedChange = { actions.enable(routine.id, it) })
                        Spacer(Modifier.weight(1f))
                        IconButton(onClick = { actions.run(routine.id) }) { Icon(Icons.Filled.PlayArrow, stringResource(R.string.routine_run)) }
                        IconButton(onClick = { editing = routine }) { Icon(Icons.Filled.Edit, stringResource(R.string.edit)) }
                        IconButton(onClick = { actions.delete(routine.id) }) {
                            Icon(Icons.Filled.Delete, stringResource(R.string.delete), tint = CccColors.Error)
                        }
                    }
                }
            }
        }
    }
    editing?.let { routine ->
        RoutineDialog(routine, state, conversations, onClose = { editing = null }) {
            actions.save(it)
            editing = null
        }
    }
}

@Composable
private fun RoutineDialog(
    routine: Routine,
    state: Routines?,
    conversations: List<Conversation>,
    onClose: () -> Unit,
    onSave: (Routine) -> Unit,
) {
    var conversation by rememberSaveable { mutableStateOf(routine.conversationId.toString()) }
    var name by rememberSaveable { mutableStateOf(routine.name) }
    var prompt by rememberSaveable { mutableStateOf(routine.prompt) }
    var kind by rememberSaveable { mutableStateOf(routine.kind) }
    var value by rememberSaveable { mutableStateOf(routine.value) }
    var fresh by rememberSaveable { mutableStateOf(routine.fresh) }
    val kinds = state?.kinds.orEmpty()
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text(stringResource(if (routine.id == 0) R.string.routine_add else R.string.routine_edit)) },
        text = {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Picker(stringResource(R.string.routine_conversation), conversation, conversations.map { it.id.toString() to it.name }) { conversation = it } }
                item { OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text(stringResource(R.string.name_optional)) }) }
                item { OutlinedTextField(prompt, { prompt = it }, Modifier.fillMaxWidth(), minLines = 3, label = { Text(stringResource(R.string.routine_prompt)) }) }
                item { Picker(stringResource(R.string.routine_when), kind, kinds.map { it.kind to it.label }) { kind = it } }
                item {
                    OutlinedTextField(value, { value = it }, Modifier.fillMaxWidth(), singleLine = true,
                        placeholder = { Text(kinds.firstOrNull { it.kind == kind }?.hint.orEmpty()) })
                }
                item { CheckLine(stringResource(R.string.routine_fresh), fresh) { fresh = it } }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSave(routine.copy(conversationId = conversation.toIntOrNull() ?: 0, name = name, prompt = prompt, kind = kind, value = value, fresh = fresh)) },
                enabled = prompt.isNotBlank() && conversation.isNotEmpty(),
            ) { Text(stringResource(R.string.save)) }
        },
        dismissButton = { TextButton(onClick = onClose) { Text(stringResource(R.string.cancel)) } },
    )
}

// --- live sessions -------------------------------------------------------------------------------

/** Claude Code sessions running on the computer (s in ccc), a tab of the main screen; a prompt for one is typed in once it's idle. */
@Composable
fun LiveSessionsList(
    sessions: List<LiveSession>?,
    onPrompt: (String, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var target by remember { mutableStateOf<LiveSession?>(null) }
    LazyColumn(modifier.fillMaxSize(), contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 8.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (sessions == null) {
            item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            return@LazyColumn
        }
        item { Text(stringResource(R.string.live_sessions_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted) }
        if (sessions.isEmpty()) item { Text(stringResource(R.string.live_sessions_empty), color = CccColors.Muted) }
        items(sessions, key = { it.sessionId }) { session ->
            Column(Modifier.clickable { target = session }) {
                Section(session.name) {
                    Text(listOfNotNull(session.kindLabel ?: session.kind, session.statusLabel ?: session.status, session.stateLabel ?: session.state).joinToString(" · "),
                        style = MaterialTheme.typography.labelMedium,
                        color = if (session.status == "idle") CccColors.Claude else CccColors.Waiting)
                    Text(session.cwd, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                }
            }
        }
    }
    target?.let { session ->
        var prompt by rememberSaveable { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { target = null },
            title = { Text(session.name) },
            text = { OutlinedTextField(prompt, { prompt = it }, Modifier.fillMaxWidth(), minLines = 4,
                placeholder = { Text(stringResource(R.string.message_hint)) }) },
            confirmButton = {
                TextButton(onClick = { onPrompt(session.sessionId, prompt); target = null }, enabled = prompt.isNotBlank()) {
                    Text(stringResource(R.string.send))
                }
            },
            dismissButton = { TextButton(onClick = { target = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

// --- analytics -----------------------------------------------------------------------------------

/** One month's tokens (a in ccc): per day, per model, per conversation. */
@Composable
fun AnalyticsScreen(
    state: Analytics?,
    usage: io.github.luquas95.ccc.data.Usage?,
    snackbar: SnackbarHostState,
    onBack: () -> Unit,
    onMonth: (Int, Int) -> Unit,
    onArchive: () -> Unit,
) {
    Scaffold(
        topBar = { Bar(stringResource(R.string.analytics), null, onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            usage?.let { item { Section(stringResource(R.string.usage_limits)) { UsageCard(it) } } }
            if (state == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                return@LazyColumn
            }
            item {
                val shown = YearMonth.of(state.year, state.month)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { shown.minusMonths(1).let { onMonth(it.year, it.monthValue) } }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, stringResource(R.string.month_previous))
                    }
                    Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(state.title, fontWeight = FontWeight.Bold, color = CccColors.Title)
                        Text(stringResource(R.string.tokens_total, tokens(state.total)), style = MaterialTheme.typography.labelMedium)
                    }
                    IconButton(onClick = { shown.plusMonths(1).let { onMonth(it.year, it.monthValue) } },
                        enabled = shown < YearMonth.now()) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, stringResource(R.string.month_next))
                    }
                }
            }
            item { Section(stringResource(R.string.tokens_per_day)) { DayBars(state) } }
            item {
                Section(stringResource(R.string.tokens_per_model)) {
                    if (state.byModel.isEmpty()) Text(stringResource(R.string.tokens_none), color = CccColors.Muted)
                    val top = state.byModel.maxOfOrNull { it.tokens }?.coerceAtLeast(1) ?: 1
                    state.byModel.forEach { model ->
                        Text("${model.model} · ${tokens(model.tokens)}", style = MaterialTheme.typography.bodySmall)
                        LinearProgressIndicator(progress = { model.tokens.toFloat() / top }, modifier = Modifier.fillMaxWidth().height(6.dp),
                            color = CccColors.Title, trackColor = CccColors.SurfaceHigh, gapSize = 0.dp, drawStopIndicator = {})
                    }
                }
            }
            item {
                Section(stringResource(R.string.tokens_per_conversation)) {
                    state.byConversation.forEach { c ->
                        Row {
                            Text(c.name + if (c.deleted) " ${stringResource(R.string.deleted)}" else "", Modifier.weight(1f),
                                color = if (c.deleted) CccColors.Muted else Color.Unspecified, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(tokens(c.tokens), fontWeight = FontWeight.Bold)
                        }
                        Text(stringResource(R.string.run_counts, c.success, c.errors, c.rateLimited),
                            style = MaterialTheme.typography.labelSmall, color = CccColors.Muted)
                        HorizontalDivider(color = CccColors.Line)
                    }
                    Text(stringResource(R.string.blocked_minutes, state.blockedMinutes.toString()), style = MaterialTheme.typography.bodySmall)
                    Text(state.reserve?.let { stringResource(R.string.reserve_on, it) } ?: stringResource(R.string.reserve_off),
                        style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                }
            }
            item { OutlinedButton(onClick = onArchive) { Text(stringResource(R.string.archive_months)) } }
        }
    }
}

@Composable
private fun DayBars(state: Analytics) {
    val days = YearMonth.of(state.year, state.month).lengthOfMonth()
    val byDay = state.byDay.associate { it.day.takeLast(2).toInt() to it.tokens }
    val top = (byDay.values.maxOrNull() ?: 0L).coerceAtLeast(1)
    Canvas(Modifier.fillMaxWidth().height(96.dp)) {
        val slot = size.width / days
        for (day in 1..days) {
            val value = byDay[day] ?: 0L
            val h = size.height * value / top
            drawRect(
                color = if (value > 0) CccColors.Title else CccColors.SurfaceHigh,
                topLeft = Offset((day - 1) * slot + slot * 0.15f, size.height - h.coerceAtLeast(2f)),
                size = Size(slot * 0.7f, h.coerceAtLeast(2f)),
            )
        }
    }
    Row {
        Text("1", style = MaterialTheme.typography.labelSmall, color = CccColors.Muted)
        Spacer(Modifier.weight(1f))
        Text(days.toString(), style = MaterialTheme.typography.labelSmall, color = CccColors.Muted)
    }
}

// --- ccc's settings ----------------------------------------------------------------------------------

/** What ccc's settings screen can do. */
class SettingsActions(
    val back: () -> Unit,
    val save: (Map<String, JsonElement>) -> Unit,
    val action: (String) -> Unit,
    val savePresets: (List<PromptPreset>) -> Unit,
    val deleteLaunchPreset: (String) -> Unit,
    val backup: () -> Unit,
    val connection: () -> Unit,
)

/** ccc's own settings (Ctrl+P in ccc) — the same choices; secrets only as set / not set. */
@Composable
fun CccSettingsScreen(
    state: CccSettings?,
    presets: List<PromptPreset>,
    snackbar: SnackbarHostState,
    actions: SettingsActions,
    initialTab: Int = 0,
    language: String = "",
    onLanguage: (String) -> Unit = {},
) {
    Scaffold(
        topBar = { Bar(stringResource(R.string.ccc_settings), null, actions.back) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (state == null) {
            LinearProgressIndicator(Modifier.fillMaxWidth().padding(padding))
            return@Scaffold
        }
        // The computer's language and look (the TUI's) are not set here: the app has its own language choice.
        var groups by rememberSaveable(state) { mutableStateOf(state.groups) }
        var continueText by rememberSaveable(state) { mutableStateOf(state.continueText) }
        var reserve by rememberSaveable(state) { mutableStateOf(state.usageReserve?.toString() ?: "") }
        var reviewModel by rememberSaveable(state) { mutableStateOf(state.reviewModel) }
        var window by rememberSaveable(state) { mutableStateOf(state.contextWindow?.toString() ?: "") }
        var warn by rememberSaveable(state) { mutableStateOf(state.contextWarn.toString()) }
        var danger by rememberSaveable(state) { mutableStateOf(state.contextDanger.toString()) }
        var notify by rememberSaveable(state) { mutableStateOf(state.contextNotify) }
        var exportFolder by rememberSaveable(state) { mutableStateOf(state.exportFolder) }
        var exportSend by rememberSaveable(state) { mutableStateOf(state.exportSend) }
        var archiveFolder by rememberSaveable(state) { mutableStateOf(state.archiveFolder) }
        var chat by rememberSaveable(state) { mutableStateOf(state.telegram.chat) }
        var token by rememberSaveable(state) { mutableStateOf("") }
        var webhook by rememberSaveable(state) { mutableStateOf("") }
        // What each service is told: the keys of the ticked categories, kept in the form until Save.
        var telegramOn by rememberSaveable(state) { mutableStateOf(state.notifyTelegram.filterValues { it }.keys.joinToString(",")) }
        var discordOn by rememberSaveable(state) { mutableStateOf(state.notifyDiscord.filterValues { it }.keys.joinToString(",")) }
        var choosing by rememberSaveable { mutableStateOf("") }
        val off = stringResource(R.string.off)
        val auto = stringResource(R.string.auto)
        // One tab per kind of setting, so each is found in one place; the values of all the tabs are
        // kept together and one Save (on the tabs that have fields) sends them.
        var tab by rememberSaveable { mutableIntStateOf(initialTab) }
        val tabs = listOf(R.string.settings_general, R.string.settings_queues, R.string.settings_notifications,
            R.string.tab_presets, R.string.settings_data, R.string.settings_connection)
        if (choosing != "") {
            val on = if (choosing == "telegram") telegramOn else discordOn
            NotifyCategoriesDialog(
                title = stringResource(if (choosing == "telegram") R.string.settings_telegram else R.string.settings_discord),
                categories = state.notifyCategories, ticked = on.split(",").filter { it.isNotEmpty() }.toSet(),
                onDone = { keys ->
                    if (choosing == "telegram") telegramOn = keys.joinToString(",") else discordOn = keys.joinToString(",")
                    choosing = ""
                },
                onDismiss = { choosing = "" },
            )
        }
        Column(Modifier.fillMaxSize().padding(padding)) {
        ScrollableTabRow(selectedTabIndex = tab, edgePadding = 12.dp, containerColor = CccColors.Background) {
            tabs.forEachIndexed { i, label ->
                Tab(selected = tab == i, onClick = { tab = i }, text = { Text(stringResource(label)) })
            }
        }
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (tab == 0) item {
                Section(stringResource(R.string.settings_general)) {
                    // The app's own language (not the computer's): applies at once, apart from Save.
                    LanguageChoice(language, onLanguage)
                    Picker(stringResource(R.string.groups_in_list), groups, state.groupsChoices.map { it.value to it.label }) { groups = it }
                }
            }
            if (tab == 1) item {
                Section(stringResource(R.string.settings_queues)) {
                    OutlinedTextField(continueText, { continueText = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.continue_text)) })
                    Picker(stringResource(R.string.usage_reserve), reserve, listOf("" to off) + state.reserveChoices.map { "$it" to "$it %" }) { reserve = it }
                    Picker(stringResource(R.string.review_model), reviewModel, state.reviewModels.map { it.value to it.label }) { reviewModel = it }
                }
            }
            if (tab == 1) item {
                Section(stringResource(R.string.settings_context)) {
                    Picker(stringResource(R.string.context_window), window, listOf("" to auto) + state.windowChoices.map { "$it" to "${it / 1000}k" }) { window = it }
                    Picker(stringResource(R.string.context_warn), warn, state.thresholdChoices.map { "$it" to "$it %" }) { warn = it }
                    Picker(stringResource(R.string.context_danger), danger, state.thresholdChoices.map { "$it" to "$it %" }) { danger = it }
                    CheckLine(stringResource(R.string.context_notify), notify) { notify = it }
                }
            }
            if (tab == 2) item {
                Section(stringResource(R.string.settings_telegram)) {
                    Text(stringResource(if (state.telegram.on) R.string.on else R.string.telegram_off_hint),
                        color = if (state.telegram.on) CccColors.Claude else CccColors.Waiting, style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(token, { token = it }, Modifier.fillMaxWidth(), singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        label = { Text(stringResource(R.string.telegram_token)) },
                        placeholder = { Text(stringResource(if (state.telegram.tokenSet) R.string.secret_saved else R.string.telegram_token_hint)) })
                    OutlinedTextField(chat, { chat = it }, Modifier.fillMaxWidth(), singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), label = { Text(stringResource(R.string.telegram_chat)) })
                    Row {
                        TextButton(onClick = { actions.action("telegram-test") }) { Text(stringResource(R.string.send_test)) }
                        TextButton(onClick = { choosing = "telegram" }) { Text(stringResource(R.string.choose_messages)) }
                        TextButton(onClick = { actions.action("telegram-off") }) { Text(stringResource(R.string.turn_off), color = CccColors.Error) }
                    }
                }
            }
            if (tab == 2) item {
                Section(stringResource(R.string.settings_discord)) {
                    Text(stringResource(if (state.discord.on) R.string.on else R.string.discord_off_hint),
                        color = if (state.discord.on) CccColors.Claude else CccColors.Waiting, style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(webhook, { webhook = it }, Modifier.fillMaxWidth(), singleLine = true,
                        visualTransformation = PasswordVisualTransformation(), label = { Text(stringResource(R.string.discord_webhook)) },
                        placeholder = { Text(stringResource(if (state.discord.on) R.string.secret_saved else R.string.discord_webhook_hint)) })
                    Row {
                        TextButton(onClick = { actions.action("discord-test") }) { Text(stringResource(R.string.send_test)) }
                        TextButton(onClick = { choosing = "discord" }) { Text(stringResource(R.string.choose_messages)) }
                        TextButton(onClick = { actions.action("discord-off") }) { Text(stringResource(R.string.turn_off), color = CccColors.Error) }
                    }
                }
            }
            if (tab == 4) item {
                Section(stringResource(R.string.settings_folders)) {
                    OutlinedTextField(exportFolder, { exportFolder = it }, Modifier.fillMaxWidth(), singleLine = true,
                        label = { Text(stringResource(R.string.export_folder)) })
                    Picker(stringResource(R.string.after_export), exportSend, state.sendChoices.map { it.value to it.label }) { exportSend = it }
                    OutlinedTextField(archiveFolder, { archiveFolder = it }, Modifier.fillMaxWidth(), singleLine = true,
                        label = { Text(stringResource(R.string.archive_folder)) })
                }
            }
            if (tab == 3) item { PromptPresetsSection(presets, actions.savePresets) }
            if (tab == 3) item {
                Section(stringResource(R.string.launch_presets)) {
                    if (state.launchPresets.isEmpty()) Text(stringResource(R.string.launch_presets_none), color = CccColors.Muted,
                        style = MaterialTheme.typography.bodySmall)
                    state.launchPresets.forEach { name ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(name, Modifier.weight(1f))
                            IconButton(onClick = { actions.deleteLaunchPreset(name) }) {
                                Icon(Icons.Filled.Delete, stringResource(R.string.delete), tint = CccColors.Error)
                            }
                        }
                    }
                }
            }
            if (tab == 4) item {
                Section(stringResource(R.string.settings_data)) {
                    Text(stringResource(R.string.backup_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                    OutlinedButton(onClick = actions.backup) { Text(stringResource(R.string.backup_now)) }
                }
            }
            if (tab == 5) item {
                Section(stringResource(R.string.settings_connection)) {
                    Text(stringResource(R.string.settings_connection_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                    Button(onClick = actions.connection, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.connection)) }
                }
            }
            if (tab != 3 && tab != 5) item {
                Button(onClick = {
                    actions.save(buildMap {
                        put("groups", JsonPrimitive(groups))
                        put("continue_text", JsonPrimitive(continueText))
                        put("usage_reserve", reserve.toIntOrNull()?.let { JsonPrimitive(it) } ?: JsonNull)
                        put("review_model", JsonPrimitive(reviewModel))
                        put("context_window", window.toIntOrNull()?.let { JsonPrimitive(it) } ?: JsonNull)
                        put("context_warn", JsonPrimitive(warn.toInt()))
                        put("context_danger", JsonPrimitive(danger.toInt()))
                        put("context_notify", JsonPrimitive(notify))
                        put("export_folder", JsonPrimitive(exportFolder))
                        put("export_send", JsonPrimitive(exportSend))
                        put("archive_folder", JsonPrimitive(archiveFolder))
                        put("telegram_chat", JsonPrimitive(chat))
                        if (token.isNotBlank()) put("telegram_token", JsonPrimitive(token))
                        if (webhook.isNotBlank()) put("discord_webhook", JsonPrimitive(webhook))
                        put("notify_telegram", notifyJson(state.notifyCategories, telegramOn))
                        put("notify_discord", notifyJson(state.notifyCategories, discordOn))
                    })
                }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.save)) }
            }
        }
        }
    }
}

/** The preset prompts (Alt+1 … 9 in ccc): each change is saved at once. */
@Composable
private fun PromptPresetsSection(presets: List<PromptPreset>, onSave: (List<PromptPreset>) -> Unit) {
    var editing by remember { mutableStateOf<Int?>(null) }
    Section(stringResource(R.string.prompt_presets)) {
        Text(stringResource(R.string.prompt_presets_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
        presets.forEachIndexed { i, preset ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f).clickable { editing = i }) {
                    Text("${i + 1}. " + (if (preset.sendNow) "⏎ " else "✎ ") + preset.name, fontWeight = FontWeight.Bold)
                    Text(preset.text, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall,
                        color = CccColors.Muted)
                }
                IconButton(onClick = { onSave(presets.toMutableList().apply { add(i - 1, removeAt(i)) }) }, enabled = i > 0) {
                    Icon(Icons.Filled.KeyboardArrowUp, stringResource(R.string.move_up))
                }
                IconButton(onClick = { onSave(presets.toMutableList().apply { add(i + 1, removeAt(i)) }) }, enabled = i < presets.lastIndex) {
                    Icon(Icons.Filled.KeyboardArrowDown, stringResource(R.string.move_down))
                }
                IconButton(onClick = { onSave(presets.filterIndexed { j, _ -> j != i }) }) {
                    Icon(Icons.Filled.Delete, stringResource(R.string.delete), tint = CccColors.Error)
                }
            }
        }
        if (presets.size < 9) OutlinedButton(onClick = { editing = -1 }) { Text(stringResource(R.string.add)) }
    }
    editing?.let { index ->
        val preset = presets.getOrNull(index)
        var name by rememberSaveable(index) { mutableStateOf(preset?.name.orEmpty()) }
        var text by rememberSaveable(index) { mutableStateOf(preset?.text.orEmpty()) }
        var sendNow by rememberSaveable(index) { mutableStateOf(preset?.sendNow ?: false) }
        AlertDialog(
            onDismissRequest = { editing = null },
            title = { Text(stringResource(R.string.prompt_presets)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(name, { name = it }, singleLine = true, label = { Text(stringResource(R.string.name)) })
                    OutlinedTextField(text, { text = it }, minLines = 3, label = { Text(stringResource(R.string.text)) })
                    CheckLine(stringResource(if (sendNow) R.string.send_now else R.string.send_now_off), sendNow) { sendNow = it }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val edited = PromptPreset(index + 1, name.trim(), text.trim(), sendNow)
                    onSave(if (preset == null) presets + edited else presets.mapIndexed { j, p -> if (j == index) edited else p })
                    editing = null
                }, enabled = name.isNotBlank() && text.isNotBlank()) { Text(stringResource(R.string.save)) }
            },
            dismissButton = { TextButton(onClick = { editing = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

/** The categories as the settings call wants them: every one, ticked or not. */
private fun notifyJson(categories: List<NotifyCategory>, on: String): JsonObject {
    val ticked = on.split(",").filter { it.isNotEmpty() }.toSet()
    return JsonObject(categories.associate { it.key to JsonPrimitive(it.key in ticked) })
}

/** Which messages one service gets — a tick for each kind; applied to the form, saved with Save. */
@Composable
private fun NotifyCategoriesDialog(
    title: String,
    categories: List<NotifyCategory>,
    ticked: Set<String>,
    onDone: (Set<String>) -> Unit,
    onDismiss: () -> Unit,
) {
    var chosen by remember { mutableStateOf(ticked) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            LazyColumn {
                items(categories) { category ->
                    Column(Modifier.padding(bottom = 6.dp)) {
                        CheckLine(category.label, category.key in chosen) { on ->
                            chosen = if (on) chosen + category.key else chosen - category.key
                        }
                        Text(category.hint, Modifier.padding(start = 48.dp), color = CccColors.Muted,
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { onDone(chosen) }) { Text(stringResource(R.string.ok)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
}

package io.github.luquas95.ccc.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.Goal
import io.github.luquas95.ccc.data.Review
import io.github.luquas95.ccc.data.WorkflowRun
import io.github.luquas95.ccc.ui.theme.CccColors

private const val OUTPUT_CHARS = 600

/** Pick one of [options] (value to label), shown as a button. */
@Composable
fun Picker(label: String, value: String, options: List<Pair<String, String>>, onPick: (String) -> Unit) {
    var open by rememberSaveable { mutableStateOf(false) }
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
        Box {
            OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth()) {
                Text(options.firstOrNull { it.first == value }?.second ?: value, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f))
                Text("▾")
            }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                options.forEach { (option, text) ->
                    DropdownMenuItem(text = { Text(text) }, onClick = { open = false; onPick(option) })
                }
            }
        }
    }
}

@Composable
internal fun Section(title: String, content: @Composable () -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Line),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, color = CccColors.Title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleSmall)
            content()
        }
    }
}

@Composable
internal fun CheckLine(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable { onChange(!checked) }, verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = checked, onCheckedChange = onChange)
        Text(label, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun RoundsField(value: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = { text -> onChange(text.filter { it.isDigit() }.take(2)) },
        label = { Text(stringResource(R.string.rounds)) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        modifier = Modifier.width(120.dp),
    )
}

@Composable
private fun Go(text: String, enabled: Boolean, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(containerColor = CccColors.Claude, contentColor = Color.Black),
    ) { Text(text) }
}

@Composable
private fun Stop(enabled: Boolean, onClick: () -> Unit) {
    TextButton(onClick = onClick, enabled = enabled) { Text(stringResource(R.string.stop), color = CccColors.Error) }
}

/** What the agents screen can do. */
class AgentsActions(
    val back: () -> Unit,
    val review: (String, Boolean, Int?) -> Unit,
    val stopReview: () -> Unit,
    val applyReview: (Int) -> Unit,
    val goal: (String, String, Int?) -> Unit,
    val stopGoal: () -> Unit,
    val workflow: (String, String, String, Int?) -> Unit,
    val answer: (Boolean, String) -> Unit,
    val stopWorkflow: () -> Unit,
)

/** Reviews (v), goal loops (g), and workflows (w) of one conversation. */
@Composable
fun AgentsScreen(
    state: AgentsState,
    name: String,
    firstTab: Int,
    snackbar: SnackbarHostState,
    actions: AgentsActions,
) {
    var tab by rememberSaveable { mutableIntStateOf(firstTab) }
    Scaffold(
        topBar = { Bar(stringResource(R.string.agents), name, actions.back) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            PrimaryTabRow(selectedTabIndex = tab, containerColor = CccColors.Background, contentColor = CccColors.Title) {
                listOf(R.string.reviews, R.string.goal, R.string.workflow).forEachIndexed { i, label ->
                    Tab(selected = tab == i, onClick = { tab = i }, text = { Text(stringResource(label), maxLines = 1) })
                }
            }
            LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                when (tab) {
                    0 -> reviewsTab(state, actions)
                    1 -> goalsTab(state, actions)
                    else -> workflowsTab(state, actions)
                }
            }
        }
    }
}

private fun LazyListScope.loading(ready: Boolean): Boolean {
    if (!ready) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
    return !ready
}

private fun LazyListScope.reviewsTab(state: AgentsState, actions: AgentsActions) {
    val reviews = state.reviews
    if (loading(reviews != null) || reviews == null) return
    item(key = "review-form") {
        var instructions by rememberSaveable { mutableStateOf("") }
        var untilPass by rememberSaveable { mutableStateOf(false) }
        var rounds by rememberSaveable { mutableStateOf("5") }
        Section(stringResource(R.string.review_new)) {
            Text(stringResource(R.string.review_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
            OutlinedTextField(instructions, { instructions = it }, Modifier.fillMaxWidth(), minLines = 3,
                placeholder = { Text(stringResource(R.string.review_instructions)) })
            CheckLine(stringResource(R.string.review_until_pass), untilPass) { untilPass = it }
            if (untilPass) RoundsField(rounds) { rounds = it }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Go(stringResource(R.string.review_start), !reviews.active) {
                    actions.review(instructions, untilPass, rounds.toIntOrNull())
                    instructions = ""
                }
                Stop(reviews.active, actions.stopReview)
            }
        }
    }
    if (reviews.reviews.isEmpty()) item { Empty(R.string.reviews_empty) }
    items(reviews.reviews, key = { "review:${it.id}" }) { ReviewCard(it) { actions.applyReview(it.id) } }
}

@Composable
private fun Empty(text: Int) {
    Text(stringResource(text), color = CccColors.Muted, modifier = Modifier.padding(8.dp))
}

@Composable
private fun ReviewCard(review: Review, onApply: () -> Unit) {
    val color = when (review.verdict) {
        "PASS" -> CccColors.Claude
        "FAIL" -> CccColors.Error
        "PARTIAL" -> CccColors.Waiting
        else -> if (review.status == "error") CccColors.Error else CccColors.Muted
    }
    Section(listOfNotNull(review.verdict ?: review.statusLabel, "${review.round}/${review.maxRounds}".takeIf { review.untilPass || review.round > 1 },
        shortTime(review.finishedAt ?: review.createdAt)).joinToString(" · ")) {
        if (review.scope.isNotEmpty()) Text(review.scope, style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
        if (review.instructions.isNotEmpty()) Text(review.instructions, style = MaterialTheme.typography.bodySmall)
        if (review.error.isNotEmpty()) Text(review.error, color = CccColors.Error, style = MaterialTheme.typography.bodySmall)
        if (review.report.isNotEmpty()) Expandable(review.report, color)
        if (review.canApply) Go(stringResource(R.string.review_apply), true, onApply)
        if (review.fixSent) Text(stringResource(R.string.review_fix_sent), color = CccColors.Claude, style = MaterialTheme.typography.bodySmall)
    }
}

/** Long text: the start of it, all on a tap. */
@Composable
private fun Expandable(text: String, color: Color = Color.Unspecified, mono: Boolean = false) {
    var open by rememberSaveable(text.hashCode()) { mutableStateOf(false) }
    Text(
        if (open || text.length <= OUTPUT_CHARS) text else text.take(OUTPUT_CHARS) + " …",
        Modifier.clickable { open = !open },
        style = MaterialTheme.typography.bodySmall,
        color = color,
        fontFamily = if (mono) FontFamily.Monospace else null,
    )
}

private fun LazyListScope.goalsTab(state: AgentsState, actions: AgentsActions) {
    val goals = state.goals
    if (loading(goals != null) || goals == null) return
    item(key = "goal-form") {
        var goal by rememberSaveable { mutableStateOf("") }
        var check by rememberSaveable { mutableStateOf("") }
        var rounds by rememberSaveable { mutableStateOf("5") }
        Section(stringResource(R.string.goal_new)) {
            Text(stringResource(R.string.goal_hint), style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
            OutlinedTextField(goal, { goal = it }, Modifier.fillMaxWidth(), minLines = 3,
                placeholder = { Text(stringResource(R.string.goal_text)) })
            OutlinedTextField(check, { check = it }, Modifier.fillMaxWidth(), singleLine = true,
                label = { Text(stringResource(R.string.check_command)) })
            RoundsField(rounds) { rounds = it }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Go(stringResource(R.string.goal_start), !goals.active && goal.isNotBlank()) {
                    actions.goal(goal, check, rounds.toIntOrNull())
                    goal = ""
                }
                Stop(goals.active, actions.stopGoal)
            }
        }
    }
    if (goals.goals.isEmpty()) item { Empty(R.string.goals_empty) }
    items(goals.goals, key = { "goal:${it.id}" }) { GoalCard(it) }
}

@Composable
private fun GoalCard(goal: Goal) {
    Section(listOfNotNull(goal.statusLabel, "${goal.round}/${goal.maxRounds}", shortTime(goal.createdAt)).joinToString(" · ")) {
        Text(goal.goal, style = MaterialTheme.typography.bodyMedium)
        if (goal.checkCommand.isNotEmpty()) {
            Text("${stringResource(R.string.check_command)}: ${goal.checkCommand}", fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
        }
        if (goal.status == "running") Text(goal.phaseLabel, color = CccColors.Waiting, style = MaterialTheme.typography.bodySmall)
        if (goal.lastReason.isNotEmpty()) Expandable(goal.lastReason)
    }
}

private fun LazyListScope.workflowsTab(state: AgentsState, actions: AgentsActions) {
    val flows = state.workflows
    if (loading(flows != null) || flows == null) return
    item(key = "workflow-form") {
        var template by rememberSaveable { mutableStateOf("") }
        var task by rememberSaveable { mutableStateOf("") }
        var check by rememberSaveable { mutableStateOf("") }
        var rounds by rememberSaveable { mutableStateOf("") }
        LaunchedEffect(state.templates) {
            if (template.isEmpty()) state.templates.firstOrNull()?.let { template = it.name; rounds = it.maxRounds.toString() }
        }
        val chosen = state.templates.firstOrNull { it.name == template }
        Section(stringResource(R.string.workflow_new)) {
            Picker(stringResource(R.string.workflow_template), template, state.templates.map { it.name to it.title }) { name ->
                template = name
                state.templates.firstOrNull { it.name == name }?.let { rounds = it.maxRounds.toString() }
            }
            chosen?.let {
                Text(it.steps, style = MaterialTheme.typography.bodySmall, color = CccColors.Muted)
                if (it.details.isNotEmpty()) Expandable(it.details, CccColors.Muted, mono = true)
            }
            OutlinedTextField(task, { task = it }, Modifier.fillMaxWidth(), minLines = 3,
                placeholder = { Text(stringResource(R.string.workflow_task)) })
            OutlinedTextField(check, { check = it }, Modifier.fillMaxWidth(), singleLine = true,
                label = { Text(stringResource(R.string.check_command)) })
            RoundsField(rounds) { rounds = it }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Go(stringResource(R.string.workflow_start), !flows.active && task.isNotBlank() && template.isNotEmpty()) {
                    actions.workflow(template, task, check, rounds.toIntOrNull())
                    task = ""
                }
                Stop(flows.active, actions.stopWorkflow)
            }
        }
    }
    if (flows.waiting) {
        item(key = "workflow-gate") {
            var note by rememberSaveable { mutableStateOf("") }
            Section(stringResource(R.string.workflow_gate)) {
                OutlinedTextField(note, { note = it }, Modifier.fillMaxWidth(),
                    placeholder = { Text(stringResource(R.string.workflow_note)) })
                Row {
                    Go(stringResource(R.string.approve), true) { actions.answer(true, note); note = "" }
                    TextButton(onClick = { actions.answer(false, note); note = "" }) {
                        Text(stringResource(R.string.reject), color = CccColors.Error)
                    }
                }
            }
        }
    }
    if (flows.runs.isEmpty()) item { Empty(R.string.workflows_empty) }
    items(flows.runs, key = { "workflow:${it.id}" }) { WorkflowCard(it) }
}

@Composable
private fun WorkflowCard(run: WorkflowRun) {
    Section(listOfNotNull(run.name, run.statusLabel, "${run.round}/${run.maxRounds}", shortTime(run.createdAt)).joinToString(" · ")) {
        Row(Modifier.horizontalScroll(rememberScrollState())) {
            run.steps.forEach { step ->
                val (mark, color) = when (step.state) {
                    "done" -> "✓" to CccColors.Claude
                    "now" -> "▶" to CccColors.Waiting
                    "waits" -> "⏸" to CccColors.Approval
                    else -> "○" to CccColors.Muted
                }
                Text("$mark ${step.label}   ", color = color, style = MaterialTheme.typography.labelMedium)
            }
        }
        Text(run.task, style = MaterialTheme.typography.bodyMedium)
        if (run.lastReason.isNotEmpty()) Expandable(run.lastReason)
        run.events.forEach { event ->
            Text(
                "${event.kindLabel} · ${event.name}  (${stringResource(R.string.round)} ${event.round})  " +
                    event.verdict.ifEmpty { event.status },
                fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium,
                color = when (event.verdict.ifEmpty { event.status }) {
                    "PASS", "APPROVED", "done" -> CccColors.Claude
                    "FAIL", "REJECTED", "error" -> CccColors.Error
                    else -> CccColors.Waiting
                },
            )
            if (event.output.isNotEmpty()) Expandable(event.output, CccColors.Muted)
        }
    }
}

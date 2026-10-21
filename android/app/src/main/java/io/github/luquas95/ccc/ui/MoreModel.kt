package io.github.luquas95.ccc.ui

import io.github.luquas95.ccc.data.Analytics
import io.github.luquas95.ccc.data.AskItem
import io.github.luquas95.ccc.data.CccApi
import io.github.luquas95.ccc.data.CccSettings
import io.github.luquas95.ccc.data.Goals
import io.github.luquas95.ccc.data.LiveSession
import io.github.luquas95.ccc.data.PromptPreset
import io.github.luquas95.ccc.data.Reviews
import io.github.luquas95.ccc.data.Routine
import io.github.luquas95.ccc.data.Routines
import io.github.luquas95.ccc.data.WorkflowTemplate
import io.github.luquas95.ccc.data.Workflows
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement

/** A conversation's reviews, goals, workflows and questions. */
data class AgentsState(
    val id: Int,
    val reviews: Reviews? = null,
    val goals: Goals? = null,
    val workflows: Workflows? = null,
    val templates: List<WorkflowTemplate> = emptyList(),
    val asks: List<AskItem>? = null,
)

/**
 * The state of the screens beyond the conversations (agents, routines, live
 * sessions, analytics, ccc's settings), owned by [AppViewModel]: [run]
 * calls the API with its error handling, [say] shows a message.
 */
class MoreModel(
    private val scope: CoroutineScope,
    private val run: suspend (suspend (CccApi) -> Unit) -> Boolean,
    private val say: (String) -> Unit,
) {
    private val _agents = MutableStateFlow<AgentsState?>(null)
    val agents: StateFlow<AgentsState?> = _agents.asStateFlow()

    private val _routines = MutableStateFlow<Routines?>(null)
    val routines: StateFlow<Routines?> = _routines.asStateFlow()

    private val _sessions = MutableStateFlow<List<LiveSession>?>(null)
    val sessions: StateFlow<List<LiveSession>?> = _sessions.asStateFlow()

    private val _analytics = MutableStateFlow<Analytics?>(null)
    val analytics: StateFlow<Analytics?> = _analytics.asStateFlow()

    private val _settings = MutableStateFlow<CccSettings?>(null)
    val settings: StateFlow<CccSettings?> = _settings.asStateFlow()

    private fun go(block: suspend (CccApi) -> Unit) {
        scope.launch { run(block) }
    }

    // --- agents ----------------------------------------------------------------------------

    fun openAgents(id: Int) {
        _agents.value = AgentsState(id)
        go { api -> _agents.update { it?.copy(templates = api.workflowTemplates()) } }
        scope.launch { reloadAgents(id) }
    }

    fun closeAgents() {
        _agents.value = null
    }

    suspend fun reloadAgents(id: Int) {
        if (_agents.value?.id != id) return
        run { api ->
            val reviews = api.reviews(id)
            val goals = api.goals(id)
            val workflows = api.workflows(id)
            val asks = api.asks(id)
            _agents.update { if (it?.id == id) it.copy(reviews = reviews, goals = goals, workflows = workflows, asks = asks) else it }
        }
    }

    private fun agentAction(block: suspend (CccApi, Int) -> Unit) {
        val id = _agents.value?.id ?: return
        go { api ->
            block(api, id)
            reloadAgents(id)
        }
    }

    fun requestReview(instructions: String, untilPass: Boolean, rounds: Int?) =
        agentAction { api, id -> api.requestReview(id, instructions, untilPass, rounds) }

    fun stopReview() = agentAction { api, id -> api.stopReview(id) }

    fun applyReview(reviewId: Int) = agentAction { api, _ -> api.applyReview(reviewId) }

    fun startGoal(goal: String, check: String, rounds: Int?) = agentAction { api, id -> api.startGoal(id, goal, check, rounds) }

    fun stopGoal() = agentAction { api, id -> api.stopGoal(id) }

    fun startWorkflow(template: String, task: String, check: String, rounds: Int?) =
        agentAction { api, id -> api.startWorkflow(id, template, task, check, rounds) }

    fun answerWorkflow(approve: Boolean, note: String) = agentAction { api, id -> api.answerWorkflow(id, approve, note) }

    fun stopWorkflow() = agentAction { api, id -> api.stopWorkflow(id) }

    fun ask(to: Int, question: String, deliver: Boolean) = agentAction { api, id -> api.ask(id, to, question, deliver) }

    fun cancelAsk(askId: Int) = agentAction { api, _ -> api.cancelAsk(askId) }

    // --- routines ----------------------------------------------------------------------------

    fun loadRoutines() = go { api -> _routines.value = api.routines() }

    fun saveRoutine(routine: Routine) = go { api ->
        _routines.value = if (routine.id == 0) api.addRoutine(routine) else api.editRoutine(routine)
    }

    fun deleteRoutine(id: Int) = go { api -> _routines.value = api.deleteRoutine(id) }

    fun enableRoutine(id: Int, enabled: Boolean) = go { api -> _routines.value = api.enableRoutine(id, enabled) }

    fun runRoutine(id: Int) = go { api ->
        say(api.runRoutine(id).label)
        _routines.value = api.routines()
    }

    // --- live sessions -------------------------------------------------------------------------

    fun loadSessions() = go { api -> _sessions.value = api.liveSessions() }

    fun promptSession(sessionId: String, prompt: String, done: String) = go { api ->
        api.promptLiveSession(sessionId, prompt)
        say(done)
    }

    // --- analytics -------------------------------------------------------------------------------

    fun loadAnalytics(year: Int? = null, month: Int? = null) = go { api -> _analytics.value = api.analytics(year, month) }

    fun archiveAnalytics(done: String) = go { api ->
        api.archiveAnalytics()
        say(done)
    }

    // --- settings -----------------------------------------------------------------------------------

    fun loadSettings() = go { api -> _settings.value = api.settings() }

    fun changeSettings(changes: Map<String, JsonElement>, done: String) = go { api ->
        _settings.value = api.changeSettings(changes)
        say(done)
    }

    /** "telegram-test", "telegram-off", "discord-test", "discord-off". */
    fun settingsAction(action: String, done: String) = go { api ->
        api.settingsAction(action)
        _settings.value = api.settings()
        say(done)
    }

    fun savePromptPresets(presets: List<PromptPreset>, then: () -> Unit) = go { api ->
        api.savePromptPresets(presets)
        then()
    }

    fun deleteLaunchPreset(name: String) = go { api ->
        api.deleteLaunchPreset(name)
        _settings.value = api.settings()
    }

    fun backup(done: String) = go { api ->
        api.backup()
        say(done)
    }
}

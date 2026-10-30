package io.github.luquas95.ccc.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Reviews, goals, workflows, questions, routines, live sessions, analytics and settings (src/ccc/api_agents.py, api_views.py). */

/** The answer of POST /pair: the token of this phone's own device. */
@Serializable
data class PairResult(
    val token: String,
    @SerialName("device_id") val deviceId: Int,
    val name: String = "",
    val version: String = "",
)

/** A phone signed in to ccc's API (GET /devices); [current] is the one asking. */
@Serializable
data class Device(
    val id: Int,
    val name: String,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
    @SerialName("last_ip") val lastIp: String = "",
    val current: Boolean = false,
)

@Serializable
data class Devices(val devices: List<Device> = emptyList())

@Serializable
data class Review(
    val id: Int,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    val verdict: String? = null,
    val round: Int = 1,
    @SerialName("max_rounds") val maxRounds: Int = 1,
    @SerialName("until_pass") val untilPass: Boolean = false,
    val scope: String = "",
    val instructions: String = "",
    val report: String = "",
    val error: String = "",
    @SerialName("fix_sent") val fixSent: Boolean = false,
    @SerialName("can_apply") val canApply: Boolean = false,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
)

@Serializable
data class Reviews(val active: Boolean = false, val reviews: List<Review> = emptyList())

@Serializable
data class Goal(
    val id: Int,
    val goal: String,
    @SerialName("check_command") val checkCommand: String = "",
    val round: Int = 1,
    @SerialName("max_rounds") val maxRounds: Int = 1,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    @SerialName("phase_label") val phaseLabel: String = "",
    @SerialName("last_reason") val lastReason: String = "",
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class Goals(val active: Boolean = false, val goals: List<Goal> = emptyList())

@Serializable
data class WorkflowTemplate(
    val name: String,
    val title: String,
    val steps: String = "",
    val details: String = "",
    @SerialName("max_rounds") val maxRounds: Int = 3,
)

/** state: "done", "now", "waits" or "to_come". */
@Serializable
data class WorkflowStep(val label: String, val state: String)

@Serializable
data class WorkflowEvent(
    val kind: String,
    @SerialName("kind_label") val kindLabel: String = "",
    val name: String = "",
    val round: Int = 1,
    val status: String = "",
    val verdict: String = "",
    val output: String = "",
)

@Serializable
data class WorkflowRun(
    val id: Int,
    val name: String,
    val task: String,
    val round: Int = 1,
    @SerialName("max_rounds") val maxRounds: Int = 1,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    @SerialName("last_reason") val lastReason: String = "",
    val steps: List<WorkflowStep> = emptyList(),
    val events: List<WorkflowEvent> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class Workflows(val active: Boolean = false, val waiting: Boolean = false, val runs: List<WorkflowRun> = emptyList())

@Serializable
data class AskItem(
    val id: Int,
    val outgoing: Boolean,
    @SerialName("other_id") val otherId: Int,
    @SerialName("other_name") val otherName: String,
    @SerialName("by_agent") val byAgent: Boolean = false,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    val question: String,
    val answer: String = "",
    val error: String = "",
    @SerialName("can_cancel") val canCancel: Boolean = false,
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class RoutineKind(val kind: String, val label: String, val hint: String = "")

@Serializable
data class Routine(
    val id: Int,
    @SerialName("conversation_id") val conversationId: Int,
    val conversation: String = "",
    val name: String,
    val prompt: String,
    val kind: String,
    val value: String,
    val schedule: String = "",
    val fresh: Boolean = false,
    val enabled: Boolean = true,
    @SerialName("next_run_at") val nextRunAt: String? = null,
    @SerialName("last_run_at") val lastRunAt: String? = null,
    @SerialName("last_status") val lastStatus: String = "",
    val skipped: Int = 0,
)

@Serializable
data class Routines(val kinds: List<RoutineKind> = emptyList(), val routines: List<Routine> = emptyList())

@Serializable
data class RoutineRun(val status: String, val label: String)

@Serializable
data class LiveSession(
    @SerialName("session_id") val sessionId: String,
    val name: String,
    val cwd: String,
    val kind: String,
    val status: String? = null,
    val state: String? = null,
)

@Serializable
data class DayTokens(val day: String, val tokens: Long)

@Serializable
data class ModelTokens(val model: String, val tokens: Long)

@Serializable
data class ConversationTokens(
    val id: Int,
    val name: String,
    val deleted: Boolean = false,
    val tokens: Long,
    val success: Int = 0,
    val errors: Int = 0,
    @SerialName("rate_limited") val rateLimited: Int = 0,
)

@Serializable
data class MonthTokens(val year: Int, val month: Int, val tokens: Long)

@Serializable
data class Analytics(
    val year: Int,
    val month: Int,
    val title: String,
    val total: Long,
    @SerialName("by_day") val byDay: List<DayTokens> = emptyList(),
    @SerialName("by_model") val byModel: List<ModelTokens> = emptyList(),
    @SerialName("by_conversation") val byConversation: List<ConversationTokens> = emptyList(),
    val months: List<MonthTokens> = emptyList(),
    @SerialName("blocked_minutes") val blockedMinutes: Double = 0.0,
    val reserve: Int? = null,
)

/** What a conversation's Claude Code shows: the screen with its colours (ANSI) and the cursor. */
@Serializable
data class Terminal(
    val screen: String,
    val width: Int = 80,
    val height: Int = 24,
    @SerialName("cursor_x") val cursorX: Int = 0,
    @SerialName("cursor_y") val cursorY: Int = 0,
)

@Serializable
data class Choice(val value: String, val label: String)

@Serializable
data class TelegramState(@SerialName("token_set") val tokenSet: Boolean = false, val chat: String = "", val on: Boolean = false)

@Serializable
data class DiscordState(val on: Boolean = false)

/** ccc's settings with the choices for each; secrets only as set / not set. */
@Serializable
data class CccSettings(
    val language: String,
    val languages: List<Choice> = emptyList(),
    val groups: String,
    @SerialName("groups_choices") val groupsChoices: List<Choice> = emptyList(),
    @SerialName("continue_text") val continueText: String = "",
    @SerialName("usage_reserve") val usageReserve: Int? = null,
    @SerialName("reserve_choices") val reserveChoices: List<Int> = emptyList(),
    @SerialName("review_model") val reviewModel: String = "",
    @SerialName("review_models") val reviewModels: List<Choice> = emptyList(),
    @SerialName("context_window") val contextWindow: Int? = null,
    @SerialName("window_choices") val windowChoices: List<Int> = emptyList(),
    @SerialName("context_warn") val contextWarn: Int = 75,
    @SerialName("context_danger") val contextDanger: Int = 90,
    @SerialName("threshold_choices") val thresholdChoices: List<Int> = emptyList(),
    @SerialName("context_notify") val contextNotify: Boolean = true,
    @SerialName("export_folder") val exportFolder: String = "",
    @SerialName("export_send") val exportSend: String = "",
    @SerialName("send_choices") val sendChoices: List<Choice> = emptyList(),
    @SerialName("archive_folder") val archiveFolder: String = "",
    val telegram: TelegramState = TelegramState(),
    val discord: DiscordState = DiscordState(),
    @SerialName("launch_presets") val launchPresets: List<String> = emptyList(),
)

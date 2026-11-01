package io.github.luquas95.ccc.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/** What ccc's API (src/ccc/api.py) returns; field names as in its JSON. */

@Serializable
data class Status(
    val version: String,
    val language: String,
    @SerialName("daemon_running") val daemonRunning: Boolean,
    val conversations: Int,
    val running: Int,
    @SerialName("needs_approval") val needsApproval: Int,
    /** A new ccc version on origin/main; null when ccc isn't looking. */
    val update: UpdateInfo? = null,
    /** Kept for older apps: ccc's checkout's app build (the app now looks at GitHub's releases). */
    @SerialName("android_build") val androidBuild: Int = 0,
)

@Serializable
data class UpdateInfo(
    val available: Boolean = false,
    val behind: Int = 0,
    @SerialName("remote_head") val remoteHead: String? = null,
    val commits: List<String> = emptyList(),
    val android: Boolean = false,
    val error: String? = null,
    @SerialName("can_apply") val canApply: Boolean = false,
    val reason: String? = null,
)

@Serializable
data class UpdateResult(val ok: Boolean = false, val message: String = "")

@Serializable
data class Group(val key: String, val title: String)

/** A conversation's state, as ccc's QueueStatus. */
enum class ConversationStatus {
    IDLE, RUNNING, WAITING_RETRY, BLOCKED_ERROR, PAUSED_LIMIT, UNKNOWN;

    companion object {
        fun of(value: String): ConversationStatus =
            entries.firstOrNull { it.name.equals(value, ignoreCase = true) } ?: UNKNOWN
    }
}

@Serializable
data class Conversation(
    val id: Int,
    val name: String,
    val path: String,
    val status: String,
    @SerialName("delivery_mode") val deliveryMode: String,
    val archived: Boolean = false,
    val paused: Boolean = false,
    @SerialName("auto_continue") val autoContinue: Boolean = true,
    val pending: Int = 0,
    @SerialName("tokens_today") val tokensToday: Long = 0,
    @SerialName("needs_approval") val needsApproval: Boolean = false,
    val unseen: Boolean = false,
    @SerialName("last_error") val lastError: String? = null,
    @SerialName("next_retry_at") val nextRetryAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    val group: Group? = null,
    val context: ContextFill? = null,
    val git: GitState? = null,
    val goal: GoalBrief? = null,
) {
    val state: ConversationStatus get() = ConversationStatus.of(status)
}

/** Its latest goal loop for the list: while it runs and for a day after it ended (`goal` is null otherwise). */
@Serializable
data class GoalBrief(
    val id: Int,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    @SerialName("phase_label") val phaseLabel: String = "",
    val round: Int = 1,
    @SerialName("max_rounds") val maxRounds: Int = 1,
) {
    val running: Boolean get() = status == "running"
    val icon: String get() = when (status) { "running" -> "◎"; "passed" -> "✅"; "stopped" -> "■"; "error" -> "✖"; else -> "⛔" }
}

/** How full the context window is; `level` is "", "warn" or "danger" by ccc's Settings thresholds. */
@Serializable
data class ContextFill(
    val tokens: Int,
    val percent: Int? = null,
    val level: String = "",
) {
    /** 62 % (or 124k when the window is unknown). */
    val text: String get() = percent?.let { "$it %" } ?: if (tokens >= 1000) "${tokens / 1000}k" else tokens.toString()
}

/** The folder's branch and what is uncommitted / ahead / behind (null counts: no base to compare). */
@Serializable
data class GitState(
    val branch: String? = null,
    val added: Int = 0,
    val removed: Int = 0,
    val ahead: Int? = null,
    val behind: Int? = null,
) {
    /** feature-x +12−3 ↑2 */
    val text: String get() = buildList {
        branch?.let { add(it) }
        val lines = (if (added > 0) "+$added" else "") + (if (removed > 0) "−$removed" else "")
        if (lines.isNotEmpty()) add(lines)
        if ((ahead ?: 0) > 0) add("↑$ahead")
        if ((behind ?: 0) > 0) add("↓$behind")
    }.joinToString(" ")
}

/** The folder cut from the front: …/projects/shop-api — the last two folders stay. */
fun shortPath(path: String): String {
    val parts = path.trimEnd('/').split('/').filter { it.isNotEmpty() }
    return if (parts.size <= 2) path else "…/" + parts.takeLast(2).joinToString("/")
}

@Serializable
data class Queued(
    val id: Int,
    val text: String,
    @SerialName("not_before") val notBefore: String? = null,
)

@Serializable
data class Permission(
    val id: Int,
    @SerialName("conversation_id") val conversationId: Int,
    val tool: String,
    val input: JsonObject = JsonObject(emptyMap()),
    @SerialName("created_at") val createdAt: String? = null,
    /** The conversation's name (only in the list of every approval). */
    val conversation: String? = null,
)

@Serializable
data class ConversationDetail(
    val id: Int,
    val name: String,
    val path: String,
    val status: String,
    @SerialName("delivery_mode") val deliveryMode: String,
    val archived: Boolean = false,
    val paused: Boolean = false,
    val pending: Int = 0,
    val unseen: Boolean = false,
    @SerialName("last_error") val lastError: String? = null,
    @SerialName("next_retry_at") val nextRetryAt: String? = null,
    val group: Group? = null,
    val flags: String = "",
    @SerialName("remote_control_url") val remoteControlUrl: String? = null,
    val queued: List<Queued> = emptyList(),
    val permissions: List<Permission> = emptyList(),
) {
    val state: ConversationStatus get() = ConversationStatus.of(status)
}

/** One transcript event: kind is "human", "assistant_text", "tool_call" or "tool_result". */
@Serializable
data class Message(
    val index: Int,
    val kind: String,
    val text: String,
    val time: String? = null,
    @SerialName("tool_use_id") val toolUseId: String? = null,
    val detail: String? = null,
)

@Serializable
data class Messages(val total: Int, val messages: List<Message>)

@Serializable
data class UsageWindow(val percent: Double, @SerialName("resets_at") val resetsAt: String? = null)

@Serializable
data class ModelUsage(val model: String, val percent: Double, @SerialName("resets_at") val resetsAt: String? = null)

@Serializable
data class Usage(
    @SerialName("five_hour") val fiveHour: UsageWindow? = null,
    @SerialName("seven_day") val sevenDay: UsageWindow? = null,
    @SerialName("per_model") val perModel: List<ModelUsage> = emptyList(),
)

@Serializable
data class LaunchOption(val key: String, val label: String)

@Serializable
data class LaunchGroup(
    val key: String,
    val title: String,
    val exclusive: Boolean,
    val required: Boolean,
    val options: List<LaunchOption>,
)

@Serializable
data class LaunchOptions(val groups: List<LaunchGroup>, val default: List<String>)

@Serializable
data class NewConversation(
    val path: String,
    val name: String = "",
    val options: List<String>,
    val pr: String = "",
    @SerialName("session_id") val sessionId: String = "",
    @SerialName("remote_control") val remoteControl: Boolean = false,
    @SerialName("auto_continue") val autoContinue: Boolean = true,
    val prompt: String = "",
)

@Serializable
data class Groups(val mode: String, val own: List<String> = emptyList())

@Serializable
data class SearchHit(
    @SerialName("conversation_id") val conversationId: Int,
    val name: String,
    val time: String? = null,
    val kind: String,
    val snippet: String,
)

@Serializable
data class Export(val filename: String, val markdown: String)

/** A conversation that needs you: kind is "approval", "error", "limit" or "done". */
@Serializable
data class Waiting(
    @SerialName("conversation_id") val conversationId: Int,
    val name: String,
    val kind: String,
    val label: String,
)

@Serializable
data class PromptPreset(
    val number: Int,
    val name: String,
    val text: String,
    @SerialName("send_now") val sendNow: Boolean = false,
)

/** A New conversation preset (or the last choice): options and the two switches. */
@Serializable
data class LaunchChoice(
    val options: List<String>,
    @SerialName("auto_continue") val autoContinue: Boolean = true,
    @SerialName("remote_control") val remoteControl: Boolean = false,
    val name: String? = null,
)

@Serializable
data class LaunchPresets(val last: LaunchChoice? = null, val presets: List<LaunchChoice> = emptyList())

/** A Claude Code session recorded in a folder (to resume). */
@Serializable
data class Session(
    @SerialName("session_id") val sessionId: String,
    val modified: String? = null,
    @SerialName("first_prompt") val firstPrompt: String = "",
    val messages: Int = 0,
)

@Serializable
data class Task(
    val id: Int,
    val text: String,
    @SerialName("not_before") val notBefore: String? = null,
    @SerialName("by_routine") val byRoutine: Boolean = false,
)

/** A conversation's task queue and its two switches. */
@Serializable
data class Tasks(
    val paused: Boolean = false,
    @SerialName("auto_continue") val autoContinue: Boolean = true,
    val tasks: List<Task> = emptyList(),
)

/** One run of a task: status is "success", "rate_limited" or "error". */
@Serializable
data class Run(
    val id: Int,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
    val status: String,
    val tokens: Long = 0,
    @SerialName("cost_usd") val costUsd: Double = 0.0,
    @SerialName("duration_ms") val durationMs: Long = 0,
    val task: String = "",
    val result: String? = null,
    val error: String? = null,
    val commit: String? = null,
    @SerialName("git_note") val gitNote: String? = null,
    @SerialName("reverted_by") val revertedBy: String? = null,
)

/** A diff line: kind is "header", "meta", "hunk", "added", "removed" or "context". */
@Serializable
data class DiffLine(
    val index: Int,
    val text: String,
    val kind: String,
    val path: String? = null,
    @SerialName("old_line") val oldLine: Int? = null,
    @SerialName("new_line") val newLine: Int? = null,
    val commentable: Boolean = false,
)

@Serializable
data class Diff(val commit: String, val task: String = "", val lines: List<DiffLine> = emptyList())

@Serializable
data class Change(
    val conversations: List<Int> = emptyList(),
    val removed: List<Int> = emptyList(),
    /** A new ccc version was found (or taken). */
    val update: Boolean = false,
)

/** What the events stream says. */
sealed interface ServerEvent {
    /** The stream is open: whatever happened while it wasn't, fetch it now. */
    data object Connected : ServerEvent

    data class Changed(val change: Change) : ServerEvent
}

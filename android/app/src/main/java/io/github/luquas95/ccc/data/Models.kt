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
)

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
    @SerialName("needs_approval") val needsApproval: Boolean = false,
    val unseen: Boolean = false,
    @SerialName("last_error") val lastError: String? = null,
    @SerialName("next_retry_at") val nextRetryAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    val group: Group? = null,
) {
    val state: ConversationStatus get() = ConversationStatus.of(status)
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
    @SerialName("remote_control") val remoteControl: Boolean = false,
    @SerialName("auto_continue") val autoContinue: Boolean = true,
    val prompt: String = "",
)

@Serializable
data class Change(val conversations: List<Int> = emptyList(), val removed: List<Int> = emptyList())

/** What the events stream says. */
sealed interface ServerEvent {
    /** The stream is open: whatever happened while it wasn't, fetch it now. */
    data object Connected : ServerEvent

    data class Changed(val change: Change) : ServerEvent
}

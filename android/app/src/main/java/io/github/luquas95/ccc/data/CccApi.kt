package io.github.luquas95.ccc.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/** An error answer of ccc's API; [message] is ccc's own text, in its language. */
class ApiException(val code: Int, message: String) : IOException(message)

/**
 * ccc's HTTP API (src/ccc/api.py) at [server] — e.g.
 * https://computer.tailnet.ts.net, with or without /api/v1 — signed in
 * with [token] (`ccc api token`, or the one POST /pair gave this phone).
 */
class CccApi(
    server: String,
    private val token: String = "",
    private val client: OkHttpClient = defaultClient,
    /** Called (on any thread) when ccc refuses the token with 401: this phone was signed out on the computer. */
    private val onUnauthorized: () -> Unit = {},
) {
    private val base: HttpUrl = baseUrl(server) ?: throw IllegalArgumentException(server)
    // The events stream stays open: no read timeout (ccc sends a keepalive every 15 s).
    private val streamClient = client.newBuilder().readTimeout(0, TimeUnit.SECONDS).build()

    suspend fun status(): Status = get("status")

    /** Trade the one-time [code] of a QR code for a token of this phone's own (the one call that needs no token). */
    suspend fun pair(code: String, name: String): PairResult = call(
        Request.Builder().url(base.newBuilder().addPathSegments("pair").build())
            .post(body("code" to JsonPrimitive(code), "name" to JsonPrimitive(name)).toRequestBody(JSON)).build(),
    )

    /** The phones signed in, this one marked [Device.current]. */
    suspend fun devices(): List<Device> = get<Devices>("devices").devices

    /** Sign a phone out at once (this one too). */
    suspend fun removeDevice(id: Int) {
        call<Unit>(request("devices/$id").delete().build())
    }

    /** Update ccc (git pull, install, restart); an error says why not (a task is running …). */
    suspend fun applyUpdate(): UpdateResult = post("update", "{}")

    suspend fun conversations(archived: Boolean = false): List<Conversation> =
        get("conversations", if (archived) mapOf("archived" to "1") else emptyMap())

    suspend fun conversation(id: Int): ConversationDetail = get("conversations/$id")

    /** Transcript events: the newest [limit], or those after / before an index. */
    suspend fun messages(id: Int, after: Int? = null, before: Int? = null, limit: Int = 100): Messages =
        get(
            "conversations/$id/messages",
            buildMap {
                after?.let { put("after", it.toString()) }
                before?.let { put("before", it.toString()) }
                put("limit", limit.toString())
            },
        )

    suspend fun send(id: Int, text: String) {
        post<Unit>("conversations/$id/messages", json.encodeToString(TextBody.serializer(), TextBody(text)))
    }

    suspend fun retry(id: Int) {
        post<Unit>("conversations/$id/retry", "{}")
    }

    suspend fun markSeen(id: Int) {
        post<Unit>("conversations/$id/seen", "{}")
    }

    suspend fun create(request: NewConversation): ConversationDetail =
        post("conversations", json.encodeToString(NewConversation.serializer(), request))

    /** Into the Archive (true) or back (false). */
    suspend fun archive(id: Int, archived: Boolean): ConversationDetail =
        post("conversations/$id/archive", """{"archived":$archived}""")

    /** Out of ccc with its tasks and history (not while it runs); Claude Code's transcript stays. */
    suspend fun delete(id: Int) {
        call<Unit>(request("conversations/$id").delete().build())
    }

    /** Into an own group ([name], made if new), or out of it (null). */
    suspend fun setGroup(id: Int, name: String?): ConversationDetail =
        post("conversations/$id/group", json.encodeToString(NameBody.serializer(), NameBody(name)))

    suspend fun groups(): Groups = get("groups")

    suspend fun renameGroup(old: String, new: String): Groups =
        post("groups/rename", json.encodeToString(RenameBody.serializer(), RenameBody(old, new)))

    suspend fun deleteGroup(name: String): Groups =
        post("groups/delete", json.encodeToString(NameBody.serializer(), NameBody(name)))

    suspend fun search(text: String): List<SearchHit> = get("search", mapOf("q" to text))

    suspend fun export(id: Int): Export = get("conversations/$id/export")

    /** Files of the conversation's folder for an @-mention, best first. */
    suspend fun files(id: Int, text: String): List<String> = get("conversations/$id/files", mapOf("q" to text))

    suspend fun waiting(): List<Waiting> = get("waiting")

    suspend fun promptPresets(): List<PromptPreset> = get("prompt-presets")

    suspend fun launchPresets(): LaunchPresets = get("launch-presets")

    suspend fun mcpServers(path: String): List<String> = get("mcp-servers", mapOf("path" to path))

    suspend fun sessions(path: String): List<Session> = get("sessions", mapOf("path" to path))

    suspend fun tasks(id: Int): Tasks = get("conversations/$id/tasks")

    /** [whenText]: empty (as soon as possible), HH:MM, YYYY-MM-DD HH:MM or "reset". */
    suspend fun addTask(id: Int, text: String, whenText: String) {
        post<Unit>("conversations/$id/tasks", body("text" to JsonPrimitive(text), "when" to JsonPrimitive(whenText)))
    }

    suspend fun editTask(taskId: Int, text: String, whenText: String): Tasks =
        post("tasks/$taskId", body("text" to JsonPrimitive(text), "when" to JsonPrimitive(whenText)))

    suspend fun removeTask(taskId: Int): Tasks = call(request("tasks/$taskId").delete().build())

    suspend fun moveTask(taskId: Int, delta: Int): Tasks = post("tasks/$taskId/move", body("delta" to JsonPrimitive(delta)))

    suspend fun switches(id: Int, paused: Boolean? = null, autoContinue: Boolean? = null): Tasks =
        post(
            "conversations/$id/switches",
            body(*listOfNotNull(paused?.let { "paused" to JsonPrimitive(it) },
                autoContinue?.let { "auto_continue" to JsonPrimitive(it) }).toTypedArray()),
        )

    suspend fun runs(id: Int): List<Run> = get("conversations/$id/runs")

    suspend fun diff(runId: Int): Diff = get("runs/$runId/diff")

    /** Comments on diff lines (index to text), sent to Claude as one task. */
    suspend fun comment(runId: Int, comments: Map<Int, String>) {
        val list = JsonArray(comments.entries.sortedBy { it.key }.map { (index, text) ->
            JsonObject(mapOf("index" to JsonPrimitive(index), "text" to JsonPrimitive(text)))
        })
        post<Unit>("runs/$runId/comments", body("comments" to list))
    }

    /** Undo the run's commit (a new commit); [tell] queues a note for Claude. */
    suspend fun revert(runId: Int, tell: Boolean) {
        post<Unit>("runs/$runId/revert", body("tell" to JsonPrimitive(tell)))
    }

    // --- reviews, goals, workflows, questions ----------------------------------------------

    suspend fun reviews(id: Int): Reviews = get("conversations/$id/reviews")

    suspend fun requestReview(id: Int, instructions: String, untilPass: Boolean, rounds: Int?): Reviews =
        post("conversations/$id/reviews", body("instructions" to JsonPrimitive(instructions),
            "until_pass" to JsonPrimitive(untilPass), "rounds" to JsonPrimitive(rounds)))

    suspend fun stopReview(id: Int): Reviews = post("conversations/$id/reviews/stop", "{}")

    suspend fun applyReview(reviewId: Int): Reviews = post("reviews/$reviewId/apply", "{}")

    suspend fun goals(id: Int): Goals = get("conversations/$id/goals")

    suspend fun startGoal(id: Int, goal: String, check: String, rounds: Int?): Goals =
        post("conversations/$id/goals", body("goal" to JsonPrimitive(goal), "check" to JsonPrimitive(check),
            "rounds" to JsonPrimitive(rounds)))

    suspend fun stopGoal(id: Int): Goals = post("conversations/$id/goals/stop", "{}")

    suspend fun workflowTemplates(): List<WorkflowTemplate> = get("workflow-templates")

    suspend fun workflows(id: Int): Workflows = get("conversations/$id/workflows")

    suspend fun startWorkflow(id: Int, template: String, task: String, check: String, rounds: Int?): Workflows =
        post("conversations/$id/workflows", body("template" to JsonPrimitive(template), "task" to JsonPrimitive(task),
            "check" to JsonPrimitive(check), "rounds" to JsonPrimitive(rounds)))

    suspend fun answerWorkflow(id: Int, approve: Boolean, note: String): Workflows =
        post("conversations/$id/workflows/answer", body("approve" to JsonPrimitive(approve), "note" to JsonPrimitive(note)))

    suspend fun stopWorkflow(id: Int): Workflows = post("conversations/$id/workflows/stop", "{}")

    suspend fun asks(id: Int): List<AskItem> = get("conversations/$id/asks")

    suspend fun ask(id: Int, to: Int, question: String, deliver: Boolean): List<AskItem> =
        post("conversations/$id/asks", body("to" to JsonPrimitive(to), "question" to JsonPrimitive(question),
            "deliver" to JsonPrimitive(deliver)))

    suspend fun cancelAsk(askId: Int) {
        post<Unit>("asks/$askId/cancel", "{}")
    }

    // --- routines, live sessions, analytics, settings ---------------------------------------

    suspend fun routines(): Routines = get("routines")

    private fun routineBody(r: Routine): String = body(
        "conversation_id" to JsonPrimitive(r.conversationId), "name" to JsonPrimitive(r.name),
        "prompt" to JsonPrimitive(r.prompt), "kind" to JsonPrimitive(r.kind), "value" to JsonPrimitive(r.value),
        "fresh" to JsonPrimitive(r.fresh),
    )

    /** [routine]'s id is ignored: a new one. */
    suspend fun addRoutine(routine: Routine): Routines = post("routines", routineBody(routine))

    suspend fun editRoutine(routine: Routine): Routines = post("routines/${routine.id}", routineBody(routine))

    suspend fun deleteRoutine(id: Int): Routines = call(request("routines/$id").delete().build())

    suspend fun enableRoutine(id: Int, enabled: Boolean): Routines =
        post("routines/$id/enabled", body("enabled" to JsonPrimitive(enabled)))

    suspend fun runRoutine(id: Int): RoutineRun = post("routines/$id/run", "{}")

    suspend fun liveSessions(): List<LiveSession> = get("live-sessions")

    suspend fun promptLiveSession(sessionId: String, prompt: String) {
        post<Unit>("live-sessions/$sessionId/prompt", body("prompt" to JsonPrimitive(prompt)))
    }

    suspend fun analytics(year: Int?, month: Int?): Analytics =
        get("analytics", buildMap {
            year?.let { put("year", it.toString()) }
            month?.let { put("month", it.toString()) }
        })

    suspend fun archiveAnalytics() {
        post<Unit>("analytics/archive", "{}")
    }

    suspend fun settings(): CccSettings = get("settings")

    /** Only the keys given change (see /settings in ccc's API). */
    suspend fun changeSettings(changes: Map<String, JsonElement>): CccSettings =
        post("settings", json.encodeToString(JsonObject.serializer(), JsonObject(changes)))

    suspend fun settingsAction(action: String) {
        post<Unit>("settings/$action", "{}")
    }

    suspend fun savePromptPresets(presets: List<PromptPreset>): List<PromptPreset> =
        post("prompt-presets", body("presets" to JsonArray(presets.map {
            JsonObject(mapOf("name" to JsonPrimitive(it.name), "text" to JsonPrimitive(it.text),
                "send_now" to JsonPrimitive(it.sendNow)))
        })))

    suspend fun deleteLaunchPreset(name: String) {
        post<Unit>("launch-presets/delete", body("name" to JsonPrimitive(name)))
    }

    suspend fun saveLaunchPreset(choice: LaunchChoice) {
        post<Unit>("launch-presets", json.encodeToString(LaunchChoice.serializer(), choice))
    }

    suspend fun backup() {
        post<Unit>("backup", "{}")
    }

    suspend fun terminal(id: Int): Terminal = get("conversations/$id/terminal")

    /** Text into the conversation's Claude Code as one paste (and Enter, unless [submit] is false). */
    suspend fun terminalPaste(id: Int, text: String, submit: Boolean): Terminal =
        post("conversations/$id/terminal", body("paste" to JsonPrimitive(text), "submit" to JsonPrimitive(submit)))

    /** tmux key names: Enter, Escape, Tab, BTab, Up, Down, Left, Right, C-c … */
    suspend fun terminalKeys(id: Int, keys: List<String>): Terminal =
        post("conversations/$id/terminal", body("keys" to JsonArray(keys.map { JsonPrimitive(it) })))

    /** A few characters as typed (an answer to a menu). */
    suspend fun terminalType(id: Int, text: String): Terminal = post("conversations/$id/terminal", body("type" to JsonPrimitive(text)))

    suspend fun permissions(): List<Permission> = get("permissions")

    /** [decision]: "allow", "always" (this tool in this conversation from now on) or "deny". */
    suspend fun decide(permissionId: Int, decision: String) {
        post<Unit>("permissions/$permissionId", json.encodeToString(DecisionBody.serializer(), DecisionBody(decision)))
    }

    suspend fun usage(): Usage? = get("usage")

    suspend fun projects(): List<String> = get("projects")

    suspend fun launchOptions(): LaunchOptions = get("launch-options")

    /** The events stream: [ServerEvent.Connected] once open, then every change; ends when ccc closes it. */
    fun events(): Flow<ServerEvent> = flow {
        val call = streamClient.newCall(request("events").get().build())
        currentCoroutineContext()[Job]?.invokeOnCompletion { call.cancel() }
        call.execute().use { response ->
            if (!response.isSuccessful) throw error(response.code, response.body.string())
            emit(ServerEvent.Connected)
            val source = response.body.source()
            val parser = SseParser()
            while (true) {
                val line = source.readUtf8Line() ?: break
                val event = parser.feed(line) ?: continue
                if (event.event == "changed") {
                    emit(ServerEvent.Changed(json.decodeFromString(Change.serializer(), event.data)))
                }
            }
        }
    }.flowOn(Dispatchers.IO)

    private suspend inline fun <reified T> get(path: String, query: Map<String, String> = emptyMap()): T =
        call(request(path, query).get().build())

    private suspend inline fun <reified T> post(path: String, body: String): T =
        call(request(path).post(body.toRequestBody(JSON)).build())

    private suspend inline fun <reified T> call(request: Request): T = withContext(Dispatchers.IO) {
        client.newCall(request).execute().use { response ->
            val body = response.body.string()
            if (!response.isSuccessful) throw error(response.code, body)
            if (T::class == Unit::class) Unit as T else json.decodeFromString<T>(body)
        }
    }

    private fun request(path: String, query: Map<String, String> = emptyMap()): Request.Builder {
        val url = base.newBuilder().addPathSegments(path).apply {
            query.forEach { (name, value) -> addQueryParameter(name, value) }
        }.build()
        return Request.Builder().url(url).header("Authorization", "Bearer $token")
    }

    private fun body(vararg fields: Pair<String, JsonElement>): String =
        json.encodeToString(JsonObject.serializer(), JsonObject(mapOf(*fields)))

    private fun error(code: Int, body: String): ApiException {
        val message = runCatching { json.decodeFromString(ErrorBody.serializer(), body).error }.getOrNull()
        if (code == 401 && token.isNotEmpty()) onUnauthorized()
        return ApiException(code, message ?: "HTTP $code")
    }

    @Serializable
    private data class TextBody(val text: String)

    @Serializable
    private data class DecisionBody(val decision: String)

    @Serializable
    private data class ErrorBody(val error: String)

    @Serializable
    private data class NameBody(val name: String?)

    @Serializable
    private data class RenameBody(val old: String, val new: String)

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
        }
        private val defaultClient = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        /** The API's base URL from what the user typed: https assumed, /api/v1 added. */
        fun baseUrl(server: String): HttpUrl? {
            var text = server.trim().trimEnd('/')
            if (text.isEmpty()) return null
            if (!text.contains("://")) text = "https://$text"
            if (!text.endsWith("/api/v1")) text += "/api/v1"
            return "$text/".toHttpUrlOrNull()
        }
    }
}

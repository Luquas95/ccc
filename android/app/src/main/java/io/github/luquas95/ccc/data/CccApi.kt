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
 * with [token] (`ccc api token`).
 */
class CccApi(
    server: String,
    private val token: String,
    private val client: OkHttpClient = defaultClient,
) {
    private val base: HttpUrl = baseUrl(server) ?: throw IllegalArgumentException(server)
    // The events stream stays open: no read timeout (ccc sends a keepalive every 15 s).
    private val streamClient = client.newBuilder().readTimeout(0, TimeUnit.SECONDS).build()

    suspend fun status(): Status = get("status")

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

    suspend fun sessions(path: String): List<Session> = get("sessions", mapOf("path" to path))

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

    private fun error(code: Int, body: String): ApiException {
        val message = runCatching { json.decodeFromString(ErrorBody.serializer(), body).error }.getOrNull()
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

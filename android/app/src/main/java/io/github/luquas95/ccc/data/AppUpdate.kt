package io.github.luquas95.ccc.data

import java.io.File
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request

/** A published version of the app: GitHub's release with the app attached. */
data class AppRelease(val version: String, val apkUrl: String, val notes: String)

/** Versions as "1.2.3" (a leading "v" is fine): the numbers, or null for anything else ("0.0.0-dev"). */
object Versions {
    fun parse(text: String): List<Int>? {
        val numbers = text.trim().removePrefix("v").split('.')
        if (numbers.size !in 2..4) return null
        return numbers.map { it.toIntOrNull() ?: return null }
    }

    /** [latest] is newer than [installed]; false when either isn't a version (a build made by hand never asks). */
    fun isNewer(latest: String, installed: String): Boolean {
        val new = parse(latest) ?: return false
        val old = parse(installed) ?: return false
        for (i in 0 until maxOf(new.size, old.size)) {
            val a = new.getOrElse(i) { 0 }
            val b = old.getOrElse(i) { 0 }
            if (a != b) return a > b
        }
        return false
    }
}

@Serializable
private data class ReleaseJson(
    @SerialName("tag_name") val tag: String,
    val body: String? = null,
    val draft: Boolean = false,
    val prerelease: Boolean = false,
    val assets: List<AssetJson> = emptyList(),
)

@Serializable
private data class AssetJson(val name: String, @SerialName("browser_download_url") val url: String)

private val json = Json { ignoreUnknownKeys = true }

/** GitHub's answer for releases/latest as an [AppRelease]; null for a release without the app (ccc.apk) or a tag that isn't a version. */
fun parseRelease(text: String): AppRelease? {
    val release = runCatching { json.decodeFromString(ReleaseJson.serializer(), text) }.getOrNull() ?: return null
    if (release.draft || release.prerelease || Versions.parse(release.tag) == null) return null
    val apk = release.assets.firstOrNull { it.name == APK_NAME } ?: return null
    return AppRelease(release.tag.removePrefix("v"), apk.url, release.body.orEmpty().trim())
}

const val APK_NAME = "ccc.apk"

/**
 * The app's releases on GitHub (public repository): nothing is sent but the request itself —
 * not ccc's token, which this class doesn't know.
 */
class ReleaseApi(
    private val repo: String = "Luquas95/ccc",
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(60, java.util.concurrent.TimeUnit.SECONDS)
        .build(),
    private val base: String = "https://api.github.com",
) {
    /** The newest release with the app, or null when there is none (or GitHub says no). */
    suspend fun latest(): AppRelease? = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$base/repos/$repo/releases/latest")
            .header("Accept", "application/vnd.github+json").build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@use null
            parseRelease(response.body?.string().orEmpty())
        }
    }

    /** Download the app to [target]; [progress] gets the share (0..1) as it comes. */
    suspend fun download(url: String, target: File, progress: (Float) -> Unit = {}) = withContext(Dispatchers.IO) {
        client.newCall(Request.Builder().url(url).build()).execute().use { response ->
            if (!response.isSuccessful) throw IOException("HTTP ${response.code}")
            val body = response.body ?: throw IOException("empty")
            val total = body.contentLength().coerceAtLeast(1)
            target.parentFile?.mkdirs()
            val part = File(target.path + ".part")
            body.byteStream().use { input ->
                part.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var done = 0L
                    while (true) {
                        val n = input.read(buffer)
                        if (n < 0) break
                        output.write(buffer, 0, n)
                        done += n
                        progress((done.toFloat() / total).coerceAtMost(1f))
                    }
                }
            }
            if (!part.renameTo(target)) throw IOException("rename")
        }
    }
}

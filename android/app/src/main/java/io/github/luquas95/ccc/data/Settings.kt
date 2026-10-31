package io.github.luquas95.ccc.data

import android.content.Context

/**
 * Where ccc is and the token: in the app's private preferences, which no
 * other app can read (and which aren't backed up, see the manifest).
 */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("ccc", Context.MODE_PRIVATE)

    val server: String get() = prefs.getString(SERVER, "").orEmpty()
    val token: String get() = prefs.getString(TOKEN, "").orEmpty()
    val configured: Boolean get() = server.isNotBlank() && token.isNotBlank()

    /** Notifications while the app is closed (the watch service). */
    var notifications: Boolean
        get() = prefs.getBoolean(NOTIFICATIONS, false)
        set(value) = prefs.edit().putBoolean(NOTIFICATIONS, value).apply()

    /** The app's own language: "" = follow the phone, otherwise a language tag ("en", "cs"); not the computer's or ccc's. */
    var language: String
        get() = prefs.getString(LANGUAGE, "").orEmpty()
        set(value) = prefs.edit().putString(LANGUAGE, value).apply()

    /** What the conversation list shows besides the name and state (ListDetail keys). */
    var listDetails: Set<String>
        get() = prefs.getStringSet(LIST_DETAILS, null) ?: ListDetail.DEFAULT
        set(value) = prefs.edit().putStringSet(LIST_DETAILS, value).apply()

    /** Keys of the alerts shown (see Alerts), so a restart doesn't show them again. */
    var shownAlerts: Set<String>
        get() = prefs.getStringSet(SHOWN, emptySet()).orEmpty().toSet()
        set(value) = prefs.edit().putStringSet(SHOWN, value).apply()

    fun save(server: String, token: String) {
        prefs.edit().putString(SERVER, server.trim()).putString(TOKEN, token.trim()).apply()
    }

    fun clear() {
        // The language is the app's own choice, not part of the connection: it stays.
        val language = language
        prefs.edit().clear().putString(LANGUAGE, language).apply()
    }

    private companion object {
        const val SERVER = "server"
        const val TOKEN = "token"
        const val NOTIFICATIONS = "notifications"
        const val SHOWN = "shown_alerts"
        const val LIST_DETAILS = "list_details"
        const val LANGUAGE = "language"
    }
}

/** The things a conversation's row can show besides its name and state: on the phone, as chosen. */
object ListDetail {
    const val PENDING = "pending"
    const val CONTEXT = "context"
    const val GIT = "git"
    const val PATH = "path"

    val ALL = listOf(PENDING, CONTEXT, GIT, PATH)
    val DEFAULT: Set<String> = setOf(PENDING, CONTEXT, GIT)
}

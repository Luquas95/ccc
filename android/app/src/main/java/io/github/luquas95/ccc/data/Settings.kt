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

    fun save(server: String, token: String) {
        prefs.edit().putString(SERVER, server.trim()).putString(TOKEN, token.trim()).apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    private companion object {
        const val SERVER = "server"
        const val TOKEN = "token"
    }
}

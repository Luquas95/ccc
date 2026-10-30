package io.github.luquas95.ccc.data

import java.net.URLDecoder
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/** What the QR code of `ccc api pair` holds: where ccc is and a one-time code to trade for a token. */
data class PairingInvite(val server: String, val code: String)

object Pairing {
    private const val PREFIX = "ccc://pair?"

    /** The invite in [text] (src/ccc/pairing.py `payload`: ccc://pair?server=…&code=…), or null for any other QR. */
    fun parse(text: String): PairingInvite? {
        val query = text.trim().takeIf { it.startsWith(PREFIX) }?.removePrefix(PREFIX) ?: return null
        val fields = query.split('&').mapNotNull { part ->
            val (name, value) = part.split('=', limit = 2).takeIf { it.size == 2 } ?: return@mapNotNull null
            name to runCatching { URLDecoder.decode(value, "UTF-8") }.getOrNull()
        }.toMap()
        val server = fields["server"]?.trim().orEmpty()
        val code = fields["code"]?.trim().orEmpty()
        return if (code.isEmpty() || !trusted(server)) null else PairingInvite(server, code)
    }

    /**
     * Whether [server] may be signed in to from a QR code: https, or plain http only to a private or
     * Tailscale address (what `ccc api pair --server` can give), and no user:password@ in front of the host.
     * Anyone can print a QR code, so the app also shows the host and asks before it pairs.
     */
    fun trusted(server: String): Boolean {
        val url = server.toHttpUrlOrNull() ?: return false
        if (url.username.isNotEmpty() || url.password.isNotEmpty()) return false
        return url.isHttps || isPrivate(url.host)
    }

    private fun isPrivate(host: String): Boolean {
        if (host == "localhost") return true
        val octets = host.split('.').map { it.toIntOrNull() ?: return false }
        if (octets.size != 4 || octets.any { it !in 0..255 }) return false
        val (a, b) = octets
        return a == 10 || a == 127 || (a == 192 && b == 168) || (a == 172 && b in 16..31) || (a == 100 && b in 64..127)
    }
}

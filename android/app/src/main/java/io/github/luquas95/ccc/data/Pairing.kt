package io.github.luquas95.ccc.data

import java.net.URLDecoder

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
        return if (server.isEmpty() || code.isEmpty()) null else PairingInvite(server, code)
    }
}

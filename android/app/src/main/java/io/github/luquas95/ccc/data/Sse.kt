package io.github.luquas95.ccc.data

/** One Server-Sent Event. */
data class SseEvent(val event: String, val data: String)

/**
 * Turns the lines of a Server-Sent Events stream into events: "event:"
 * and "data:" lines up to a blank line make one; ":" lines are comments
 * (ccc's keepalive).
 */
class SseParser {
    private var event = ""
    private val data = StringBuilder()

    /** Feed one line (without its line break); returns an event when one is complete. */
    fun feed(line: String): SseEvent? {
        if (line.isEmpty()) {
            if (event.isEmpty() && data.isEmpty()) return null
            val complete = SseEvent(event.ifEmpty { "message" }, data.toString())
            event = ""
            data.clear()
            return complete
        }
        if (line.startsWith(":")) return null
        val field = line.substringBefore(":")
        val value = line.substringAfter(":", "").removePrefix(" ")
        when (field) {
            "event" -> event = value
            "data" -> {
                if (data.isNotEmpty()) data.append('\n')
                data.append(value)
            }
        }
        return null
    }
}

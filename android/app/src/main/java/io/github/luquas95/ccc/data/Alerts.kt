package io.github.luquas95.ccc.data

/** What to tell the phone about: an approval to answer, or a conversation that needs you. */
sealed interface Alert {
    /** Stable across checks: the same alert is shown once. */
    val key: String

    data class Approval(val permission: Permission) : Alert {
        override val key get() = "p:${permission.id}"
    }

    data class NeedsYou(val waiting: Waiting) : Alert {
        override val key get() = "w:${waiting.conversationId}:${waiting.kind}"
    }
}

/** The outcome of one check: alerts to show, and keys of shown ones that are over (to take away). */
data class AlertChanges(val show: List<Alert>, val gone: Set<String>)

/**
 * Which alerts are new since the last check. An approval is an alert of
 * its own; a conversation needing you for something else (an error, a
 * limit, a finished reply) is one per conversation and kind — shown again
 * only after it stopped needing you.
 */
object Alerts {
    fun changes(permissions: List<Permission>, waiting: List<Waiting>, shown: Set<String>): AlertChanges {
        val now = permissions.map(Alert::Approval) + waiting.filter { it.kind != "approval" }.map(Alert::NeedsYou)
        val keys = now.map { it.key }.toSet()
        return AlertChanges(show = now.filter { it.key !in shown }, gone = shown - keys)
    }
}

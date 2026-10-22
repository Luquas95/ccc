package io.github.luquas95.ccc.data

import org.junit.Assert.assertEquals
import org.junit.Test

class AlertsTest {
    private val bash = Permission(5, 1, "Bash", conversation = "shop-api")
    private val error = Waiting(3, "data-pipeline", "error", "error")
    private val approvalWaiting = Waiting(1, "shop-api", "approval", "waits for approval")

    @Test
    fun `new approvals and conversations that need you are shown once`() {
        val first = Alerts.changes(listOf(bash), listOf(approvalWaiting, error), emptySet())
        assertEquals(listOf(Alert.Approval(bash), Alert.NeedsYou(error)), first.show)
        assertEquals(emptySet<String>(), first.gone)

        val again = Alerts.changes(listOf(bash), listOf(approvalWaiting, error), first.show.map { it.key }.toSet())
        assertEquals(emptyList<Alert>(), again.show)
    }

    @Test
    fun `an answered approval or a fixed conversation goes away`() {
        val shown = setOf("p:5", "w:3:error")
        val after = Alerts.changes(emptyList(), emptyList(), shown)
        assertEquals(shown, after.gone)
        // Needs you again later: shown again, since it was taken away.
        assertEquals(listOf(Alert.NeedsYou(error)), Alerts.changes(emptyList(), listOf(error), emptySet()).show)
    }
}

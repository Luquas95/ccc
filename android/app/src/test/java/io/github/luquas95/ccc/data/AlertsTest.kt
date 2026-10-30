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

    @Test
    fun `a new ccc version is told once, and again for the next one`() {
        val update = UpdateInfo(available = true, behind = 3, remoteHead = "a1b2c3d")
        val first = Alerts.changes(emptyList(), emptyList(), emptySet(), update)
        assertEquals(listOf(Alert.Update(3, "a1b2c3d")), first.show)
        assertEquals(emptyList<Alert>(), Alerts.changes(emptyList(), emptyList(), first.show.map { it.key }.toSet(), update).show)
        val next = update.copy(remoteHead = "e4f5a6b", behind = 4)
        assertEquals(listOf(Alert.Update(4, "e4f5a6b")), Alerts.changes(emptyList(), emptyList(), setOf("u:a1b2c3d"), next).show)
        // Updated: it goes away.
        assertEquals(setOf("u:a1b2c3d"), Alerts.changes(emptyList(), emptyList(), setOf("u:a1b2c3d"), UpdateInfo()).gone)
        assertEquals(emptyList<Alert>(), Alerts.changes(emptyList(), emptyList(), emptySet(), UpdateInfo(available = true)).show)
    }
}

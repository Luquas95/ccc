package io.github.luquas95.ccc.ui

import io.github.luquas95.ccc.data.LaunchGroup
import io.github.luquas95.ccc.data.LaunchOption
import org.junit.Assert.assertEquals
import org.junit.Test

/** The New conversation options behave as launch_options.toggle in ccc. */
class ToggleTest {
    private fun group(key: String, exclusive: Boolean, required: Boolean, vararg keys: String) =
        LaunchGroup(key, key, exclusive, required, keys.map { LaunchOption(it, it) })

    private val session = group("session", true, true, "session_new", "session_continue", "session_from_pr")
    private val extra = group("session_extra", false, false, "fork")
    private val model = group("model", true, false, "model_opus", "model_sonnet")
    private val mcp = group("mcp", false, false, "mcp_select")
    private val groups = listOf(session, extra, model, mcp)

    @Test
    fun `an exclusive group keeps one`() {
        val picked = toggle(model, listOf("session_new", "model_opus"), "model_sonnet", groups)
        assertEquals(listOf("session_new", "model_sonnet"), picked)
    }

    @Test
    fun `a required group can't be emptied, an optional one can`() {
        assertEquals(listOf("session_new"), toggle(session, listOf("session_new"), "session_new", groups))
        assertEquals(listOf("session_new"), toggle(model, listOf("session_new", "model_opus"), "model_opus", groups))
    }

    @Test
    fun `a new session drops the fork`() {
        val forked = toggle(extra, listOf("session_continue"), "fork", groups)
        assertEquals(listOf("session_continue", "fork"), forked)
        assertEquals(listOf("session_new"), toggle(session, forked, "session_new", groups))
    }

    @Test
    fun `ticking an MCP server turns the mode on, unticking the mode forgets the servers`() {
        val one = toggle(mcp, listOf("session_new"), "mcp:docs", groups)
        assertEquals(listOf("session_new", "mcp_select", "mcp:docs"), one)
        val two = toggle(mcp, one, "mcp:db", groups)
        assertEquals(listOf("session_new", "mcp_select", "mcp:db", "mcp:docs"), two)
        assertEquals(listOf("session_new", "mcp_select", "mcp:db"), toggle(mcp, two, "mcp:docs", groups))
        assertEquals(listOf("session_new"), toggle(mcp, two, "mcp_select", groups))
    }
}

class FilterMarkerTest {
    @Test
    fun `a marker chip adds or takes its marker, words stay`() {
        assertEquals("! api", toggleMarker("api", '!'))
        assertEquals("!? api", toggleMarker("! api", '?'))
        assertEquals("? api", toggleMarker("!? api", '!'))
        assertEquals("api", toggleMarker("? api", '?'))
        assertEquals("x", toggleMarker("", 'x'))
    }
}

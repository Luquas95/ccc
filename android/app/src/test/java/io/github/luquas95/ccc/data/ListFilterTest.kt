package io.github.luquas95.ccc.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ListFilterTest {
    private fun conversation(name: String, status: String = "idle", approval: Boolean = false, unseen: Boolean = false) =
        Conversation(1, name, "/home/you/projekty/$name", status, "interactive", needsApproval = approval, unseen = unseen)

    @Test
    fun `words match name and folder without case or diacritics`() {
        val filter = ListFilter.parse("PROJEKTY Šop")
        assertTrue(filter.matches(conversation("šop-api")))
        assertFalse(filter.matches(conversation("docs")))
    }

    @Test
    fun `markers are any of those states`() {
        val filter = ListFilter.parse("!? api")
        assertEquals(setOf('!', '?'), filter.states)
        assertTrue(filter.matches(conversation("api", status = "running")))
        assertTrue(filter.matches(conversation("api", approval = true)))
        assertFalse(filter.matches(conversation("api")))
        assertFalse(filter.matches(conversation("web", status = "running")))
        assertTrue(ListFilter.parse("x").matches(conversation("a", status = "blocked_error")))
        assertTrue(ListFilter.parse("*").matches(conversation("a", unseen = true)))
        assertFalse(ListFilter.parse("").active)
    }

    @Test
    fun `a mention is an at that starts a word`() {
        assertEquals(5 to "src/li", mentionAt("Look @src/li"))
        assertEquals(0 to "", mentionAt("@"))
        assertNull(mentionAt("mail me@example.com"))
        assertNull(mentionAt("@src done"))
    }
}

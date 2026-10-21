package io.github.luquas95.ccc.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SseParserTest {
    @Test
    fun `an event ends with a blank line`() {
        val parser = SseParser()
        assertNull(parser.feed("event: changed"))
        assertNull(parser.feed("data: {\"conversations\": [1]}"))
        assertEquals(SseEvent("changed", "{\"conversations\": [1]}"), parser.feed(""))
    }

    @Test
    fun `comments and lone blank lines are no events`() {
        val parser = SseParser()
        assertNull(parser.feed(": connected"))
        assertNull(parser.feed(""))
        assertNull(parser.feed(": keepalive"))
        assertNull(parser.feed(""))
    }

    @Test
    fun `data lines join, an unnamed event is a message`() {
        val parser = SseParser()
        parser.feed("data: one")
        parser.feed("data:two")
        assertEquals(SseEvent("message", "one\ntwo"), parser.feed(""))
        parser.feed("event: changed")
        parser.feed("data: x")
        assertEquals("changed", parser.feed("")?.event)
    }
}

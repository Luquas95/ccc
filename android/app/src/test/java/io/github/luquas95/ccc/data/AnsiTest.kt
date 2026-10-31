package io.github.luquas95.ccc.data

import org.junit.Assert.assertEquals
import org.junit.Test

class AnsiTest {
    @Test
    fun `colours and bold become styles, reset ends them`() {
        val parsed = Ansi.parse("plain \u001b[1;32mgreen bold\u001b[0m back")
        assertEquals(
            listOf(
                Segment("plain ", TextStyle()),
                Segment("green bold", TextStyle(fg = Ansi.xterm(2), bold = true)),
                Segment(" back", TextStyle()),
            ),
            parsed,
        )
    }

    @Test
    fun `256 colours and true colour`() {
        val parsed = Ansi.parse("\u001b[38;5;214mA\u001b[48;2;10;20;30mB")
        assertEquals(Ansi.xterm(214), parsed[0].style.fg)
        assertEquals(0xFF0A141EL, parsed[1].style.bg)
        assertEquals(Ansi.xterm(214), parsed[1].style.fg)
    }

    @Test
    fun `the cube and the greys of xterm`() {
        assertEquals(0xFF000000L, Ansi.xterm(16))
        assertEquals(0xFFFFFFFFL, Ansi.xterm(231))
        assertEquals(0xFF5FAFD7L, Ansi.xterm(74))
        assertEquals(0xFF080808L, Ansi.xterm(232))
    }

    @Test
    fun `other escapes are dropped, lines stay`() {
        val parsed = Ansi.parse("a\u001b[2Kb\nc\u001b(B")
        assertEquals(listOf(Segment("ab\nc", TextStyle())), parsed)
    }

    @Test
    fun `a hyperlink keeps its text and loses the escape`() {
        val parsed = Ansi.parse("see \u001b]8;id=1;https://x.cz/a\u001b\\docs\u001b]8;;\u001b\\ and \u001b]8;;https://y.cz\u0007more\u001b]8;;\u0007.")
        assertEquals(listOf(Segment("see docs and more.", TextStyle())), parsed)
    }

    @Test
    fun `the play glyph without a font becomes a triangle`() {
        assertEquals(listOf(Segment("▶▶ accept edits", TextStyle())), Ansi.parse("⏵⏵ accept edits"))
    }
}

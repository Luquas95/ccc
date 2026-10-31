package io.github.luquas95.ccc.data

import org.junit.Assert.assertEquals
import org.junit.Test

class MarkdownTest {
    private fun spans(text: String) = Markdown.inline(text)

    @Test
    fun `bold italic and code lose their marks`() {
        assertEquals(
            listOf(MdSpan("a "), MdSpan("tučné", bold = true), MdSpan(" b "), MdSpan("kód", code = true), MdSpan(" c ")
                , MdSpan("šikmé", italic = true)),
            spans("a **tučné** b `kód` c *šikmé*"),
        )
    }

    @Test
    fun `marks nest`() {
        assertEquals(
            listOf(MdSpan("a ", bold = true), MdSpan("b", bold = true, italic = true)),
            spans("**a *b***"),
        )
    }

    @Test
    fun `code keeps what is inside as written`() {
        assertEquals(listOf(MdSpan("**x** _y_", code = true)), spans("`**x** _y_`"))
    }

    @Test
    fun `snake_case, a lone star and unclosed marks stay as written`() {
        assertEquals(listOf(MdSpan("my_var_name")), spans("my_var_name"))
        assertEquals(listOf(MdSpan("2 * 3 * 4")), spans("2 * 3 * 4"))
        assertEquals(listOf(MdSpan("**open")), spans("**open"))
    }

    @Test
    fun `links and escapes`() {
        assertEquals(
            listOf(MdSpan("see "), MdSpan("docs", link = "https://x.cz/a"), MdSpan(" *not italic*")),
            spans("see [docs](https://x.cz/a) \\*not italic\\*"),
        )
    }

    @Test
    fun `blocks - headings, lists, quote, rule, paragraphs`() {
        val blocks = Markdown.parse("# Title\n\nfirst\nsecond\n\n- one\n  more\n  - nested\n2. two\n\n> quoted\n\n---\nend")
        assertEquals(MdBlock.Heading(1, listOf(MdSpan("Title"))), blocks[0])
        assertEquals(MdBlock.Paragraph(listOf(MdSpan("first\nsecond"))), blocks[1])
        assertEquals(MdBlock.Item(0, "•", listOf(MdSpan("one\nmore"))), blocks[2])
        assertEquals(MdBlock.Item(1, "•", listOf(MdSpan("nested"))), blocks[3])
        assertEquals(MdBlock.Item(0, "2.", listOf(MdSpan("two"))), blocks[4])
        assertEquals(MdBlock.Quote(listOf(MdSpan("quoted"))), blocks[5])
        assertEquals(MdBlock.Rule, blocks[6])
        assertEquals(MdBlock.Paragraph(listOf(MdSpan("end"))), blocks[7])
    }

    @Test
    fun `fenced code is one block, marks inside stay`() {
        val blocks = Markdown.parse("before\n```kotlin\nval a = **b**\n\n# not a heading\n```\nafter")
        assertEquals(
            listOf(
                MdBlock.Paragraph(listOf(MdSpan("before"))),
                MdBlock.Code("kotlin", "val a = **b**\n\n# not a heading"),
                MdBlock.Paragraph(listOf(MdSpan("after"))),
            ),
            blocks,
        )
    }

    @Test
    fun `an unclosed fence takes the rest and a table stays together`() {
        assertEquals(listOf(MdBlock.Code("", "a\nb")), Markdown.parse("```\na\nb"))
        assertEquals(listOf(MdBlock.Table(listOf("| a | b |", "|---|---|", "| 1 | 2 |"))),
            Markdown.parse("| a | b |\n|---|---|\n| 1 | 2 |"))
    }
}

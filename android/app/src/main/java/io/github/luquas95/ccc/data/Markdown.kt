package io.github.luquas95.ccc.data

/** A run of inline text with its look; [link] is the address of a `[text](url)`. */
data class MdSpan(
    val text: String,
    val bold: Boolean = false,
    val italic: Boolean = false,
    val strike: Boolean = false,
    val code: Boolean = false,
    val link: String? = null,
)

sealed interface MdBlock {
    data class Paragraph(val spans: List<MdSpan>) : MdBlock
    data class Heading(val level: Int, val spans: List<MdSpan>) : MdBlock
    /** A bullet or numbered item; [marker] is "•" or "1." and [depth] the nesting (0, 1, …). */
    data class Item(val depth: Int, val marker: String, val spans: List<MdSpan>) : MdBlock
    data class Quote(val spans: List<MdSpan>) : MdBlock
    data class Code(val language: String, val text: String) : MdBlock
    /** A table, kept as its own lines (shown in monospace, scrolling sideways). */
    data class Table(val lines: List<String>) : MdBlock
    data object Rule : MdBlock
}

/**
 * The part of Markdown that Claude's answers use: headings, paragraphs, bullet and numbered lists,
 * quotes, fenced code, tables, rules, and inline **bold**, *italic*, ~~strike~~, `code` and links.
 * Line breaks inside a paragraph stay line breaks (the answer is a chat, not a document).
 * Anything it doesn't know stays as plain text, so nothing is ever lost.
 */
object Markdown {
    private val HEADING = Regex("^(#{1,6})\\s+(.*?)\\s*#*\\s*$")
    private val RULE = Regex("^\\s{0,3}([-*_])(\\s*\\1){2,}\\s*$")
    private val ITEM = Regex("^(\\s*)([-*+]|\\d{1,9}[.)])\\s+(.*)$")
    private val FENCE = Regex("^\\s*(```+|~~~+)\\s*([\\w+#.-]*).*$")
    private const val ESCAPABLE = "\\`*_{}[]()#+-.!|~>"

    fun parse(text: String): List<MdBlock> {
        val blocks = mutableListOf<MdBlock>()
        val lines = text.replace("\r\n", "\n").split("\n")
        var paragraph = mutableListOf<String>()
        var quote = mutableListOf<String>()
        var table = mutableListOf<String>()
        // The item (or paragraph) lines may still continue on the next indented line.
        var item: Triple<Int, String, MutableList<String>>? = null

        fun flush() {
            if (paragraph.isNotEmpty()) blocks += MdBlock.Paragraph(inline(paragraph.joinToString("\n")))
            paragraph = mutableListOf()
            item?.let { (depth, marker, parts) -> blocks += MdBlock.Item(depth, marker, inline(parts.joinToString("\n"))) }
            item = null
            if (quote.isNotEmpty()) blocks += MdBlock.Quote(inline(quote.joinToString("\n")))
            quote = mutableListOf()
            if (table.isNotEmpty()) blocks += MdBlock.Table(table)
            table = mutableListOf()
        }

        var i = 0
        while (i < lines.size) {
            val line = lines[i]
            val fence = FENCE.matchEntire(line)
            if (fence != null) {
                flush()
                val mark = fence.groupValues[1]
                val body = mutableListOf<String>()
                i++
                while (i < lines.size && !(lines[i].trim().startsWith(mark.take(3)) && lines[i].trim().all { it == mark[0] })) {
                    body += lines[i]; i++
                }
                blocks += MdBlock.Code(fence.groupValues[2], body.joinToString("\n"))
                i++
                continue
            }
            val heading = HEADING.matchEntire(line)
            val trimmed = line.trim()
            when {
                trimmed.isEmpty() -> flush()
                heading != null -> { flush(); blocks += MdBlock.Heading(heading.groupValues[1].length, inline(heading.groupValues[2])) }
                RULE.matches(line) -> { flush(); blocks += MdBlock.Rule }
                trimmed.startsWith("|") -> { if (table.isEmpty()) flush(); table += line }
                trimmed.startsWith(">") -> { if (quote.isEmpty()) flush(); quote += trimmed.removePrefix(">").removePrefix(" ") }
                ITEM.matches(line) -> {
                    flush()
                    val (indent, marker, body) = ITEM.matchEntire(line)!!.destructured
                    val shown = if (marker[0].isDigit()) marker else "•"
                    item = Triple(indent.length / 2, shown, mutableListOf(body))
                }
                item != null && line.startsWith(" ") -> item!!.third += trimmed
                else -> { if (item != null || quote.isNotEmpty() || table.isNotEmpty()) flush(); paragraph += line }
            }
            i++
        }
        flush()
        return blocks
    }

    /** The inline marks of one piece of text; unclosed marks stay as written. */
    fun inline(text: String, base: MdSpan = MdSpan("")): List<MdSpan> {
        val out = mutableListOf<MdSpan>()
        val buf = StringBuilder()
        fun flush() {
            if (buf.isNotEmpty()) out += base.copy(text = buf.toString())
            buf.clear()
        }
        fun wordBefore(i: Int) = i > 0 && text[i - 1].isLetterOrDigit()
        fun wordAfter(i: Int) = i < text.length && text[i].isLetterOrDigit()

        var i = 0
        while (i < text.length) {
            val c = text[i]
            if (c == '\\' && i + 1 < text.length && text[i + 1] in ESCAPABLE) {
                buf.append(text[i + 1]); i += 2; continue
            }
            if (c == '`') {
                var ticks = 0
                while (i + ticks < text.length && text[i + ticks] == '`') ticks++
                val close = text.indexOf("`".repeat(ticks), i + ticks)
                if (close > i + ticks - 1 && close >= i + ticks) {
                    flush()
                    out += base.copy(text = text.substring(i + ticks, close).trim(), code = true)
                    i = close + ticks
                    continue
                }
                buf.append("`".repeat(ticks)); i += ticks; continue
            }
            val pair = if (i + 1 < text.length) text.substring(i, i + 2) else ""
            if ((pair == "**" || pair == "__" || pair == "~~") && i + 2 < text.length && !text[i + 2].isWhitespace() &&
                !(pair == "__" && wordBefore(i))
            ) {
                var close = text.indexOf(pair, i + 2)
                // "***" closes with its last two stars (the first one belongs to an inner *italic*).
                while (close > 0 && text.getOrNull(close + 2) == pair[0]) close++
                if (close > i + 2 && !text[close - 1].isWhitespace() && !(pair == "__" && wordAfter(close + 2))) {
                    flush()
                    val styled = if (pair == "~~") base.copy(strike = true) else base.copy(bold = true)
                    out += inline(text.substring(i + 2, close), styled)
                    i = close + 2
                    continue
                }
            }
            if ((c == '*' || c == '_') && i + 1 < text.length && !text[i + 1].isWhitespace() && text[i + 1] != c &&
                !(c == '_' && wordBefore(i))
            ) {
                var close = i + 1
                var found = -1
                while (close < text.length) {
                    close = text.indexOf(c, close)
                    if (close < 0) break
                    val next = text.getOrNull(close + 1)
                    if (!text[close - 1].isWhitespace() && next != c && !(c == '_' && wordAfter(close + 1))) { found = close; break }
                    close++
                }
                if (found > i + 1) {
                    flush()
                    out += inline(text.substring(i + 1, found), base.copy(italic = true))
                    i = found + 1
                    continue
                }
            }
            if (c == '[') {
                val mid = text.indexOf("](", i + 1)
                val end = if (mid > 0) text.indexOf(')', mid + 2) else -1
                if (mid > i && end > mid && !text.substring(i + 1, mid).contains('\n')) {
                    val url = text.substring(mid + 2, end).trim().substringBefore(' ')
                    if (url.isNotEmpty()) {
                        flush()
                        out += inline(text.substring(i + 1, mid), base.copy(link = url))
                        i = end + 1
                        continue
                    }
                }
            }
            buf.append(c); i++
        }
        flush()
        return out
    }
}

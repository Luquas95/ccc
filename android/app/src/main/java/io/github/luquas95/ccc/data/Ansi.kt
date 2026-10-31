package io.github.luquas95.ccc.data

/** How a run of terminal text looks: colours as ARGB (null: the terminal's own). */
data class TextStyle(
    val fg: Long? = null,
    val bg: Long? = null,
    val bold: Boolean = false,
    val dim: Boolean = false,
    val italic: Boolean = false,
    val underline: Boolean = false,
    val reverse: Boolean = false,
)

data class Segment(val text: String, val style: TextStyle)

/**
 * The screen of a terminal (tmux capture-pane -e) as styled segments: the
 * SGR escapes (colours, bold …) become styles, any other escape is
 * dropped. Lines stay separated by "\n".
 */
object Ansi {
    // CSI (ESC [ … letter), a charset choice (ESC ( B and the like), any other two-character escape.
    // An OSC (ESC ] … BEL or ESC \\), e.g. the hyperlink "ESC ] 8 ; id=… ; url ST": dropped whole, the linked text stays.
    private val ESCAPE = Regex("\u001b\\][^\u0007\u001b]*(?:\u0007|\u001b\\\\)?|\u001b\\[([0-9;:?]*)([A-Za-z])|\u001b[()*+][0-9A-Za-z]|\u001b[^\\[]")

    fun parse(raw: String): List<Segment> {
        // ⏵ (U+23F5) has no glyph in Android's fonts: it showed as an empty box. ▶ is everywhere.
        val text = raw.replace('⏵', '▶').replace('⏴', '◀')
        val segments = mutableListOf<Segment>()
        var style = TextStyle()
        var last = 0
        for (match in ESCAPE.findAll(text)) {
            if (match.range.first > last) segments += Segment(text.substring(last, match.range.first), style)
            last = match.range.last + 1
            if (match.groupValues[2] == "m") style = apply(style, match.groupValues[1])
        }
        if (last < text.length) segments += Segment(text.substring(last), style)
        return merge(segments)
    }

    private fun merge(segments: List<Segment>): List<Segment> {
        val merged = mutableListOf<Segment>()
        for (segment in segments) {
            val previous = merged.lastOrNull()
            if (previous != null && previous.style == segment.style) {
                merged[merged.lastIndex] = previous.copy(text = previous.text + segment.text)
            } else if (segment.text.isNotEmpty()) {
                merged += segment
            }
        }
        return merged
    }

    private fun apply(start: TextStyle, params: String): TextStyle {
        val codes = params.split(';', ':').map { it.toIntOrNull() ?: 0 }.ifEmpty { listOf(0) }
        var style = start
        var i = 0
        while (i < codes.size) {
            when (val code = codes[i]) {
                0 -> style = TextStyle()
                1 -> style = style.copy(bold = true)
                2 -> style = style.copy(dim = true)
                3 -> style = style.copy(italic = true)
                4 -> style = style.copy(underline = true)
                7 -> style = style.copy(reverse = true)
                22 -> style = style.copy(bold = false, dim = false)
                23 -> style = style.copy(italic = false)
                24 -> style = style.copy(underline = false)
                27 -> style = style.copy(reverse = false)
                in 30..37 -> style = style.copy(fg = xterm(code - 30))
                in 90..97 -> style = style.copy(fg = xterm(code - 90 + 8))
                39 -> style = style.copy(fg = null)
                in 40..47 -> style = style.copy(bg = xterm(code - 40))
                in 100..107 -> style = style.copy(bg = xterm(code - 100 + 8))
                49 -> style = style.copy(bg = null)
                38, 48 -> {
                    val (color, used) = extended(codes, i + 1)
                    style = if (code == 38) style.copy(fg = color) else style.copy(bg = color)
                    i += used
                }
            }
            i++
        }
        return style
    }

    /** 5;n (256 colours) or 2;r;g;b after 38 / 48: the colour and how many codes it took. */
    private fun extended(codes: List<Int>, at: Int): Pair<Long?, Int> = when (codes.getOrNull(at)) {
        5 -> xterm(codes.getOrElse(at + 1) { 0 }) to 2
        2 -> rgb(codes.getOrElse(at + 1) { 0 }, codes.getOrElse(at + 2) { 0 }, codes.getOrElse(at + 3) { 0 }) to 4
        else -> null to 0
    }

    private val BASIC = longArrayOf(
        0x000000, 0xCD3131, 0x0DBC79, 0xE5E510, 0x2472C8, 0xBC3FBC, 0x11A8CD, 0xE5E5E5,
        0x666666, 0xF14C4C, 0x23D18B, 0xF5F543, 0x3B8EEA, 0xD670D6, 0x29B8DB, 0xFFFFFF,
    )

    private fun rgb(r: Int, g: Int, b: Int): Long =
        0xFF000000 or ((r.coerceIn(0, 255).toLong()) shl 16) or ((g.coerceIn(0, 255).toLong()) shl 8) or b.coerceIn(0, 255).toLong()

    /** An xterm 256-colour index as ARGB. */
    fun xterm(index: Int): Long {
        val n = index.coerceIn(0, 255)
        if (n < 16) return 0xFF000000 or BASIC[n]
        if (n >= 232) {
            val level = 8 + (n - 232) * 10
            return rgb(level, level, level)
        }
        val cube = n - 16
        fun level(v: Int) = if (v == 0) 0 else 55 + v * 40
        return rgb(level(cube / 36), level(cube / 6 % 6), level(cube % 6))
    }
}

package io.github.luquas95.ccc.data

import java.text.Normalizer

/**
 * The filter over the list, as ccc's (src/ccc/list_filter.py): words
 * matched against a conversation's name and folder — case and diacritics
 * don't matter — and state markers at the start: ! working, ? waiting for
 * approval, x stopped on an error, * a new reply. Several markers mean any
 * of those states, several words must all match.
 */
data class ListFilter(val states: Set<Char> = emptySet(), val words: List<String> = emptyList()) {
    val active: Boolean get() = states.isNotEmpty() || words.isNotEmpty()

    fun matches(conversation: Conversation): Boolean {
        if (states.isNotEmpty() && states.intersect(statesOf(conversation)).isEmpty()) return false
        val haystack = fold("${conversation.name} ${conversation.path}")
        return words.all { it in haystack }
    }

    companion object {
        const val WORKING = '!'
        const val APPROVAL = '?'
        const val ERROR = 'x'
        const val UNSEEN = '*'
        private val MARKERS = setOf(WORKING, APPROVAL, ERROR, UNSEEN)

        fun parse(text: String): ListFilter {
            val tokens = text.split(Regex("\\s+")).filter { it.isNotEmpty() }.toMutableList()
            val states = mutableSetOf<Char>()
            while (tokens.isNotEmpty() && tokens.first().lowercase().all { it in MARKERS }) {
                states += tokens.removeAt(0).lowercase().toSet()
            }
            return ListFilter(states, tokens.map(::fold))
        }

        /** Lower case without diacritics: "Příliš" -> "prilis". */
        fun fold(text: String): String =
            Normalizer.normalize(text.lowercase(), Normalizer.Form.NFKD).replace(Regex("\\p{M}+"), "")

        private fun statesOf(c: Conversation): Set<Char> = buildSet {
            if (c.state == ConversationStatus.RUNNING) add(WORKING)
            if (c.needsApproval) add(APPROVAL)
            if (c.state == ConversationStatus.BLOCKED_ERROR) add(ERROR)
            if (c.unseen) add(UNSEEN)
        }
    }
}

/** The @-mention being typed at the end of [text]: (where its @ is, what follows), or null — as ccc's file_mentions.mention_at. */
fun mentionAt(text: String): Pair<Int, String>? {
    val start = text.lastIndexOf('@')
    if (start < 0) return null
    val query = text.substring(start + 1)
    if (query.any { it.isWhitespace() }) return null
    if (start > 0 && !text[start - 1].isWhitespace()) return null
    return start to query
}

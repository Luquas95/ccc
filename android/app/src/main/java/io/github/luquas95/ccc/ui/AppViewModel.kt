package io.github.luquas95.ccc.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.ApiException
import io.github.luquas95.ccc.data.CccApi
import io.github.luquas95.ccc.data.Conversation
import io.github.luquas95.ccc.data.ConversationDetail
import io.github.luquas95.ccc.data.Export
import io.github.luquas95.ccc.data.LaunchOptions
import io.github.luquas95.ccc.data.LaunchPresets
import io.github.luquas95.ccc.data.Message
import io.github.luquas95.ccc.data.NewConversation
import io.github.luquas95.ccc.data.Permission
import io.github.luquas95.ccc.data.PromptPreset
import io.github.luquas95.ccc.data.SearchHit
import io.github.luquas95.ccc.data.Session
import io.github.luquas95.ccc.data.ServerEvent
import io.github.luquas95.ccc.data.Settings
import io.github.luquas95.ccc.data.Status
import io.github.luquas95.ccc.data.Usage
import io.github.luquas95.ccc.data.Waiting
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** The app's screens; the last one of the stack is shown. */
sealed interface Screen {
    data object Setup : Screen
    data object Conversations : Screen
    data class Conversation(val id: Int) : Screen
    data object Approvals : Screen
    data object NewConversation : Screen
    data object Search : Screen
}

data class HomeState(
    val status: Status? = null,
    val conversations: List<Conversation> = emptyList(),
    val permissions: List<Permission> = emptyList(),
    val usage: Usage? = null,
    val archived: List<Conversation> = emptyList(),
    /** The Archive tab instead of the conversations. */
    val showArchive: Boolean = false,
    /** The list filter as typed (see ListFilter). */
    val filter: String = "",
    /** Conversations that need you, most urgent first. */
    val waiting: List<Waiting> = emptyList(),
    val ownGroups: List<String> = emptyList(),
    val promptPresets: List<PromptPreset> = emptyList(),
    val loaded: Boolean = false,
    val refreshing: Boolean = false,
    /** The events stream is open: what the app shows is current. */
    val live: Boolean = false,
)

data class ConversationState(
    val id: Int,
    val detail: ConversationDetail? = null,
    /** Oldest first. */
    val messages: List<Message> = emptyList(),
    val total: Int = 0,
    val loadingOlder: Boolean = false,
    val sending: Boolean = false,
    /** Files for the @-mention being typed. */
    val mentions: List<String> = emptyList(),
) {
    val hasOlder: Boolean get() = (messages.firstOrNull()?.index ?: 0) > 0
}

data class NewConversationState(
    val options: LaunchOptions? = null,
    val projects: List<String> = emptyList(),
    val presets: LaunchPresets? = null,
    /** Sessions of [sessionsFor] (to resume one). */
    val sessions: List<Session> = emptyList(),
    val sessionsFor: String = "",
    val creating: Boolean = false,
)

data class SearchState(val query: String = "", val hits: List<SearchHit> = emptyList(), val searching: Boolean = false)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val settings = Settings(application)
    private var api: CccApi? = settings.takeIf { it.configured }?.let { api(it.server, it.token) }

    private val _screens = MutableStateFlow(listOf(if (api != null) Screen.Conversations else Screen.Setup))
    val screens: StateFlow<List<Screen>> = _screens.asStateFlow()

    private val _home = MutableStateFlow(HomeState())
    val home: StateFlow<HomeState> = _home.asStateFlow()

    private val _conversation = MutableStateFlow<ConversationState?>(null)
    val conversation: StateFlow<ConversationState?> = _conversation.asStateFlow()

    private val _newConversation = MutableStateFlow(NewConversationState())
    val newConversation: StateFlow<NewConversationState> = _newConversation.asStateFlow()

    private val _search = MutableStateFlow(SearchState())
    val search: StateFlow<SearchState> = _search.asStateFlow()

    /** A conversation to share (Markdown); handed to the share sheet once, then [shared]. */
    private val _share = MutableStateFlow<Export?>(null)
    val share: StateFlow<Export?> = _share.asStateFlow()

    /** A message for a snackbar; shown once, then [messageShown]. */
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    val server: String get() = settings.server

    private var events: Job? = null
    private var foreground = false
    private var searching: Job? = null
    private var mentioning: Job? = null

    // --- navigation --------------------------------------------------------------

    fun open(screen: Screen) {
        _screens.update { it + screen }
        when (screen) {
            is Screen.Conversation -> openConversation(screen.id)
            Screen.NewConversation -> loadLaunchOptions()
            else -> Unit
        }
    }

    fun back() {
        _screens.update { if (it.size > 1) it.dropLast(1) else it }
        val current = _screens.value.last()
        _conversation.update { state -> state?.takeIf { current is Screen.Conversation && current.id == it.id } }
        if (current is Screen.Conversation && _conversation.value == null) openConversation(current.id)
    }

    fun messageShown() {
        _message.value = null
    }

    // --- signing in -----------------------------------------------------------------

    /** Try the server and token; keep them when ccc answers. */
    fun connect(server: String, token: String, onDone: (Boolean) -> Unit) {
        val candidate = runCatching { api(server, token) }.getOrElse {
            _message.value = text(R.string.error_server_address)
            onDone(false)
            return
        }
        viewModelScope.launch {
            try {
                candidate.status()
                settings.save(server, token)
                api = candidate
                _home.value = HomeState()
                _screens.value = listOf(Screen.Conversations)
                restartEvents()
                refresh()
                onDone(true)
            } catch (e: CancellationException) {
                throw e
            } catch (e: IOException) {
                _message.value = describe(e)
                onDone(false)
            }
        }
    }

    fun signOut() {
        settings.clear()
        api = null
        events?.cancel()
        _home.value = HomeState()
        _conversation.value = null
        _screens.value = listOf(Screen.Setup)
    }

    // --- the app in front / behind ----------------------------------------------------

    /** Keep the events stream open only while the app is seen. */
    fun setForeground(value: Boolean) {
        foreground = value
        if (value) restartEvents() else events?.cancel()
    }

    private fun restartEvents() {
        events?.cancel()
        val client = api ?: return
        if (!foreground) return
        events = viewModelScope.launch {
            var wait = 1_000L
            while (true) {
                try {
                    client.events().collect { event ->
                        when (event) {
                            ServerEvent.Connected -> {
                                wait = 1_000L
                                _home.update { it.copy(live = true) }
                                refresh()
                                _conversation.value?.let { reloadConversation(it.id) }
                            }
                            is ServerEvent.Changed -> onChange(event.change.conversations, event.change.removed)
                        }
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: IOException) {
                    if (e is ApiException && e.code == 401) {
                        _home.update { it.copy(live = false) }
                        _message.value = describe(e)
                        return@launch
                    }
                }
                // Closed or broken: connect again, waiting longer each time.
                _home.update { it.copy(live = false) }
                delay(wait)
                wait = (wait * 2).coerceAtMost(30_000L)
            }
        }
    }

    private suspend fun onChange(changed: List<Int>, removed: List<Int>) {
        refresh()
        val open = _conversation.value?.id ?: return
        if (open in removed) {
            _screens.update { stack -> stack.filterNot { it is Screen.Conversation && it.id == open } }
            _conversation.value = null
        } else if (open in changed) {
            reloadConversation(open)
        }
    }

    // --- the list ----------------------------------------------------------------------

    fun pullToRefresh() {
        viewModelScope.launch {
            _home.update { it.copy(refreshing = true) }
            refresh()
            _home.update { it.copy(refreshing = false) }
        }
    }

    private suspend fun refresh() {
        val client = api ?: return
        guard {
            val status = client.status()
            val conversations = client.conversations()
            val permissions = client.permissions()
            val archived = client.conversations(archived = true)
            val waiting = client.waiting()
            val groups = client.groups()
            val presets = client.promptPresets()
            _home.update {
                it.copy(
                    status = status, conversations = conversations, permissions = permissions, archived = archived,
                    waiting = waiting, ownGroups = groups.own, promptPresets = presets, loaded = true,
                )
            }
            // The usage comes from Anthropic through ccc: slower, and not worth an error.
            val usage = runCatching { client.usage() }.getOrNull()
            _home.update { it.copy(usage = usage) }
        }
    }

    // --- one conversation ----------------------------------------------------------------

    private fun openConversation(id: Int) {
        _conversation.value = ConversationState(id)
        viewModelScope.launch {
            reloadConversation(id)
            guard { api?.markSeen(id) }
        }
    }

    /** The detail, and the messages after the last one shown (all of the newest at first). */
    private suspend fun reloadConversation(id: Int) {
        val client = api ?: return
        guard {
            val detail = client.conversation(id)
            val shown = _conversation.value?.takeIf { it.id == id } ?: return@guard
            val last = shown.messages.lastOrNull()?.index
            val fresh = client.messages(id, after = last)
            _conversation.update { state ->
                if (state == null || state.id != id) return@update state
                val messages = if (last == null) fresh.messages else state.messages + fresh.messages
                state.copy(detail = detail, messages = messages, total = fresh.total)
            }
        }
    }

    fun loadOlder() {
        val state = _conversation.value ?: return
        val first = state.messages.firstOrNull()?.index ?: return
        if (state.loadingOlder || first == 0) return
        val client = api ?: return
        _conversation.update { it?.copy(loadingOlder = true) }
        viewModelScope.launch {
            guard {
                val older = client.messages(state.id, before = first)
                _conversation.update {
                    if (it == null || it.id != state.id) it else it.copy(messages = older.messages + it.messages)
                }
            }
            _conversation.update { it?.copy(loadingOlder = false) }
        }
    }

    fun send(text: String, onSent: () -> Unit) {
        val state = _conversation.value ?: return
        val client = api ?: return
        if (text.isBlank() || state.sending) return
        _conversation.update { it?.copy(sending = true) }
        viewModelScope.launch {
            val sent = guard {
                client.send(state.id, text)
                reloadConversation(state.id)
            }
            _conversation.update { it?.copy(sending = false) }
            if (sent) onSent()
        }
    }

    fun retry() {
        val state = _conversation.value ?: return
        val client = api ?: return
        viewModelScope.launch {
            guard {
                client.retry(state.id)
                reloadConversation(state.id)
            }
        }
    }

    // --- approvals -------------------------------------------------------------------------

    fun decide(permission: Permission, decision: String) {
        val client = api ?: return
        viewModelScope.launch {
            guard {
                client.decide(permission.id, decision)
                refresh()
                _conversation.value?.takeIf { it.id == permission.conversationId }?.let { reloadConversation(it.id) }
            }
        }
    }

    // --- a new conversation -------------------------------------------------------------------

    private fun loadLaunchOptions() {
        val client = api ?: return
        viewModelScope.launch {
            guard {
                val options = client.launchOptions()
                val projects = client.projects()
                val presets = client.launchPresets()
                _newConversation.update { it.copy(options = options, projects = projects, presets = presets) }
            }
        }
    }

    fun create(request: NewConversation) {
        val client = api ?: return
        if (_newConversation.value.creating) return
        _newConversation.update { it.copy(creating = true) }
        viewModelScope.launch {
            guard {
                val created = client.create(request)
                refresh()
                _screens.update { stack -> stack.dropLast(1) }
                open(Screen.Conversation(created.id))
            }
            _newConversation.update { it.copy(creating = false) }
        }
    }

    // --- the list: archive, filter, groups, what needs you -------------------------------------

    fun showArchive(value: Boolean) {
        _home.update { it.copy(showArchive = value) }
    }

    fun setFilter(text: String) {
        _home.update { it.copy(filter = text) }
    }

    /** Open the conversation that needs you most (Alt+N in ccc). */
    fun openNextWaiting() {
        val next = _home.value.waiting.firstOrNull { w -> _conversation.value?.id != w.conversationId } ?: return
        open(Screen.Conversation(next.conversationId))
    }

    fun renameGroup(old: String, new: String) = action {
        it.renameGroup(old, new)
        refresh()
    }

    fun deleteGroup(name: String) = action {
        it.deleteGroup(name)
        refresh()
    }

    // --- one conversation: archive, delete, group, export, presets, @-mentions -------------------

    fun archive(id: Int, archived: Boolean) = action {
        it.archive(id, archived)
        refresh()
        if (_conversation.value?.id == id) reloadConversation(id)
    }

    fun delete(id: Int) = action {
        it.delete(id)
        _screens.update { stack -> stack.filterNot { s -> s is Screen.Conversation && s.id == id } }
        if (_conversation.value?.id == id) _conversation.value = null
        refresh()
    }

    fun setGroup(id: Int, name: String?) = action {
        it.setGroup(id, name)
        refresh()
        if (_conversation.value?.id == id) reloadConversation(id)
    }

    fun export(id: Int) = action {
        _share.value = it.export(id)
    }

    fun shared() {
        _share.value = null
    }

    /** A preset prompt: sent at once, or [insert]ed into the message box. */
    fun usePreset(preset: PromptPreset, insert: (String) -> Unit) {
        if (preset.sendNow) send(preset.text) {} else insert(preset.text)
    }

    /** Offer files for the @-mention being typed (null: none being typed). */
    fun mention(query: String?) {
        mentioning?.cancel()
        val state = _conversation.value ?: return
        val client = api ?: return
        if (query == null) {
            _conversation.update { it?.copy(mentions = emptyList()) }
            return
        }
        mentioning = viewModelScope.launch {
            delay(200)
            val files = runCatching { client.files(state.id, query) }.getOrDefault(emptyList())
            _conversation.update { if (it?.id == state.id) it.copy(mentions = files) else it }
        }
    }

    // --- search ------------------------------------------------------------------------------------

    fun search(text: String) {
        searching?.cancel()
        _search.update { it.copy(query = text) }
        val client = api ?: return
        if (text.isBlank()) {
            _search.update { it.copy(hits = emptyList(), searching = false) }
            return
        }
        searching = viewModelScope.launch {
            delay(300)
            _search.update { it.copy(searching = true) }
            guard {
                val hits = client.search(text)
                _search.update { if (it.query == text) it.copy(hits = hits) else it }
            }
            _search.update { it.copy(searching = false) }
        }
    }

    // --- New conversation: presets, sessions to resume -----------------------------------------------

    fun loadSessions(path: String) {
        val client = api ?: return
        if (path.isBlank() || _newConversation.value.sessionsFor == path) return
        viewModelScope.launch {
            val sessions = runCatching { client.sessions(path) }.getOrDefault(emptyList())
            _newConversation.update { it.copy(sessions = sessions, sessionsFor = path) }
        }
    }

    // --- helpers -------------------------------------------------------------------------------

    /** Run an API call in the background, errors to the snackbar. */
    private fun action(block: suspend (CccApi) -> Unit) {
        val client = api ?: return
        viewModelScope.launch { guard { block(client) } }
    }


    /** Run [block]; a network or API error becomes the snackbar message. True when it went through. */
    private suspend fun guard(block: suspend () -> Unit): Boolean = try {
        block()
        true
    } catch (e: CancellationException) {
        throw e
    } catch (e: IOException) {
        _message.value = describe(e)
        false
    }

    private fun describe(e: IOException): String = when {
        e is ApiException && e.code == 401 -> text(R.string.error_token)
        e is ApiException -> e.message ?: text(R.string.error_network)
        else -> text(R.string.error_network)
    }

    private fun text(id: Int): String = getApplication<Application>().getString(id)

    private fun api(server: String, token: String) = CccApi(server, token)
}

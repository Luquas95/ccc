package io.github.luquas95.ccc

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import io.github.luquas95.ccc.notify.ApkInstaller
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.luquas95.ccc.ui.AgentsActions
import io.github.luquas95.ccc.ui.AgentsScreen
import io.github.luquas95.ccc.ui.AnalyticsScreen
import io.github.luquas95.ccc.ui.AppViewModel
import io.github.luquas95.ccc.ui.CccSettingsScreen
import io.github.luquas95.ccc.ui.RoutinesActions
import io.github.luquas95.ccc.ui.RoutinesScreen
import io.github.luquas95.ccc.notify.WatchService
import io.github.luquas95.ccc.ui.SettingsActions
import io.github.luquas95.ccc.ui.TerminalActions
import io.github.luquas95.ccc.ui.TerminalScreen
import io.github.luquas95.ccc.ui.ApprovalsScreen
import io.github.luquas95.ccc.ui.ConversationActions
import io.github.luquas95.ccc.ui.ConversationScreen
import io.github.luquas95.ccc.ui.ConversationsActions
import io.github.luquas95.ccc.ui.ConversationsScreen
import io.github.luquas95.ccc.ui.DiffScreen
import io.github.luquas95.ccc.ui.RunsScreen
import io.github.luquas95.ccc.ui.TasksActions
import io.github.luquas95.ccc.ui.TasksScreen
import io.github.luquas95.ccc.ui.NewConversationScreen
import io.github.luquas95.ccc.ui.Screen
import io.github.luquas95.ccc.data.Language
import io.github.luquas95.ccc.ui.SearchScreen
import io.github.luquas95.ccc.ui.SetupScreen
import io.github.luquas95.ccc.ui.theme.CccTheme

class MainActivity : ComponentActivity() {
    private val model: AppViewModel by viewModels()

    override fun attachBaseContext(newBase: android.content.Context) = super.attachBaseContext(Language.wrap(newBase))

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.BLACK),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.BLACK),
        )
        // The events stream only while the app is on screen.
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) = model.setForeground(true)
            override fun onStop(owner: LifecycleOwner) = model.setForeground(false)
        })
        setContent { CccTheme { App(model) } }
        openFrom(intent)
    }

    // A notification tapped: its conversation.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        openFrom(intent)
    }

    private fun openFrom(intent: Intent?) {
        val id = intent?.getIntExtra(WatchService.EXTRA_CONVERSATION, -1) ?: -1
        if (id >= 0) {
            intent?.removeExtra(WatchService.EXTRA_CONVERSATION)
            model.openFromNotification(id)
        }
    }
}

@Composable
private fun App(model: AppViewModel) {
    val screens by model.screens.collectAsStateWithLifecycle()
    val home by model.home.collectAsStateWithLifecycle()
    val devices by model.devices.collectAsStateWithLifecycle()
    val deviceHistory by model.deviceHistory.collectAsStateWithLifecycle()
    val invite by model.invite.collectAsStateWithLifecycle()
    val conversation by model.conversation.collectAsStateWithLifecycle()
    val newConversation by model.newConversation.collectAsStateWithLifecycle()
    val message by model.message.collectAsStateWithLifecycle()
    val search by model.search.collectAsStateWithLifecycle()
    val share by model.share.collectAsStateWithLifecycle()
    val tasks by model.tasks.collectAsStateWithLifecycle()
    val runs by model.runs.collectAsStateWithLifecycle()
    val diff by model.diff.collectAsStateWithLifecycle()
    val agents by model.more.agents.collectAsStateWithLifecycle()
    val routines by model.more.routines.collectAsStateWithLifecycle()
    val sessions by model.more.sessions.collectAsStateWithLifecycle()
    val analytics by model.more.analytics.collectAsStateWithLifecycle()
    val cccSettings by model.more.settings.collectAsStateWithLifecycle()
    val terminal by model.more.terminal.collectAsStateWithLifecycle()
    val notifications by model.notifications.collectAsStateWithLifecycle()
    val listDetails by model.listDetails.collectAsStateWithLifecycle()
    val appUpdate by model.appUpdate.collectAsStateWithLifecycle()
    val install by model.install.collectAsStateWithLifecycle()
    val newVersion by model.newVersion.collectAsStateWithLifecycle()
    val nameOf = { id: Int -> (home.conversations + home.archived).firstOrNull { it.id == id }?.name.orEmpty() }
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    // An export: to the share sheet (save it, mail it, send it to a chat …).
    LaunchedEffect(share) {
        share?.let { export ->
            model.shared()
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/markdown"
                putExtra(Intent.EXTRA_SUBJECT, export.filename)
                putExtra(Intent.EXTRA_TITLE, export.filename)
                putExtra(Intent.EXTRA_TEXT, export.markdown)
            }
            context.startActivity(Intent.createChooser(send, export.filename))
        }
    }
    // The downloaded app: to the system installer — which first needs the one-time "install unknown apps" allowance.
    LaunchedEffect(install) {
        install?.let { apk ->
            model.installStarted()
            if (!context.packageManager.canRequestPackageInstalls()) {
                snackbar.showSnackbar(context.getString(R.string.app_allow_install))
                context.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")))
                return@let
            }
            ApkInstaller.install(context, apk)
        }
    }
    LaunchedEffect(message) {
        message?.let {
            model.messageShown()
            snackbar.showSnackbar(it)
        }
    }
    BackHandler(enabled = screens.size > 1) { model.back() }

    when (val screen = screens.last()) {
        Screen.Setup -> SetupScreen(
            server = model.server,
            signedIn = screens.size > 1,
            notifications = notifications,
            listDetails = listDetails,
            onListDetail = model::setListDetail,
            snackbar = snackbar,
            onBack = if (screens.size > 1) model::back else null,
            onConnect = model::connect,
            language = model.language,
            onLanguage = { model.setLanguage(it); (context as? android.app.Activity)?.recreate() },
            onNotifications = model::setNotifications,
            onSignOut = model::signOut,
            devices = devices,
            deviceHistory = deviceHistory,
            onDevices = model::loadDevices,
            onSignOutDevice = model::signOutDevice,
            invite = invite,
            currentServer = model.currentServer,
            onScan = model::scanned,
            onPair = model::pair,
            onInviteDismissed = model::inviteDismissed,
        )
        Screen.Conversations -> ConversationsScreen(
            state = home,
            listDetails = listDetails,
            newVersion = newVersion,
            snackbar = snackbar,
            sessions = sessions,
            appUpdate = appUpdate,
            actions = ConversationsActions(
                open = { model.open(Screen.Conversation(it)) },
                openQueue = { model.open(Screen.Tasks(it)) },
                approvals = { model.open(Screen.Approvals) },
                settings = { model.open(Screen.CccSettings) },
                new = { model.open(Screen.NewConversation) },
                refresh = model::pullToRefresh,
                search = { model.open(Screen.Search) },
                tab = model::showTab,
                filter = model::setFilter,
                filterState = model::toggleFilterState,
                updateApp = model::updateApp,
                nextWaiting = model::openNextWaiting,
                renameGroup = model::renameGroup,
                deleteGroup = model::deleteGroup,
                routines = { model.open(Screen.Routines) },
                analytics = { model.open(Screen.Analytics) },
                promptSession = { id, prompt -> model.more.promptSession(id, prompt, context.getString(R.string.prompt_queued)) },
                applyUpdate = model::applyUpdate,
            ),
        )
        is Screen.Conversation -> conversation?.takeIf { it.id == screen.id }?.let {
            ConversationScreen(
                state = it,
                presets = home.promptPresets,
                ownGroups = home.ownGroups,
                snackbar = snackbar,
                actions = ConversationActions(
                    back = model::back,
                    send = model::send,
                    retry = model::retry,
                    loadOlder = model::loadOlder,
                    decide = model::decide,
                    archive = { archived -> model.archive(screen.id, archived) },
                    delete = { model.delete(screen.id) },
                    setGroup = { name -> model.setGroup(screen.id, name) },
                    export = { model.export(screen.id) },
                    usePreset = model::usePreset,
                    mention = model::mention,
                    tasks = { model.open(Screen.Tasks(screen.id)) },
                    runs = { model.open(Screen.Runs(screen.id)) },
                    agents = { model.open(Screen.Agents(screen.id)) },
                    terminal = { model.open(Screen.Terminal(screen.id)) },
                ),
            )
        }
        is Screen.Tasks -> tasks?.takeIf { it.id == screen.id }?.let {
            TasksScreen(
                state = it,
                name = nameOf(screen.id),
                snackbar = snackbar,
                actions = TasksActions(
                    back = model::back,
                    add = model::addTask,
                    edit = model::editTask,
                    remove = model::removeTask,
                    move = model::moveTask,
                    paused = model::setPaused,
                    autoContinue = model::setAutoContinue,
                ),
            )
        }
        is Screen.Runs -> runs?.takeIf { it.id == screen.id }?.let {
            RunsScreen(
                state = it,
                name = nameOf(screen.id),
                snackbar = snackbar,
                onBack = model::back,
                onDiff = { run -> model.open(Screen.Diff(run)) },
                onRevert = model::revert,
            )
        }
        is Screen.Diff -> diff?.takeIf { it.runId == screen.runId }?.let {
            DiffScreen(
                state = it,
                snackbar = snackbar,
                onBack = model::back,
                onComment = model::setComment,
                onSend = model::sendComments,
            )
        }
        is Screen.Agents -> agents?.takeIf { it.id == screen.id }?.let {
            val more = model.more
            AgentsScreen(
                state = it,
                name = nameOf(screen.id),
                others = home.conversations.filter { c -> c.id != screen.id },
                firstTab = screen.tab,
                snackbar = snackbar,
                actions = AgentsActions(
                    back = model::back,
                    review = more::requestReview,
                    stopReview = more::stopReview,
                    applyReview = more::applyReview,
                    goal = more::startGoal,
                    stopGoal = more::stopGoal,
                    workflow = more::startWorkflow,
                    answer = more::answerWorkflow,
                    stopWorkflow = more::stopWorkflow,
                    ask = more::ask,
                    cancelAsk = more::cancelAsk,
                ),
            )
        }
        Screen.Routines -> RoutinesScreen(
            state = routines,
            conversations = home.conversations,
            snackbar = snackbar,
            actions = RoutinesActions(
                back = model::back,
                save = model.more::saveRoutine,
                delete = model.more::deleteRoutine,
                enable = model.more::enableRoutine,
                run = model.more::runRoutine,
            ),
        )
        Screen.Analytics -> AnalyticsScreen(
            state = analytics,
            usage = home.usage,
            snackbar = snackbar,
            onBack = model::back,
            onMonth = { year, month -> model.more.loadAnalytics(year, month) },
            onArchive = { model.more.archiveAnalytics(context.getString(R.string.archived_months)) },
        )
        Screen.CccSettings -> CccSettingsScreen(
            state = cccSettings,
            presets = home.promptPresets,
            snackbar = snackbar,
            actions = SettingsActions(
                back = model::back,
                save = { model.more.changeSettings(it, context.getString(R.string.settings_saved)) },
                action = { model.more.settingsAction(it, context.getString(R.string.done)) },
                savePresets = model::savePromptPresets,
                deleteLaunchPreset = model.more::deleteLaunchPreset,
                backup = { model.more.backup(context.getString(R.string.backed_up)) },
                connection = { model.open(Screen.Setup) },
            ),
        )
        is Screen.Terminal -> terminal?.takeIf { it.id == screen.id }?.let {
            TerminalScreen(
                state = it,
                name = nameOf(screen.id),
                snackbar = snackbar,
                actions = TerminalActions(
                    back = model::back,
                    paste = model.more::terminalPaste,
                    keys = model.more::terminalKeys,
                    type = model.more::terminalType,
                ),
            )
        }
        Screen.Search -> SearchScreen(
            state = search,
            snackbar = snackbar,
            onBack = model::back,
            onSearch = model::search,
            onOpen = { model.open(Screen.Conversation(it)) },
        )
        Screen.Approvals -> ApprovalsScreen(
            permissions = home.permissions,
            snackbar = snackbar,
            onBack = model::back,
            onOpen = { model.open(Screen.Conversation(it)) },
            onDecide = model::decide,
        )
        Screen.NewConversation -> NewConversationScreen(
            state = newConversation,
            snackbar = snackbar,
            onBack = model::back,
            onLoadSessions = model::loadSessions,
            onLoadMcpServers = model::loadMcpServers,
            onCreate = model::create,
        )
    }
}

package io.github.luquas95.ccc.ui

import android.graphics.Bitmap
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import io.github.luquas95.ccc.data.Language
import io.github.luquas95.ccc.data.Settings
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.core.view.drawToBitmap
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.github.luquas95.ccc.data.Analytics
import io.github.luquas95.ccc.data.CccSettings
import io.github.luquas95.ccc.data.Choice
import io.github.luquas95.ccc.data.ContextFill
import io.github.luquas95.ccc.data.AppRelease
import io.github.luquas95.ccc.data.Conversation
import io.github.luquas95.ccc.data.GitState
import io.github.luquas95.ccc.data.ListDetail
import io.github.luquas95.ccc.data.ConversationTokens
import io.github.luquas95.ccc.data.DayTokens
import io.github.luquas95.ccc.data.Goals
import io.github.luquas95.ccc.data.LiveSession
import io.github.luquas95.ccc.data.ModelTokens
import io.github.luquas95.ccc.data.Review
import io.github.luquas95.ccc.data.Reviews
import io.github.luquas95.ccc.data.Routine
import io.github.luquas95.ccc.data.RoutineKind
import io.github.luquas95.ccc.data.Routines
import io.github.luquas95.ccc.data.TelegramState
import io.github.luquas95.ccc.data.WorkflowEvent
import io.github.luquas95.ccc.data.WorkflowRun
import io.github.luquas95.ccc.data.WorkflowStep
import io.github.luquas95.ccc.data.WorkflowTemplate
import io.github.luquas95.ccc.data.Workflows
import io.github.luquas95.ccc.data.Diff
import io.github.luquas95.ccc.data.DiffLine
import io.github.luquas95.ccc.data.Run
import io.github.luquas95.ccc.data.Task
import io.github.luquas95.ccc.data.Tasks
import io.github.luquas95.ccc.data.ConversationDetail
import io.github.luquas95.ccc.data.Group
import io.github.luquas95.ccc.data.LaunchChoice
import io.github.luquas95.ccc.data.LaunchPresets
import io.github.luquas95.ccc.data.LaunchGroup
import io.github.luquas95.ccc.data.LaunchOption
import io.github.luquas95.ccc.data.LaunchOptions
import io.github.luquas95.ccc.data.Message
import io.github.luquas95.ccc.data.Permission
import io.github.luquas95.ccc.data.PromptPreset
import io.github.luquas95.ccc.data.SearchHit
import io.github.luquas95.ccc.data.Queued
import io.github.luquas95.ccc.data.Status
import io.github.luquas95.ccc.data.UpdateInfo
import io.github.luquas95.ccc.data.Usage
import io.github.luquas95.ccc.data.UsageWindow
import io.github.luquas95.ccc.data.Waiting
import io.github.luquas95.ccc.ui.theme.CccTheme
import java.io.File
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Every screen with made-up data, rendered for real (Robolectric's native
 * graphics) — that they draw at all, and pictures of them in
 * build/screenshots/<locale>/ for docs and pull requests.
 * Czech: ./gradlew testDebugUnitTest -Pscreenshots.locale=cs is not needed —
 * the cs test class below renders the same screens in Czech.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "en-w411dp-h891dp-xxhdpi")
open class ScreenshotsTest {
    @get:Rule
    val compose = createAndroidComposeRule<ComponentActivity>()

    protected open val locale = "en"

    @Test
    fun conversations() = shot("conversations", "shop-api") {
        ConversationsScreen(home, ListDetail.DEFAULT, null, SnackbarHostState(), listActions)
    }

    @Test
    fun dashboard() = shot("dashboard", "shop-api") {
        ConversationsScreen(home.copy(tab = HomeTab.DASHBOARD), ListDetail.DEFAULT, null, SnackbarHostState(), listActions)
    }

    @Test
    fun updateBanner() = shot("update", "shop-api") {
        val update = UpdateInfo(
            available = true, behind = 3, remoteHead = "a1b2c3d", android = true, canApply = true,
            commits = listOf("a1b2c3d Add rate limiting to the orders API", "9f8e7d6 Fix the login redirect",
                "5c4b3a2 Dashboard: context fill and git state"),
        )
        val status = home.status!!.copy(update = update, androidBuild = 6)
        ConversationsScreen(home.copy(status = status, waiting = emptyList(), usage = null), ListDetail.DEFAULT,
            AppRelease("1.2.0", "", ""), SnackbarHostState(), listActions)
    }

    @Test
    fun archive() = shot("archive", "old-prototype") {
        ConversationsScreen(home.copy(tab = HomeTab.ARCHIVE, filter = "proto"), ListDetail.DEFAULT, null, SnackbarHostState(), listActions)
    }

    @Test
    fun conversation() = shot("conversation", "Rate limiting added") {
        ConversationScreen(conversation, home.promptPresets, home.ownGroups, SnackbarHostState(), conversationActions)
    }

    @Test
    fun mention() = shot("mention", "src/api/limits.py") {
        ConversationScreen(
            conversation.copy(mentions = listOf("src/api/limits.py", "src/api/orders.py", "tests/api/test_limits.py")),
            home.promptPresets, home.ownGroups, SnackbarHostState(), conversationActions,
        )
    }

    @Test
    fun tasks() = shot("tasks", "admin endpoints") {
        TasksScreen(tasksState, "shop-api", SnackbarHostState(), tasksActions)
    }

    @Test
    fun runs() = shot("runs", "4f2a9c1") {
        RunsScreen(runsState, "shop-api", SnackbarHostState(), {}, {}, { _, _ -> })
    }

    @Test
    fun diff() = shot("diff", "RATE_PER_MIN") {
        DiffScreen(diffState, SnackbarHostState(), {}, { _, _ -> }, {})
    }

    @Test
    fun reviews() = shot("reviews", "hits()") {
        AgentsScreen(agentsState, "shop-api", 0, SnackbarHostState(), agentsActions)
    }

    @Test
    fun workflow() = shot("workflow", "Add caching") {
        AgentsScreen(agentsState, "shop-api", 2, SnackbarHostState(), agentsActions)
    }

    @Test
    fun routines() = shot("routines", "Nightly") {
        RoutinesScreen(routinesState, home.conversations, SnackbarHostState(), RoutinesActions({}, {}, {}, { _, _ -> }, {}))
    }

    @Test
    fun analytics() = shot("analytics", "mobile-app") {
        AnalyticsScreen(analyticsState, home.usage, SnackbarHostState(), {}, { _, _ -> }, {})
    }

    @Test
    fun cccSettings() = shot("ccc_settings", "80 %") {
        CccSettingsScreen(settingsState, home.promptPresets, SnackbarHostState(), SettingsActions({}, {}, {}, {}, {}, {}, {}), initialTab = 1)
    }

    /** The phone speaks [locale]; the app is set to the other language — the point of the app's own choice. */
    @Test
    fun cccSettingsGeneral() {
        val appLanguage = if (locale == "en") "cs" else "en"
        Settings(compose.activity).language = appLanguage
        val wrapped = Language.wrap(compose.activity)
        val groups = if (appLanguage == "cs") listOf(Choice("project", "Podle projektu a vlastní skupiny"), Choice("own", "Jen vlastní skupiny"))
        else listOf(Choice("project", "By project, and your own groups"), Choice("own", "Only your own groups"))
        val label = Language.CHOICES.first { it.first == appLanguage }.second
        shot("ccc_settings_general", label) {
            CompositionLocalProvider(LocalContext provides wrapped, LocalConfiguration provides wrapped.resources.configuration) {
                CccSettingsScreen(settingsState.copy(groupsChoices = groups), home.promptPresets, SnackbarHostState(),
                    SettingsActions({}, {}, {}, {}, {}, {}, {}), initialTab = 0, language = appLanguage)
            }
        }
    }

    @Test
    fun liveSessions() = shot("live_sessions", "refactor-auth") {
        ConversationsScreen(home.copy(tab = HomeTab.SESSIONS), ListDetail.DEFAULT, null, SnackbarHostState(), listActions,
            listOf(LiveSession("a1", "refactor-auth", "/home/you/projects/shop-api", "interactive", "busy"),
                LiveSession("b2", "nightly-etl", "/home/you/projects/data-pipeline", "background", "idle")))
    }

    @Test
    fun search() = shot("search", "rate limiting") {
        SearchScreen(searchState, SnackbarHostState(), {}, {}, {})
    }

    @Test
    fun approvals() = shot("approvals", "Bash") {
        ApprovalsScreen(listOf(permission), SnackbarHostState(), {}, {}, { _, _ -> })
    }

    @Test
    fun newConversation() = shot("new_conversation", "shop-api") {
        NewConversationScreen(
            NewConversationState(launchOptions, listOf("/home/you/projects/shop-api", "/home/you/projects/docs-site"),
                LaunchPresets(presets = listOf(LaunchChoice(listOf("perm_plan", "model_opus"), name = "Review"),
                    LaunchChoice(listOf("perm_skip", "model_sonnet"), name = "Quick fix")))),
            SnackbarHostState(), {}, {}, {}, {},
        )
    }

    @Test
    fun setup() = shot("setup", "ccc") {
        SetupScreen("", false, false, ListDetail.DEFAULT, { _, _ -> }, SnackbarHostState(), null, { _, _, _ -> }, {}, {})
    }

    @Test
    fun connection() = shot("connection", "computer.tailnet") {
        SetupScreen("computer.tailnet.ts.net", true, true, ListDetail.DEFAULT, { _, _ -> }, SnackbarHostState(), {}, { _, _, _ -> }, {}, {},
            devices = listOf(
                io.github.luquas95.ccc.data.Device(1, "Pixel 8", lastSeenAt = "2026-10-30T12:01:00", lastIp = "100.64.0.7", current = true),
                io.github.luquas95.ccc.data.Device(2, "Redmi Note 13", lastSeenAt = "2026-10-29T07:54:00", lastIp = "100.64.0.9"),
            ))
    }

    @Test
    fun conversationListDetails() = shot("list_details", "computer.tailnet", scrollTo = io.github.luquas95.ccc.R.string.detail_path) {
        SetupScreen("computer.tailnet.ts.net", true, true, setOf(ListDetail.CONTEXT, ListDetail.GIT), { _, _ -> },
            SnackbarHostState(), {}, { _, _, _ -> }, {}, {})
    }

    @Test
    fun routine_delete() = shot("routine_delete", "Nightly", dialog = true) {
        RoutinesScreen(routinesState, home.conversations, SnackbarHostState(), RoutinesActions({}, {}, {}, { _, _ -> }, {}))
    }

    @Test
    fun update_failed() = shot("update_failed", "Nothing to update", dialog = true) {
        UpdateOutcomeDialog(AppViewModel.UpdateOutcome(false, "Nothing to update: ccc is already at the latest commit."), {})
    }

    @Test
    fun terminal() = shot("terminal", "Welcome") {
        TerminalScreen(terminalState, "web", SnackbarHostState(), TerminalActions({}, { _, _ -> }, {}, {}))
    }

    private fun shot(name: String, expect: String, scrollTo: Int? = null, dialog: Boolean = false, content: @Composable () -> Unit) {
        compose.setContent { CccTheme(content) }
        compose.onAllNodesWithText(expect, substring = true, useUnmergedTree = true).onFirst().assertExists()
        scrollTo?.let { compose.onAllNodesWithText(compose.activity.getString(it)).onFirst().performScrollTo() }
        compose.waitForIdle()
        if (dialog) {
            if (name == "routine_delete") {
                val delete = compose.activity.getString(io.github.luquas95.ccc.R.string.delete)
                compose.onAllNodesWithContentDescription(delete).onFirst().performClick()
                compose.waitForIdle()
            }
            saveWithDialog(name)
        } else save(name)
    }

    /** The dialog is a window of its own: lay its picture over the dimmed screen below. */
    private fun saveWithDialog(name: String) {
        val screen = compose.activity.window.decorView.drawToBitmap()
        val window = org.robolectric.shadows.ShadowDialog.getLatestDialog().window!!.decorView
        val box = window.drawToBitmap()
        val out = screen.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = android.graphics.Canvas(out)
        canvas.drawColor(android.graphics.Color.argb(120, 0, 0, 0))
        canvas.drawBitmap(box, (out.width - box.width) / 2f, (out.height - box.height) / 2f, null)
        val folder = File("build/screenshots/$locale").apply { mkdirs() }
        File(folder, "$name.png").outputStream().use { out.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun save(name: String) {
        val bitmap = compose.activity.window.decorView.drawToBitmap()
        val folder = File("build/screenshots/$locale").apply { mkdirs() }
        File(folder, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private companion object {
        val listActions = ConversationsActions({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, { _, _ -> }, {}, {}, {})
        val conversationActions = ConversationActions(
            {}, { _, _ -> }, {}, {}, { _, _ -> }, {}, {}, {}, {}, { _, _ -> }, {}, {}, {}, {}, {},
        )
        val terminalState = TerminalState(
            5,
            io.github.luquas95.ccc.data.Terminal(
                "\u001b[38;5;214m✻\u001b[0m \u001b[1mWelcome to Claude Code!\u001b[0m\n\n" +
                    "  \u001b[2m/help for help, /status for your current setup\u001b[0m\n\n" +
                    "\u001b[38;5;74m> \u001b[0mAdd caching to GET /products\n\n" +
                    "\u001b[32m●\u001b[0m I'll add a Redis cache with a 60 s TTL.\n\n" +
                    "\u001b[1mDo you want to make this edit to src/api/products.py?\u001b[0m\n" +
                    " \u001b[38;5;74m❯ 1. Yes\u001b[0m\n   2. Yes, and don't ask again this session\n   3. No, and tell Claude what to do differently\n",
                100, 30, 3, 9,
            ),
        )
        val agentsActions = AgentsActions({}, { _, _, _ -> }, {}, {}, { _, _, _ -> }, {}, { _, _, _, _ -> }, { _, _ -> }, {})

        val agentsState = AgentsState(
            1,
            reviews = Reviews(active = false, reviews = listOf(
                Review(4, "done", "done", verdict = "FAIL", round = 1, maxRounds = 3, untilPass = true,
                    scope = "2 runs since the last review (4f2a9c1, 9b1d77a)",
                    report = "1. src/api/limits.py:5 — hits() counts per process, not per API key across workers.\n" +
                        "2. No test for the 429 Retry-After header.\n\nVERDICT: FAIL — the limit isn't shared between workers.",
                    canApply = true, createdAt = "2026-10-21T20:20:00"),
                Review(3, "done", "done", verdict = "PASS", scope = "run 8c0d1e2", report = "VERDICT: PASS — clean rename.",
                    createdAt = "2026-10-21T18:10:00"),
            )),
            goals = Goals(), workflows = Workflows(runs = listOf(
                WorkflowRun(2, "plan-build-review", "Add caching to GET /products", round = 1, maxRounds = 3, status = "waiting",
                    statusLabel = "waits for you", steps = listOf(WorkflowStep("plan", "done"), WorkflowStep("your approval", "waits"),
                        WorkflowStep("build", "to_come"), WorkflowStep("review ×2", "to_come")),
                    events = listOf(WorkflowEvent("plan", "plan", "planner", 1, "done",
                        output = "1. Cache in Redis for 60 s keyed by query\n2. Invalidate on product update\n3. Tests for hit / miss / invalidation")),
                    createdAt = "2026-10-21T20:30:00"),
            ), active = true, waiting = true),
            templates = listOf(WorkflowTemplate("plan-build-review", "Plan → approval → build → review",
                "plan → your approval → build → review ×2  (back to build at most 3×)")),
        )

        val routinesState = Routines(
            kinds = listOf(RoutineKind("daily", "Every day at", "e.g. 18:00"), RoutineKind("cron", "Cron pattern", "e.g. 0 22 * * *")),
            routines = listOf(
                Routine(1, 1, "shop-api", "Nightly dependencies", "Update dependencies, run the tests and open a PR", "daily", "22:00",
                    "every day at 22:00", nextRunAt = "2026-10-22T22:00:00", lastStatus = "queued in its conversation"),
                Routine(2, 3, "data-pipeline", "Weekly report", "Summarise last week's failed jobs", "weekly", "monday 08:00",
                    "Mondays at 08:00", fresh = true, enabled = false),
            ),
        )

        val analyticsState = Analytics(
            2026, 10, "October 2026", 3_643_987,
            byDay = (1..21).map { DayTokens("2026-10-%02d".format(it), (it * 37_000L) % 260_000 + 20_000) },
            byModel = listOf(ModelTokens("claude-sonnet-5-5", 3_157_987), ModelTokens("claude-opus-5-5", 486_000)),
            byConversation = listOf(ConversationTokens(4, "mobile-app", tokens = 3_017_988, success = 18),
                ConversationTokens(1, "shop-api", tokens = 486_000, success = 4, rateLimited = 1)),
            blockedMinutes = 12.5, reserve = 80,
        )

        val settingsState = CccSettings(
            language = "auto", languages = listOf(Choice("auto", "Auto (system)"), Choice("en", "English"), Choice("cs", "Čeština")),
            groups = "project", groupsChoices = listOf(Choice("project", "By project, and your own groups"), Choice("own", "Only your own groups")),
            continueText = "Continue where you stopped.", usageReserve = 80, reserveChoices = listOf(50, 80, 90),
            reviewModel = "", reviewModels = listOf(Choice("", "Same as the conversation"), Choice("opus", "Opus")),
            windowChoices = listOf(200_000, 1_000_000), thresholdChoices = listOf(60, 75, 90),
            sendChoices = listOf(Choice("", "Only save to the folder")), telegram = TelegramState(true, "123456789", true),
            launchPresets = listOf("Quick fix", "Review"),
        )
        val tasksActions = TasksActions({}, { _, _ -> }, { _, _, _ -> }, {}, { _, _ -> }, {}, {})

        val tasksState = TasksState(1, Tasks(paused = false, autoContinue = true, tasks = listOf(
            Task(9, "Add rate limiting to the admin endpoints too"),
            Task(10, "Run the full test suite and fix anything that fails", notBefore = "2026-10-22T23:30:00"),
            Task(11, "Nightly: update dependencies and open a PR", byRoutine = true),
        )))

        val runsState = RunsState(1, listOf(
            Run(31, "2026-10-21T20:13:00", status = "success", tokens = 48_210, task = "Add rate limiting to GET /orders",
                result = "Rate limiting added: GET /orders and GET /orders/{id} allow 60 requests/min…", commit = "4f2a9c1e0b"),
            Run(30, "2026-10-21T19:40:00", status = "rate_limited", tokens = 12_004, task = "Refactor the order service",
                error = "Usage limit reached — resets at 20:00"),
            Run(29, "2026-10-21T18:02:00", status = "success", tokens = 30_550, task = "Rename OrderDTO to Order",
                result = "Renamed in 14 files.", commit = "9b1d77aa21", revertedBy = "c0ffee1234"),
        ))

        val diffState = DiffState(
            31,
            Diff("4f2a9c1e0b", "Add rate limiting to GET /orders", listOf(
                DiffLine(0, "commit 4f2a9c1e0b", "header"),
                DiffLine(1, " src/api/limits.py | 12 ++++++++++++", "header"),
                DiffLine(2, "diff --git a/src/api/limits.py b/src/api/limits.py", "meta"),
                DiffLine(3, "@@ -1,3 +1,8 @@", "hunk", "src/api/limits.py", newLine = 1, commentable = true),
                DiffLine(4, " from fastapi import Request", "context", "src/api/limits.py", 1, 1, true),
                DiffLine(5, "-RATE = None", "removed", "src/api/limits.py", oldLine = 2, commentable = true),
                DiffLine(6, "+RATE_PER_MIN = 60", "added", "src/api/limits.py", newLine = 2, commentable = true),
                DiffLine(7, "+WINDOW_SECONDS = 60", "added", "src/api/limits.py", newLine = 3, commentable = true),
                DiffLine(8, "+def limited(key: str) -> bool:", "added", "src/api/limits.py", newLine = 4, commentable = true),
                DiffLine(9, "+    return hits(key, WINDOW_SECONDS) > RATE_PER_MIN", "added", "src/api/limits.py",
                    newLine = 5, commentable = true),
            )),
            comments = mapOf(6 to "Read this from the settings, not a constant."),
        )

        val searchState = SearchState(
            query = "rate limiting",
            hits = listOf(
                SearchHit(1, "shop-api", "2026-10-21T18:13:00+00:00", "assistant_text",
                    "Rate limiting added: • GET /orders and GET /orders/{id} allow 60 requests/min per API key…"),
                SearchHit(1, "shop-api", "2026-10-21T18:02:00+00:00", "human",
                    "Add rate limiting to GET /orders — 60 requests a minute per API key."),
                SearchHit(6, "old-prototype", "2026-09-02T09:40:00+00:00", "assistant_text",
                    "…no rate limiting yet, the prototype trusts every client…"),
            ),
        )

        val permission = Permission(
            id = 1, conversationId = 1, tool = "Bash", conversation = "shop-api",
            input = buildJsonObject { put("command", JsonPrimitive("pytest -q tests/api")) },
        )

        val home = HomeState(
            status = Status("0.1.0", "en", daemonRunning = true, conversations = 5, running = 2, needsApproval = 1),
            usage = Usage(UsageWindow(64.0), UsageWindow(38.0)),
            permissions = listOf(permission),
            waiting = listOf(Waiting(1, "shop-api", "approval", "waits for approval"),
                Waiting(3, "data-pipeline", "error", "error")),
            ownGroups = listOf("Release 2.1"),
            promptPresets = listOf(PromptPreset(1, "Tests", "Run the full test suite", sendNow = true),
                PromptPreset(2, "Commit", "Commit what you have", sendNow = false)),
            archived = listOf(
                Conversation(6, "old-prototype", "/home/you/projects/old-prototype", "idle", "headless", archived = true),
                Conversation(7, "spike-auth", "/home/you/projects/spike-auth", "idle", "interactive", archived = true),
            ),
            loaded = true,
            live = true,
            conversations = listOf(
                Conversation(1, "shop-api", "/home/you/projects/shop-api", "running", "interactive", pending = 2,
                    needsApproval = true, group = Group("own:Release 2.1", "Release 2.1"),
                    context = ContextFill(124_000, 62, ""), git = GitState("feature/rate-limit", 12, 3, 2, 0)),
                Conversation(2, "docs-site", "/home/you/projects/docs-site", "waiting_retry", "interactive", pending = 1,
                    group = Group("own:Release 2.1", "Release 2.1"),
                    context = ContextFill(172_000, 86, "warn"), git = GitState("main", 0, 0, 0, 1)),
                Conversation(3, "data-pipeline", "/home/you/projects/data-pipeline", "blocked_error", "headless",
                    lastError = "pytest failed: 3 tests", group = Group("project:/home/you/projects/data-pipeline", "data-pipeline")),
                Conversation(4, "mobile-app", "/home/you/projects/mobile-app", "idle", "interactive", unseen = true,
                    group = Group("project:/home/you/projects/mobile-app", "mobile-app"),
                    context = ContextFill(186_000, 93, "danger"), git = GitState("fix/login-crash", 4, 1, 1, 0)),
                Conversation(5, "infra", "/home/you/projects/infra", "running", "remote_control",
                    group = Group("project:/home/you/projects/infra", "infra")),
            ),
        )

        val conversation = ConversationState(
            id = 1,
            total = 5,
            detail = ConversationDetail(
                1, "shop-api", "/home/you/projects/shop-api", "running", "interactive", pending = 1,
                flags = "skip permissions · Opus · effort max",
                queued = listOf(Queued(9, "Add rate limiting to the admin endpoints too")),
                permissions = listOf(permission),
            ),
            messages = listOf(
                Message(0, "human", "Add rate limiting to GET /orders — 60 requests a minute per API key.",
                    "2026-10-21T18:02:00+00:00"),
                Message(1, "tool_call", "Edit: src/api/limits.py", "2026-10-21T18:03:00+00:00"),
                Message(2, "tool_result", "The file src/api/limits.py has been updated.", "2026-10-21T18:03:00+00:00"),
                Message(3, "tool_call", "Bash: pytest -q tests/api/test_orders.py", "2026-10-21T18:04:00+00:00"),
                Message(4, "assistant_text", "Rate limiting added:\n• GET /orders and GET /orders/{id} allow 60 requests/min " +
                    "per API key\n• limits live in src/api/limits.py\n• 3 new tests — all 8 passing", "2026-10-21T18:13:00+00:00"),
            ),
        )

        val launchOptions = LaunchOptions(
            groups = listOf(
                LaunchGroup("session", "Session", exclusive = true, required = true, options = listOf(
                    LaunchOption("session_new", "New session"), LaunchOption("session_continue", "Continue last in directory"),
                    LaunchOption("session_resume", "Resume selected…"), LaunchOption("session_from_pr", "From pull request…"))),
                LaunchGroup("session_extra", "", exclusive = false, required = false,
                    options = listOf(LaunchOption("fork", "As a copy (fork)"))),
                LaunchGroup("permissions", "Permissions", exclusive = true, required = true, options = listOf(
                    LaunchOption("perm_skip", "Skip all permission checks"), LaunchOption("perm_accept_edits", "Auto-accept edits"),
                    LaunchOption("perm_plan", "Plan only"))),
                LaunchGroup("model", "Model", exclusive = true, required = false, options = listOf(
                    LaunchOption("model_opus", "Opus"), LaunchOption("model_sonnet", "Sonnet"),
                    LaunchOption("model_haiku", "Haiku"), LaunchOption("model_fable", "Fable"))),
            ),
            default = listOf("session_new", "perm_skip"),
        )
    }
}

/** The same screens in Czech (ccc's texts in them stay as the data has them). */
@Config(sdk = [35], qualifiers = "cs-w411dp-h891dp-xxhdpi")
class ScreenshotsCzechTest : ScreenshotsTest() {
    override val locale = "cs"
}

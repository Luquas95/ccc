package io.github.luquas95.ccc.ui

import android.graphics.Bitmap
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.core.view.drawToBitmap
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.github.luquas95.ccc.data.Conversation
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
        ConversationsScreen(home, SnackbarHostState(), listActions)
    }

    @Test
    fun archive() = shot("archive", "old-prototype") {
        ConversationsScreen(home.copy(showArchive = true, filter = "proto"), SnackbarHostState(), listActions)
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
            SnackbarHostState(), {}, {}, {},
        )
    }

    @Test
    fun setup() = shot("setup", "ccc") {
        SetupScreen("", false, SnackbarHostState(), null, { _, _, _ -> }, {})
    }

    private fun shot(name: String, expect: String, content: @Composable () -> Unit) {
        compose.setContent { CccTheme(content) }
        compose.onAllNodesWithText(expect, substring = true, useUnmergedTree = true).onFirst().assertExists()
        compose.waitForIdle()
        val bitmap = compose.activity.window.decorView.drawToBitmap()
        val folder = File("build/screenshots/$locale").apply { mkdirs() }
        File(folder, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private companion object {
        val listActions = ConversationsActions({}, {}, {}, {}, {}, {}, {}, {}, {}, { _, _ -> }, {})
        val conversationActions = ConversationActions(
            {}, { _, _ -> }, {}, {}, { _, _ -> }, {}, {}, {}, {}, { _, _ -> }, {},
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
                    needsApproval = true, group = Group("own:Release 2.1", "Release 2.1")),
                Conversation(2, "docs-site", "/home/you/projects/docs-site", "waiting_retry", "interactive", pending = 1,
                    group = Group("own:Release 2.1", "Release 2.1")),
                Conversation(3, "data-pipeline", "/home/you/projects/data-pipeline", "blocked_error", "headless",
                    lastError = "pytest failed: 3 tests", group = Group("project:/home/you/projects/data-pipeline", "data-pipeline")),
                Conversation(4, "mobile-app", "/home/you/projects/mobile-app", "idle", "interactive", unseen = true,
                    group = Group("project:/home/you/projects/mobile-app", "mobile-app")),
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

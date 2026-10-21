package io.github.luquas95.ccc

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
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.luquas95.ccc.ui.AppViewModel
import io.github.luquas95.ccc.ui.ApprovalsScreen
import io.github.luquas95.ccc.ui.ConversationScreen
import io.github.luquas95.ccc.ui.ConversationsScreen
import io.github.luquas95.ccc.ui.NewConversationScreen
import io.github.luquas95.ccc.ui.Screen
import io.github.luquas95.ccc.ui.SetupScreen
import io.github.luquas95.ccc.ui.theme.CccTheme

class MainActivity : ComponentActivity() {
    private val model: AppViewModel by viewModels()

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
    }
}

@Composable
private fun App(model: AppViewModel) {
    val screens by model.screens.collectAsStateWithLifecycle()
    val home by model.home.collectAsStateWithLifecycle()
    val conversation by model.conversation.collectAsStateWithLifecycle()
    val newConversation by model.newConversation.collectAsStateWithLifecycle()
    val message by model.message.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
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
            snackbar = snackbar,
            onBack = if (screens.size > 1) model::back else null,
            onConnect = model::connect,
            onSignOut = model::signOut,
        )
        Screen.Conversations -> ConversationsScreen(
            state = home,
            snackbar = snackbar,
            onOpen = { model.open(Screen.Conversation(it)) },
            onApprovals = { model.open(Screen.Approvals) },
            onSettings = { model.open(Screen.Setup) },
            onNew = { model.open(Screen.NewConversation) },
            onRefresh = model::pullToRefresh,
        )
        is Screen.Conversation -> conversation?.takeIf { it.id == screen.id }?.let {
            ConversationScreen(
                state = it,
                snackbar = snackbar,
                onBack = model::back,
                onSend = model::send,
                onRetry = model::retry,
                onLoadOlder = model::loadOlder,
                onDecide = model::decide,
            )
        }
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
            onCreate = model::create,
        )
    }
}

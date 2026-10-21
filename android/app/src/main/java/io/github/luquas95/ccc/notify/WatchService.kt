package io.github.luquas95.ccc.notify

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import io.github.luquas95.ccc.MainActivity
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.Alert
import io.github.luquas95.ccc.data.Alerts
import io.github.luquas95.ccc.data.ApiException
import io.github.luquas95.ccc.data.CccApi
import io.github.luquas95.ccc.data.Settings
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Keeps ccc's event stream open while the app is closed and turns what
 * needs you into notifications: an approval (with Allow / Deny right in
 * it), an error, a usage limit, a finished reply. A foreground service —
 * the only way Android lets an app keep a connection; there's no push
 * server, everything stays on the tailnet.
 */
class WatchService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val checking = Mutex()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        channels(this)
        val watching = NotificationCompat.Builder(this, CHANNEL_WATCH)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.watch_title))
            .setContentText(getString(R.string.watch_text))
            .setContentIntent(openApp(this, null))
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(WATCH_ID, watching, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(WATCH_ID, watching)
        }
        scope.launch { watch() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private suspend fun watch() {
        val settings = Settings(this)
        if (!settings.configured || !settings.notifications) {
            stopSelf()
            return
        }
        val api = CccApi(settings.server, settings.token)
        var wait = 2_000L
        while (true) {
            try {
                api.events().collect {
                    wait = 2_000L
                    check(api, settings)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: IOException) {
                if (e is ApiException && e.code == 401) {
                    settings.notifications = false
                    stopSelf()
                    return
                }
            }
            delay(wait)
            wait = (wait * 2).coerceAtMost(60_000L)
        }
    }

    private suspend fun check(api: CccApi, settings: Settings) = checking.withLock {
        val changes = Alerts.changes(api.permissions(), api.waiting(), settings.shownAlerts)
        val manager = NotificationManagerCompat.from(this)
        changes.gone.forEach { manager.cancel(it, ALERT_ID) }
        changes.show.forEach { post(this, it) }
        settings.shownAlerts = settings.shownAlerts - changes.gone + changes.show.map { it.key }
    }

    companion object {
        const val CHANNEL_WATCH = "watch"
        const val CHANNEL_APPROVALS = "approvals"
        const val CHANNEL_NEEDS_YOU = "needs_you"
        const val WATCH_ID = 1
        const val ALERT_ID = 2
        const val EXTRA_CONVERSATION = "conversation"

        /** Start or stop watching, as the setting says. */
        fun sync(context: Context) {
            val settings = Settings(context)
            val intent = Intent(context, WatchService::class.java)
            if (settings.configured && settings.notifications) {
                ContextCompat.startForegroundService(context, intent)
            } else {
                context.stopService(intent)
            }
        }

        fun channels(context: Context) {
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannels(listOf(
                NotificationChannel(CHANNEL_APPROVALS, context.getString(R.string.channel_approvals), NotificationManager.IMPORTANCE_HIGH),
                NotificationChannel(CHANNEL_NEEDS_YOU, context.getString(R.string.channel_needs_you), NotificationManager.IMPORTANCE_DEFAULT),
                NotificationChannel(CHANNEL_WATCH, context.getString(R.string.channel_watch), NotificationManager.IMPORTANCE_MIN),
            ))
        }

        /** The app, on a conversation when [conversationId] is given. */
        fun openApp(context: Context, conversationId: Int?): PendingIntent {
            val intent = Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            conversationId?.let { intent.putExtra(EXTRA_CONVERSATION, it) }
            return PendingIntent.getActivity(context, conversationId ?: 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }

        private fun post(context: Context, alert: Alert) {
            val builder = when (alert) {
                is Alert.Approval -> {
                    val p = alert.permission
                    NotificationCompat.Builder(context, CHANNEL_APPROVALS)
                        .setContentTitle(context.getString(R.string.approval_title, p.conversation ?: "Claude", p.tool))
                        .setContentText(p.input.values.firstOrNull()?.toString()?.trim('"')?.take(200).orEmpty())
                        .setContentIntent(openApp(context, p.conversationId))
                        .addAction(0, context.getString(R.string.allow), ApprovalReceiver.intent(context, p.id, "allow", alert.key))
                        .addAction(0, context.getString(R.string.deny), ApprovalReceiver.intent(context, p.id, "deny", alert.key))
                        .setPriority(NotificationCompat.PRIORITY_HIGH)
                        .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                }
                is Alert.NeedsYou -> NotificationCompat.Builder(context, CHANNEL_NEEDS_YOU)
                    .setContentTitle(alert.waiting.name)
                    .setContentText(alert.waiting.label)
                    .setContentIntent(openApp(context, alert.waiting.conversationId))
                    .setAutoCancel(true)
            }
            val notification: Notification = builder.setSmallIcon(R.drawable.ic_notification).build()
            try {
                NotificationManagerCompat.from(context).notify(alert.key, ALERT_ID, notification)
            } catch (e: SecurityException) {
                // Notifications aren't allowed (Android 13+): nothing to show.
            }
        }
    }
}

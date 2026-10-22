package io.github.luquas95.ccc.notify

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationManagerCompat
import io.github.luquas95.ccc.data.CccApi
import io.github.luquas95.ccc.data.Settings
import java.io.IOException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Allow / Deny tapped in an approval's notification: answered without opening the app. */
class ApprovalReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getIntExtra(EXTRA_ID, -1)
        val decision = intent.getStringExtra(EXTRA_DECISION) ?: return
        val key = intent.getStringExtra(EXTRA_KEY) ?: return
        val settings = Settings(context)
        if (id < 0 || !settings.configured) return
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                CccApi(settings.server, settings.token).decide(id, decision)
                NotificationManagerCompat.from(context).cancel(key, WatchService.ALERT_ID)
            } catch (e: IOException) {
                // Not answered (offline, or already decided): the notification stays to open the app.
            } finally {
                pending.finish()
            }
        }
    }

    companion object {
        private const val EXTRA_ID = "id"
        private const val EXTRA_DECISION = "decision"
        private const val EXTRA_KEY = "key"

        fun intent(context: Context, permissionId: Int, decision: String, key: String): PendingIntent {
            val intent = Intent(context, ApprovalReceiver::class.java)
                .putExtra(EXTRA_ID, permissionId)
                .putExtra(EXTRA_DECISION, decision)
                .putExtra(EXTRA_KEY, key)
            val code = permissionId * 2 + if (decision == "allow") 0 else 1
            return PendingIntent.getBroadcast(context, code, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }
    }
}

/** After the phone starts (or the app is updated): watch again if notifications are on. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            WatchService.sync(context)
        }
    }
}

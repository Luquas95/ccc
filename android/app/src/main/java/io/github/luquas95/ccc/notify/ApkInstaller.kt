package io.github.luquas95.ccc.notify

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import io.github.luquas95.ccc.R
import java.io.File
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * Installs the downloaded app with the system's PackageInstaller: the system asks the person
 * (once more) and the outcome comes back to [InstallResultReceiver] — so a failure is told, not silent.
 */
object ApkInstaller {
    const val ACTION = "io.github.luquas95.ccc.INSTALL_RESULT"

    /** What went wrong (or null): the app shows it as a message. */
    val problem = MutableStateFlow<String?>(null)

    fun install(context: Context, apk: File) {
        val installer = context.packageManager.packageInstaller
        val id = installer.createSession(PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL))
        installer.openSession(id).use { session ->
            apk.inputStream().use { input ->
                session.openWrite("ccc.apk", 0, apk.length()).use { output ->
                    input.copyTo(output)
                    session.fsync(output)
                }
            }
            val result = PendingIntent.getBroadcast(
                context, id, Intent(ACTION).setPackage(context.packageName),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
            )
            session.commit(result.intentSender)
        }
    }
}

class InstallResultReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                confirm?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)?.let(context::startActivity)
            }
            PackageInstaller.STATUS_SUCCESS -> Unit // the app is replaced and restarts
            else -> {
                val why = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE).orEmpty()
                ApkInstaller.problem.value = context.getString(R.string.app_install_failed, "$why ($status)")
            }
        }
    }
}

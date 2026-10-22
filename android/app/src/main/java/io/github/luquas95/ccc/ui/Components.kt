package io.github.luquas95.ccc.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.luquas95.ccc.R
import io.github.luquas95.ccc.data.ConversationStatus
import io.github.luquas95.ccc.data.Permission
import io.github.luquas95.ccc.data.Usage
import io.github.luquas95.ccc.data.UsageWindow
import io.github.luquas95.ccc.ui.theme.CccColors
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject

fun statusColor(status: ConversationStatus, needsApproval: Boolean = false): Color = when {
    needsApproval -> CccColors.Approval
    status == ConversationStatus.RUNNING -> CccColors.Running
    status == ConversationStatus.WAITING_RETRY || status == ConversationStatus.PAUSED_LIMIT -> CccColors.Waiting
    status == ConversationStatus.BLOCKED_ERROR -> CccColors.Error
    else -> CccColors.Line
}

@Composable
fun statusLabel(status: ConversationStatus): String = stringResource(
    when (status) {
        ConversationStatus.IDLE -> R.string.status_idle
        ConversationStatus.RUNNING -> R.string.status_running
        ConversationStatus.WAITING_RETRY -> R.string.status_waiting_retry
        ConversationStatus.BLOCKED_ERROR -> R.string.status_blocked_error
        ConversationStatus.PAUSED_LIMIT -> R.string.status_paused_limit
        ConversationStatus.UNKNOWN -> R.string.status_unknown
    },
)

@Composable
fun StatusDot(color: Color, modifier: Modifier = Modifier) {
    Box(modifier.size(10.dp).background(color, CircleShape))
}

/** "14:05" today, else "21. 10. 14:05" — in the phone's time zone. */
fun shortTime(iso: String?): String? {
    iso ?: return null
    val time = runCatching { OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()) }
        .recoverCatching { java.time.LocalDateTime.parse(iso).atZone(ZoneId.systemDefault()) }
        .getOrNull() ?: return null
    val today = time.toLocalDate() == java.time.LocalDate.now()
    return time.format(DateTimeFormatter.ofPattern(if (today) "HH:mm" else "d. M. HH:mm"))
}

private val pretty = Json { prettyPrint = true }

fun prettyInput(input: JsonObject): String = pretty.encodeToString(JsonObject.serializer(), input)

/** Claude asks to use a tool: what and with which input, Allow / Always / Deny. */
@Composable
fun ApprovalCard(
    permission: Permission,
    conversationName: String?,
    onDecide: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CccColors.Surface),
        border = BorderStroke(1.dp, CccColors.Approval),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(
                stringResource(R.string.approval_title, conversationName ?: stringResource(R.string.claude), permission.tool),
                style = MaterialTheme.typography.titleSmall,
                color = CccColors.Approval,
            )
            Spacer(Modifier.height(8.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .heightIn(max = 180.dp)
                    .background(CccColors.Background, RoundedCornerShape(6.dp))
                    .verticalScroll(rememberScrollState())
                    .horizontalScroll(rememberScrollState())
                    .padding(8.dp),
            ) {
                Text(prettyInput(permission.input), fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Button(
                    onClick = { onDecide("allow") },
                    colors = ButtonDefaults.buttonColors(containerColor = CccColors.Claude, contentColor = Color.Black),
                ) { Text(stringResource(R.string.allow)) }
                OutlinedButton(onClick = { onDecide("always") }) { Text(stringResource(R.string.always_allow)) }
                Spacer(Modifier.weight(1f))
                TextButton(
                    onClick = { onDecide("deny") },
                    colors = ButtonDefaults.textButtonColors(contentColor = CccColors.Error),
                ) { Text(stringResource(R.string.deny)) }
            }
        }
    }
}

/** The usage limits: 5-hour and 7-day windows. */
@Composable
fun UsageCard(usage: Usage, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        usage.fiveHour?.let { UsageRow(stringResource(R.string.usage_five_hour), it) }
        usage.sevenDay?.let { UsageRow(stringResource(R.string.usage_seven_day), it) }
    }
}

@Composable
private fun UsageRow(label: String, window: UsageWindow) {
    val fraction = (window.percent / 100).toFloat().coerceIn(0f, 1f)
    val color = when {
        window.percent >= 90 -> CccColors.Error
        window.percent >= 70 -> CccColors.Waiting
        else -> CccColors.Title
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.width(72.dp), style = MaterialTheme.typography.labelMedium, color = CccColors.Muted)
        LinearProgressIndicator(
            progress = { fraction },
            modifier = Modifier.weight(1f).height(6.dp),
            color = color,
            trackColor = CccColors.SurfaceHigh,
            gapSize = 0.dp,
            drawStopIndicator = {},
        )
        Text(
            "${window.percent.toInt()} %",
            Modifier.width(48.dp).padding(start = 8.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

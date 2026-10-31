package io.github.luquas95.ccc.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.luquas95.ccc.data.Markdown
import io.github.luquas95.ccc.data.MdBlock
import io.github.luquas95.ccc.data.MdSpan
import io.github.luquas95.ccc.ui.theme.CccColors

/** Claude's answer as formatted text: headings, lists, code, bold … instead of the raw Markdown marks. */
@Composable
fun MarkdownText(text: String, modifier: Modifier = Modifier) {
    val blocks = remember(text) { Markdown.parse(text) }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        blocks.forEach { Block(it) }
    }
}

@Composable
private fun Block(block: MdBlock) {
    val body = MaterialTheme.typography.bodyMedium
    when (block) {
        is MdBlock.Paragraph -> Text(styled(block.spans), style = body)
        is MdBlock.Heading -> Text(
            styled(block.spans),
            style = when (block.level) {
                1 -> MaterialTheme.typography.titleLarge
                2 -> MaterialTheme.typography.titleMedium
                else -> MaterialTheme.typography.titleSmall
            },
            fontWeight = FontWeight.Bold,
            color = CccColors.Title,
            modifier = Modifier.padding(top = 4.dp),
        )
        is MdBlock.Item -> Row(Modifier.padding(start = (block.depth * 16).dp)) {
            Text(block.marker, style = body, color = CccColors.Muted, modifier = Modifier.width(if (block.marker.length > 2) 28.dp else 18.dp))
            Text(styled(block.spans), style = body)
        }
        is MdBlock.Quote -> Row(Modifier.height(IntrinsicSize.Min)) {
            Row(Modifier.width(3.dp).fillMaxHeight().background(CccColors.Line)) {}
            Text(styled(block.spans), style = body, color = CccColors.Muted, modifier = Modifier.padding(start = 8.dp))
        }
        is MdBlock.Code -> Text(
            block.text,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            softWrap = false,
            modifier = Modifier
                .fillMaxWidth()
                .background(CccColors.SurfaceHigh, RoundedCornerShape(6.dp))
                .horizontalScroll(rememberScrollState())
                .padding(8.dp),
        )
        is MdBlock.Table -> Text(
            block.lines.joinToString("\n"),
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            softWrap = false,
            modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        )
        MdBlock.Rule -> Row(Modifier.fillMaxWidth().height(1.dp).background(CccColors.Line)) {}
    }
}

@Composable
private fun styled(spans: List<MdSpan>): AnnotatedString {
    val linkStyle = TextLinkStyles(SpanStyle(color = CccColors.Title, textDecoration = TextDecoration.Underline))
    return remember(spans) {
        buildAnnotatedString {
            spans.forEach { span ->
                val style = SpanStyle(
                    fontWeight = if (span.bold) FontWeight.Bold else null,
                    fontStyle = if (span.italic) FontStyle.Italic else null,
                    textDecoration = if (span.strike) TextDecoration.LineThrough else null,
                    fontFamily = if (span.code) FontFamily.Monospace else null,
                    background = if (span.code) CccColors.SurfaceHigh else androidx.compose.ui.graphics.Color.Unspecified,
                    fontSize = if (span.code) 13.sp else androidx.compose.ui.unit.TextUnit.Unspecified,
                )
                val link = span.link
                if (link != null) withLink(LinkAnnotation.Url(link, linkStyle)) { withStyle(style) { append(span.text) } }
                else withStyle(style) { append(span.text) }
            }
        }
    }
}

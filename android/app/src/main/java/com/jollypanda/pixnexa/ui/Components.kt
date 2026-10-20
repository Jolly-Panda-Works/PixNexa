package com.jollypanda.pixnexa.ui

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.text.format.Formatter
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.material3.Icon
import com.jollypanda.pixnexa.OutputFile
import com.jollypanda.pixnexa.R

const val WEBSITE = "https://usef-farahmand.github.io/image-format-converter/"

/** The launcher icon artwork, drawn with Compose (adaptive mipmaps cannot be painted directly). */
@Composable
fun AppLogo(size: Dp, modifier: Modifier = Modifier) {
    Box(
        modifier
            .size(size)
            .clip(RoundedCornerShape(size * 0.28f))
            .background(Brush.verticalGradient(listOf(OrangeLight, OrangeDark))),
    ) {
        Image(
            painter = painterResource(R.drawable.ic_launcher_foreground),
            contentDescription = null,
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer(scaleX = 1.45f, scaleY = 1.45f),
        )
    }
}

/** A row of segmented buttons for picking one of a few values; labels are string resources. */
@Composable
fun <T> ChoiceRow(
    options: List<Triple<T, Int, ImageVector?>>,
    selected: T,
    onSelect: (T) -> Unit,
    enabled: Boolean = true,
) {
    LabelChoiceRow(
        options = options.map { (value, label, icon) -> Triple(value, stringResource(label), icon) },
        selected = selected,
        onSelect = onSelect,
        enabled = enabled,
    )
}

/** The same row with ready-made label texts. */
@Composable
fun <T> LabelChoiceRow(
    options: List<Triple<T, String, ImageVector?>>,
    selected: T,
    onSelect: (T) -> Unit,
    enabled: Boolean = true,
) {
    val colors = SegmentedButtonDefaults.colors(
        activeContainerColor = MaterialTheme.colorScheme.primary,
        activeContentColor = MaterialTheme.colorScheme.onPrimary,
        activeBorderColor = MaterialTheme.colorScheme.primary,
        inactiveContainerColor = Color.Transparent,
        inactiveBorderColor = MaterialTheme.colorScheme.outline,
    )
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        options.forEachIndexed { index, (value, label, icon) ->
            val isSelected = value == selected
            val inactiveIcon: (@Composable () -> Unit)? =
                if (icon == null) null else ({ Icon(icon, contentDescription = null, Modifier.size(18.dp)) })
            SegmentedButton(
                selected = isSelected,
                onClick = { onSelect(value) },
                shape = SegmentedButtonDefaults.itemShape(index, options.size),
                enabled = enabled,
                colors = colors,
                icon = {
                    SegmentedButtonDefaults.Icon(
                        active = isSelected,
                        inactiveContent = inactiveIcon,
                    )
                },
            ) {
                Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

fun formatSize(context: Context, bytes: Long): String =
    if (bytes < 0) "—" else Formatter.formatShortFileSize(context, bytes)

/** Shares finished files through the Android Share menu, with the narrowest MIME type that fits all of them. */
fun shareFiles(context: Context, outputs: List<OutputFile>) {
    if (outputs.isEmpty()) return
    val uris = outputs.map { it.shareUri }
    val intent = if (uris.size == 1) {
        Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM, uris[0])
    } else {
        Intent(Intent.ACTION_SEND_MULTIPLE).putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
    }
    intent.type = commonMimeType(outputs.map { it.mimeType })
    // ClipData carries the read grant to whichever app the user picks.
    intent.clipData = ClipData.newRawUri(null, uris[0]).apply { uris.drop(1).forEach { addItem(ClipData.Item(it)) } }
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    context.startActivity(Intent.createChooser(intent, null))
}

// One type when all files share it, "image/(any)" for mixed images, "(any)/(any)" for mixed kinds.
private fun commonMimeType(types: List<String>): String {
    val distinct = types.distinct()
    if (distinct.size == 1) return distinct[0]
    val topLevel = distinct.map { it.substringBefore('/') }.distinct()
    return if (topLevel.size == 1) "${topLevel[0]}/*" else "*/*"
}

fun openWebsite(context: Context) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(WEBSITE)))
    } catch (e: ActivityNotFoundException) {
        // No browser installed: nothing to open.
    }
}

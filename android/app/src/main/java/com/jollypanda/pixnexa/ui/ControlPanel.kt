package com.jollypanda.pixnexa.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.Compress
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material.icons.rounded.SwapHoriz
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.jollypanda.pixnexa.AudioBitrate
import com.jollypanda.pixnexa.ConvertViewModel
import com.jollypanda.pixnexa.Destination
import com.jollypanda.pixnexa.ImageTarget
import com.jollypanda.pixnexa.ItemStatus
import com.jollypanda.pixnexa.MaxEdge
import com.jollypanda.pixnexa.MediaKind
import com.jollypanda.pixnexa.Mode
import com.jollypanda.pixnexa.PageSize
import com.jollypanda.pixnexa.PdfDpi
import com.jollypanda.pixnexa.PdfTarget
import com.jollypanda.pixnexa.R
import com.jollypanda.pixnexa.VideoQuality
import com.jollypanda.pixnexa.VideoRes
import com.jollypanda.pixnexa.VideoTarget
import kotlin.math.roundToInt

/**
 * The bottom panel: Convert / Compress, then one compact block per file category in the list
 * (only the formats and options that fit), where to save, and the start / progress row.
 */
@Composable
fun ControlPanel(vm: ConvertViewModel, onPickFolder: () -> Unit, onStart: () -> Unit) {
    val context = LocalContext.current
    val maxOptionsHeight = (LocalConfiguration.current.screenHeightDp * 0.45f).dp
    val enabled = !vm.running
    Surface(
        color = MaterialTheme.colorScheme.surfaceContainer,
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        shadowElevation = 8.dp,
    ) {
        Column(
            Modifier
                .navigationBarsPadding()
                .padding(horizontal = 16.dp, vertical = 14.dp),
        ) {
            Column(
                Modifier
                    .heightIn(max = maxOptionsHeight)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ChoiceRow(
                    options = listOf(
                        Triple(Mode.CONVERT, R.string.mode_convert, Icons.Rounded.SwapHoriz),
                        Triple(Mode.COMPRESS, R.string.mode_compress, Icons.Rounded.Compress),
                    ),
                    selected = vm.mode,
                    onSelect = vm::updateMode,
                    enabled = enabled,
                )

                for (kind in vm.kinds) {
                    HorizontalDivider(Modifier.padding(top = 4.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    KindHeader(kind, vm.count(kind))
                    when (kind) {
                        MediaKind.IMAGE -> ImageOptions(vm, enabled)
                        MediaKind.VIDEO -> VideoOptions(vm, enabled)
                        MediaKind.AUDIO -> AudioOptions(vm, enabled)
                        MediaKind.PDF -> PdfOptions(vm, enabled)
                    }
                }

                HorizontalDivider(Modifier.padding(top = 4.dp), color = MaterialTheme.colorScheme.outlineVariant)
                SectionLabel(stringResource(R.string.save_to))
                val folders = vm.galleryFolders()
                val onlyPictures = folders.all { it.startsWith("Pictures") }
                ChoiceRow(
                    options = listOf(
                        Triple(Destination.GALLERY, if (onlyPictures) R.string.dest_gallery else R.string.dest_media, Icons.Rounded.PhotoLibrary),
                        Triple(Destination.FOLDER, R.string.dest_folder, Icons.Rounded.Folder),
                    ),
                    selected = vm.destination,
                    onSelect = { if (it == Destination.FOLDER && vm.folder == null) onPickFolder() else vm.updateDestination(it) },
                    enabled = enabled,
                )
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.heightIn(min = 40.dp)) {
                    val gallery = vm.destination == Destination.GALLERY
                    Text(
                        if (gallery) folders.joinToString(" · ")
                        else vm.folderName ?: stringResource(R.string.choose_folder),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    if (!gallery) {
                        TextButton(onClick = onPickFolder, enabled = enabled) {
                            Text(stringResource(if (vm.folder == null) R.string.choose_folder else R.string.change_folder))
                        }
                    }
                }
            }

            Spacer(Modifier.height(8.dp))
            val compress = vm.mode == Mode.COMPRESS
            if (vm.running) {
                val total = vm.items.size.coerceAtLeast(1)
                val partial = vm.items.sumOf { item ->
                    val p = (item.status as? ItemStatus.Working)?.progress ?: 0f
                    if (p > 0f) p.toDouble() else 0.0
                }
                LinearProgressIndicator(
                    progress = { ((vm.processedCount + partial) / total).toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        stringResource(
                            if (compress) R.string.compressing else R.string.converting,
                            (vm.processedCount + 1).coerceAtMost(total),
                            total,
                        ),
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedButton(onClick = vm::stop) { Text(stringResource(R.string.cancel)) }
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val outputs = vm.allOutputs
                    if (outputs.isNotEmpty()) {
                        FilledTonalButton(
                            onClick = { shareFiles(context, outputs) },
                            modifier = Modifier.height(52.dp),
                        ) {
                            Icon(Icons.Rounded.Share, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text(stringResource(R.string.share_all))
                        }
                    }
                    Button(
                        onClick = onStart,
                        enabled = vm.items.isNotEmpty(),
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                    ) {
                        Icon(if (compress) Icons.Rounded.Compress else Icons.Rounded.AutoAwesome, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            stringResource(if (compress) R.string.compress else R.string.convert, vm.items.size),
                            style = MaterialTheme.typography.titleSmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun KindHeader(kind: MediaKind, count: Int) {
    val label = when (kind) {
        MediaKind.IMAGE -> R.string.kind_images_count
        MediaKind.VIDEO -> R.string.kind_videos_count
        MediaKind.AUDIO -> R.string.kind_audio_count
        MediaKind.PDF -> R.string.kind_pdfs_count
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(kindIcon(kind), contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(6.dp))
        Text(
            stringResource(label, count),
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun ImageOptions(vm: ConvertViewModel, enabled: Boolean) {
    val convert = vm.mode == Mode.CONVERT
    val target = vm.imageTarget
    if (convert) {
        ChoiceRow(
            options = listOf(
                Triple(ImageTarget.JPEG, R.string.format_jpeg, null),
                Triple(ImageTarget.PNG, R.string.format_png, null),
                Triple(ImageTarget.WEBP, R.string.format_webp, null),
                Triple(ImageTarget.PDF, R.string.format_pdf, null),
            ),
            selected = target,
            onSelect = vm::updateImageTarget,
            enabled = enabled,
        )
        if (target == ImageTarget.PDF) {
            Hint(stringResource(R.string.images_to_pdf_hint, vm.count(MediaKind.IMAGE)), important = true)
            SectionLabel(stringResource(R.string.page_size))
            ChoiceRow(
                options = listOf(
                    Triple(PageSize.FIT, R.string.page_fit, null),
                    Triple(PageSize.A4, R.string.page_a4, null),
                ),
                selected = vm.pageSize,
                onSelect = vm::updatePageSize,
                enabled = enabled,
            )
        }
    } else {
        Hint(stringResource(R.string.compress_image_hint))
    }

    val lossy = !convert || target != ImageTarget.PNG
    if (lossy) {
        QualitySlider(vm.quality, vm::updateQuality, vm::saveQuality, enabled)
    } else {
        Hint(stringResource(R.string.quality_lossless))
    }

    SectionLabel(stringResource(R.string.resize_label))
    ChoiceRow(
        options = listOf(
            Triple(MaxEdge.ORIGINAL, R.string.size_original, null),
            Triple(MaxEdge.UHD, R.string.size_4k, null),
            Triple(MaxEdge.FHD, R.string.size_1080, null),
            Triple(MaxEdge.HD, R.string.size_720, null),
        ),
        selected = vm.maxEdge,
        onSelect = vm::updateMaxEdge,
        enabled = enabled,
    )

    // Target size works by lowering the JPEG/WebP quality, so it is offered only where that applies.
    if (!convert || target == ImageTarget.JPEG || target == ImageTarget.WEBP) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                SectionLabel(stringResource(R.string.target_size))
                Text(
                    stringResource(R.string.target_size_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.width(12.dp))
            OutlinedTextField(
                value = if (vm.targetKb > 0) vm.targetKb.toString() else "",
                onValueChange = vm::updateTargetKb,
                enabled = enabled,
                singleLine = true,
                placeholder = { Text(stringResource(R.string.target_off)) },
                suffix = { Text(stringResource(R.string.unit_kb)) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.width(132.dp),
            )
        }
    }
}

@Composable
private fun VideoOptions(vm: ConvertViewModel, enabled: Boolean) {
    if (vm.mode == Mode.CONVERT) {
        val targets = buildList<Triple<VideoTarget, Int, ImageVector?>> {
            add(Triple(VideoTarget.MP4_H264, R.string.video_h264, null))
            if (vm.hevcSupported) add(Triple(VideoTarget.MP4_HEVC, R.string.video_hevc, null))
            add(Triple(VideoTarget.M4A, R.string.video_audio_only, null))
        }
        ChoiceRow(options = targets, selected = vm.effectiveVideoTarget, onSelect = vm::updateVideoTarget, enabled = enabled)
        if (vm.effectiveVideoTarget == VideoTarget.M4A) {
            Hint(stringResource(R.string.video_extract_hint))
        } else {
            SectionLabel(stringResource(R.string.resolution))
            ChoiceRow(
                options = listOf(
                    Triple(VideoRes.ORIGINAL, R.string.size_original, null),
                    Triple(VideoRes.P1080, R.string.size_1080, null),
                    Triple(VideoRes.P720, R.string.size_720, null),
                    Triple(VideoRes.P480, R.string.size_480, null),
                ),
                selected = vm.videoRes,
                onSelect = vm::updateVideoRes,
                enabled = enabled,
            )
        }
    } else {
        Hint(stringResource(R.string.compress_video_hint))
        SectionLabel(stringResource(R.string.resolution))
        ChoiceRow(
            options = listOf(
                Triple(VideoRes.P1080, R.string.size_1080, null),
                Triple(VideoRes.P720, R.string.size_720, null),
                Triple(VideoRes.P480, R.string.size_480, null),
            ),
            selected = vm.compressRes,
            onSelect = vm::updateCompressRes,
            enabled = enabled,
        )
        SectionLabel(stringResource(R.string.video_quality))
        ChoiceRow(
            options = listOf(
                Triple(VideoQuality.HIGH, R.string.quality_high, null),
                Triple(VideoQuality.MEDIUM, R.string.quality_medium, null),
                Triple(VideoQuality.LOW, R.string.quality_small, null),
            ),
            selected = vm.videoQuality,
            onSelect = vm::updateVideoQuality,
            enabled = enabled,
        )
    }
}

@Composable
private fun AudioOptions(vm: ConvertViewModel, enabled: Boolean) {
    Hint(stringResource(R.string.audio_hint))
    SectionLabel(stringResource(R.string.audio_bitrate))
    ChoiceRow(
        options = listOf(
            Triple(AudioBitrate.K64, R.string.kbps_64, null),
            Triple(AudioBitrate.K96, R.string.kbps_96, null),
            Triple(AudioBitrate.K128, R.string.kbps_128, null),
            Triple(AudioBitrate.K192, R.string.kbps_192, null),
            Triple(AudioBitrate.K256, R.string.kbps_256, null),
        ),
        selected = vm.audioBitrate,
        onSelect = vm::updateAudioBitrate,
        enabled = enabled,
    )
}

@Composable
private fun PdfOptions(vm: ConvertViewModel, enabled: Boolean) {
    val convert = vm.mode == Mode.CONVERT
    if (convert) {
        ChoiceRow(
            options = listOf(
                Triple(PdfTarget.JPEG, R.string.format_jpeg, null),
                Triple(PdfTarget.PNG, R.string.format_png, null),
                Triple(PdfTarget.MERGE, R.string.pdf_merge, null),
            ),
            selected = vm.pdfTarget,
            onSelect = vm::updatePdfTarget,
            enabled = enabled,
        )
        if (vm.pdfTarget == PdfTarget.MERGE) {
            Hint(stringResource(R.string.pdf_merge_hint, vm.count(MediaKind.PDF)), important = true)
        } else {
            Hint(stringResource(R.string.pdf_pages_hint))
        }
    } else {
        Hint(stringResource(R.string.pdf_compress_hint), important = true)
    }

    SectionLabel(stringResource(R.string.pdf_dpi))
    ChoiceRow(
        options = listOf(
            Triple(PdfDpi.LOW, R.string.dpi_72, null),
            Triple(PdfDpi.MEDIUM, R.string.dpi_150, null),
            Triple(PdfDpi.HIGH, R.string.dpi_300, null),
        ),
        selected = vm.pdfDpi,
        onSelect = vm::updatePdfDpi,
        enabled = enabled,
    )
    if (!convert || vm.pdfTarget != PdfTarget.PNG) {
        QualitySlider(vm.pdfQuality, vm::updatePdfQuality, vm::savePdfQuality, enabled)
    }
}

@Composable
private fun QualitySlider(value: Int, onChange: (Int) -> Unit, onDone: () -> Unit, enabled: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        SectionLabel(stringResource(R.string.quality_label), Modifier.weight(1f))
        Text(
            stringResource(R.string.quality_value, value),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold,
        )
    }
    Slider(
        value = value.toFloat(),
        onValueChange = { onChange(it.roundToInt()) },
        onValueChangeFinished = onDone,
        valueRange = 1f..100f,
        enabled = enabled,
        modifier = Modifier.height(32.dp),
    )
}

/** A short explanation under an option; [important] ones (combined files, lost text) get an icon and the accent color. */
@Composable
private fun Hint(text: String, important: Boolean = false) {
    val color = if (important) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
    Row(verticalAlignment = Alignment.Top) {
        if (important) {
            Icon(
                Icons.Rounded.Info,
                contentDescription = null,
                tint = color,
                modifier = Modifier
                    .padding(top = 1.dp)
                    .size(16.dp),
            )
            Spacer(Modifier.width(6.dp))
        }
        Text(text, style = MaterialTheme.typography.bodySmall, color = color)
    }
}

@Composable
private fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier,
    )
}

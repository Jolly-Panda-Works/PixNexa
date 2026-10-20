package com.jollypanda.pixnexa.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.AddPhotoAlternate
import androidx.compose.material.icons.rounded.AttachFile
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.Movie
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.PictureAsPdf
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.os.ConfigurationCompat
import coil.compose.AsyncImage
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest
import com.jollypanda.pixnexa.CombinedResult
import com.jollypanda.pixnexa.ConvertViewModel
import com.jollypanda.pixnexa.Destination
import com.jollypanda.pixnexa.FileItem
import com.jollypanda.pixnexa.ItemStatus
import com.jollypanda.pixnexa.MediaKind
import com.jollypanda.pixnexa.Mode
import com.jollypanda.pixnexa.R
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

/** MIME types offered by the "Files" picker (the system document picker). */
private val DOCUMENT_TYPES = arrayOf("image/*", "video/*", "audio/*", "application/pdf")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(vm: ConvertViewModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var showSettings by rememberSaveable { mutableStateOf(false) }
    var showAddMenu by remember { mutableStateOf(false) }

    val mediaPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia()) {
        vm.addFiles(it)
    }
    val pickMedia: () -> Unit = {
        mediaPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageAndVideo))
    }
    val documentPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) {
        vm.addFiles(it)
    }
    val pickDocuments: () -> Unit = { documentPicker.launch(DOCUMENT_TYPES) }
    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) vm.updateFolder(uri)
    }
    val pickFolder: () -> Unit = { folderPicker.launch(null) }
    val storagePermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) vm.start()
        else scope.launch { snackbar.showSnackbar(context.getString(R.string.error_permission)) }
    }
    val convert: () -> Unit = {
        val legacyGallery = vm.destination == Destination.GALLERY && Build.VERSION.SDK_INT < Build.VERSION_CODES.Q
        when {
            !vm.canSave() -> pickFolder()
            legacyGallery && ContextCompat.checkSelfPermission(context, Manifest.permission.WRITE_EXTERNAL_STORAGE) !=
                PackageManager.PERMISSION_GRANTED -> storagePermission.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
            else -> vm.start()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AppLogo(32.dp)
                        Spacer(Modifier.width(10.dp))
                        Text(stringResource(R.string.app_name), fontWeight = FontWeight.Bold)
                    }
                },
                actions = {
                    if (vm.items.isNotEmpty() && !vm.running) {
                        IconButton(onClick = vm::clear) {
                            Icon(Icons.Rounded.DeleteSweep, contentDescription = stringResource(R.string.clear_all))
                        }
                    }
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Rounded.Settings, contentDescription = stringResource(R.string.settings))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        bottomBar = {
            if (vm.items.isNotEmpty()) ControlPanel(vm, onPickFolder = pickFolder, onStart = convert)
        },
        floatingActionButton = {
            if (vm.items.isNotEmpty() && !vm.running) {
                Box {
                    ExtendedFloatingActionButton(
                        onClick = { showAddMenu = true },
                        icon = { Icon(Icons.Rounded.Add, contentDescription = null) },
                        text = { Text(stringResource(R.string.add_more)) },
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                        contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                    DropdownMenu(expanded = showAddMenu, onDismissRequest = { showAddMenu = false }) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.select_media)) },
                            leadingIcon = { Icon(Icons.Rounded.AddPhotoAlternate, contentDescription = null) },
                            onClick = {
                                showAddMenu = false
                                pickMedia()
                            },
                        )
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.select_files)) },
                            leadingIcon = { Icon(Icons.Rounded.AttachFile, contentDescription = null) },
                            onClick = {
                                showAddMenu = false
                                pickDocuments()
                            },
                        )
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (vm.items.isEmpty()) {
            EmptyState(Modifier.padding(padding), onPickMedia = pickMedia, onPickFiles = pickDocuments)
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(
                    start = 16.dp,
                    end = 16.dp,
                    top = padding.calculateTopPadding() + 4.dp,
                    bottom = padding.calculateBottomPadding() + 88.dp,
                ),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (!vm.running && (vm.doneItems.isNotEmpty() || vm.combinedResults.isNotEmpty())) {
                    item(key = "summary") { SummaryCard(vm) }
                }
                items(vm.combinedResults, key = { "combined-" + it.name }) { result ->
                    CombinedCard(result, onShare = { shareFiles(context, listOf(result.output)) })
                }
                items(vm.items, key = { it.id }) { item ->
                    ItemRow(
                        item = item,
                        compress = vm.mode == Mode.COMPRESS,
                        enabled = !vm.running,
                        onRemove = { vm.remove(item) },
                        onShare = { (item.status as? ItemStatus.Done)?.let { shareFiles(context, it.outputs) } },
                    )
                }
            }
        }
    }

    if (showSettings) SettingsSheet(vm, onDismiss = { showSettings = false })
}

@Composable
private fun EmptyState(modifier: Modifier, onPickMedia: () -> Unit, onPickFiles: () -> Unit) {
    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 32.dp, vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        AppLogo(96.dp)
        Spacer(Modifier.height(24.dp))
        Text(
            stringResource(R.string.empty_title),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            stringResource(R.string.empty_body),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            listOf(
                Icons.Rounded.Image to R.string.kind_image,
                Icons.Rounded.Movie to R.string.kind_video,
                Icons.Rounded.MusicNote to R.string.kind_audio,
                Icons.Rounded.PictureAsPdf to R.string.kind_pdf,
            ).forEach { (icon, label) ->
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Text(stringResource(label), style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        Button(onClick = onPickMedia, modifier = Modifier.height(52.dp)) {
            Icon(Icons.Rounded.AddPhotoAlternate, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.select_media), style = MaterialTheme.typography.titleSmall)
        }
        Spacer(Modifier.height(10.dp))
        OutlinedButton(onClick = onPickFiles, modifier = Modifier.height(48.dp)) {
            Icon(Icons.Rounded.AttachFile, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.select_files))
        }
        Spacer(Modifier.height(16.dp))
        Row(
            Modifier
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surfaceContainerHigh)
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Rounded.CloudOff, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(6.dp))
            Text(stringResource(R.string.offline_badge), style = MaterialTheme.typography.labelMedium)
        }
    }
}

fun kindIcon(kind: MediaKind): ImageVector = when (kind) {
    MediaKind.IMAGE -> Icons.Rounded.Image
    MediaKind.VIDEO -> Icons.Rounded.Movie
    MediaKind.AUDIO -> Icons.Rounded.MusicNote
    MediaKind.PDF -> Icons.Rounded.PictureAsPdf
}

/** Thumbnail for images and videos (first frame), a type icon for audio and PDF. */
@Composable
private fun Thumbnail(item: FileItem) {
    val context = LocalContext.current
    Box(
        Modifier
            .size(56.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        when (item.kind) {
            MediaKind.IMAGE, MediaKind.VIDEO -> {
                val request = remember(item.uri, item.kind) {
                    ImageRequest.Builder(context)
                        .data(item.uri)
                        .size(192)
                        .apply { if (item.kind == MediaKind.VIDEO) decoderFactory(VideoFrameDecoder.Factory()) }
                        .crossfade(true)
                        .build()
                }
                AsyncImage(
                    model = request,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
                if (item.kind == MediaKind.VIDEO) {
                    Icon(
                        Icons.Rounded.PlayArrow,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier
                            .size(22.dp)
                            .clip(CircleShape)
                            .background(Color.Black.copy(alpha = 0.45f)),
                    )
                }
            }
            MediaKind.AUDIO, MediaKind.PDF -> Icon(
                kindIcon(item.kind),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(28.dp),
            )
        }
    }
}

@Composable
private fun ItemRow(item: FileItem, compress: Boolean, enabled: Boolean, onRemove: () -> Unit, onShare: () -> Unit) {
    val context = LocalContext.current
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Thumbnail(item)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    item.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(2.dp))
                when (val status = item.status) {
                    ItemStatus.Waiting -> Text(
                        formatSize(context, item.size),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    is ItemStatus.Working -> {
                        Text(
                            stringResource(if (compress) R.string.status_compressing else R.string.status_converting),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        val progressModifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 6.dp)
                        if (status.progress >= 0f) {
                            LinearProgressIndicator(progress = { status.progress.coerceIn(0f, 1f) }, modifier = progressModifier)
                        } else {
                            LinearProgressIndicator(modifier = progressModifier)
                        }
                    }
                    is ItemStatus.Done -> {
                        SizeChange(item.size, status.outputSize)
                        if (status.outputs.size > 1) {
                            Text(
                                stringResource(R.string.files_count, status.outputs.size),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    is ItemStatus.Combined -> Text(
                        stringResource(R.string.status_combined, status.resultName),
                        style = MaterialTheme.typography.bodySmall,
                        color = successColor,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    is ItemStatus.Failed -> Text(
                        stringResource(status.message),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            when (item.status) {
                is ItemStatus.Done -> IconButton(onClick = onShare) {
                    Icon(Icons.Rounded.Share, contentDescription = stringResource(R.string.share))
                }
                is ItemStatus.Working -> Spacer(Modifier.width(48.dp))
                else -> IconButton(onClick = onRemove, enabled = enabled) {
                    Icon(Icons.Rounded.Close, contentDescription = stringResource(R.string.remove))
                }
            }
        }
    }
}

/** A file made from several inputs (images → one PDF, or merged PDFs). */
@Composable
private fun CombinedCard(result: CombinedResult, onShare: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary),
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(56.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Rounded.PictureAsPdf, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    result.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(2.dp))
                SizeChange(result.inputSize, result.outputSize)
            }
            IconButton(onClick = onShare) {
                Icon(Icons.Rounded.Share, contentDescription = stringResource(R.string.share))
            }
        }
    }
}

/** "2.4 MB → 820 KB  −66%" (the arrow points the reading direction). */
@Composable
private fun SizeChange(before: Long, after: Long) {
    val context = LocalContext.current
    val arrow = if (LocalLayoutDirection.current == LayoutDirection.Rtl) "←" else "→"
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            "${formatSize(context, before)} $arrow ${formatSize(context, after)}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (before > 0) {
            val locale = ConfigurationCompat.getLocales(LocalConfiguration.current)[0] ?: java.util.Locale.getDefault()
            val percent = ((after - before) * 100.0 / before).roundToInt()
            val color = if (after <= before) successColor else MaterialTheme.colorScheme.error
            Spacer(Modifier.width(8.dp))
            Text(
                String.format(locale, "%+d%%", percent),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = color,
                modifier = Modifier
                    .clip(RoundedCornerShape(50))
                    .background(color.copy(alpha = 0.14f))
                    .padding(horizontal = 6.dp, vertical = 1.dp),
            )
        }
    }
}

@Composable
private fun SummaryCard(vm: ConvertViewModel) {
    val context = LocalContext.current
    val done = vm.doneItems
    val combined = vm.combinedResults
    val combinedInputs = vm.items.count { it.status is ItemStatus.Combined }
    val failed = vm.items.count { it.status is ItemStatus.Failed }
    val known = done.filter { it.size >= 0 }
    val before = known.sumOf { it.size } + combined.sumOf { it.inputSize }
    val after = known.sumOf { (it.status as ItemStatus.Done).outputSize } + combined.sumOf { it.outputSize }
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
        contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    stringResource(
                        R.string.summary,
                        done.size + combinedInputs,
                        formatSize(context, before),
                        formatSize(context, after),
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                if (failed > 0) {
                    Text(
                        stringResource(R.string.summary_failed, failed),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}

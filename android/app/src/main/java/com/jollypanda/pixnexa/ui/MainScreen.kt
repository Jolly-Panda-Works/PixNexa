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
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AddPhotoAlternate
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import coil.request.ImageRequest
import com.jollypanda.pixnexa.ConvertViewModel
import com.jollypanda.pixnexa.Destination
import com.jollypanda.pixnexa.ImageItem
import com.jollypanda.pixnexa.ItemStatus
import com.jollypanda.pixnexa.OutputFormat
import com.jollypanda.pixnexa.R
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(vm: ConvertViewModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var showSettings by rememberSaveable { mutableStateOf(false) }

    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia()) {
        vm.addImages(it)
    }
    val pickImages: () -> Unit = {
        imagePicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
    }
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
        bottomBar = { ControlPanel(vm, onPickFolder = pickFolder, onConvert = convert) },
        floatingActionButton = {
            if (vm.items.isNotEmpty() && !vm.running) {
                ExtendedFloatingActionButton(
                    onClick = pickImages,
                    icon = { Icon(Icons.Rounded.AddPhotoAlternate, contentDescription = null) },
                    text = { Text(stringResource(R.string.add_more)) },
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (vm.items.isEmpty()) {
            EmptyState(Modifier.padding(padding), onPick = pickImages)
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
                if (!vm.running && vm.doneItems.isNotEmpty()) {
                    item(key = "summary") { SummaryCard(vm) }
                }
                items(vm.items, key = { it.id }) { item ->
                    ItemRow(
                        item = item,
                        enabled = !vm.running,
                        onRemove = { vm.remove(item) },
                        onShare = { (item.status as? ItemStatus.Done)?.let { shareImages(context, listOf(it.shareUri)) } },
                    )
                }
            }
        }
    }

    if (showSettings) SettingsSheet(vm, onDismiss = { showSettings = false })
}

@Composable
private fun EmptyState(modifier: Modifier, onPick: () -> Unit) {
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
        Spacer(Modifier.height(24.dp))
        Button(onClick = onPick, modifier = Modifier.height(52.dp)) {
            Icon(Icons.Rounded.AddPhotoAlternate, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.select_images), style = MaterialTheme.typography.titleSmall)
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

@Composable
private fun ControlPanel(vm: ConvertViewModel, onPickFolder: () -> Unit, onConvert: () -> Unit) {
    val context = LocalContext.current
    Surface(
        color = MaterialTheme.colorScheme.surfaceContainer,
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        shadowElevation = 8.dp,
    ) {
        Column(
            Modifier
                .navigationBarsPadding()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SectionLabel(stringResource(R.string.format_label))
            ChoiceRow(
                options = OutputFormat.entries.map { Triple(it, formatLabel(it), null) },
                selected = vm.format,
                onSelect = vm::updateFormat,
                enabled = !vm.running,
            )

            if (vm.format.lossy) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    SectionLabel(stringResource(R.string.quality_label), Modifier.weight(1f))
                    Text(
                        stringResource(R.string.quality_value, vm.quality),
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Slider(
                    value = vm.quality.toFloat(),
                    onValueChange = { vm.updateQuality(it.roundToInt()) },
                    onValueChangeFinished = vm::saveQuality,
                    valueRange = 1f..100f,
                    enabled = !vm.running,
                    modifier = Modifier.height(32.dp),
                )
            } else {
                Text(
                    stringResource(R.string.quality_lossless),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 6.dp),
                )
            }

            SectionLabel(stringResource(R.string.save_to))
            ChoiceRow(
                options = listOf(
                    Triple(Destination.GALLERY, R.string.dest_gallery, Icons.Rounded.PhotoLibrary),
                    Triple(Destination.FOLDER, R.string.dest_folder, Icons.Rounded.Folder),
                ),
                selected = vm.destination,
                onSelect = { if (it == Destination.FOLDER && vm.folder == null) onPickFolder() else vm.updateDestination(it) },
                enabled = !vm.running,
            )
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.height(40.dp)) {
                val gallery = vm.destination == Destination.GALLERY
                Text(
                    if (gallery) stringResource(R.string.dest_gallery_hint)
                    else vm.folderName ?: stringResource(R.string.choose_folder),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                if (!gallery) {
                    TextButton(onClick = onPickFolder, enabled = !vm.running) {
                        Text(stringResource(if (vm.folder == null) R.string.choose_folder else R.string.change_folder))
                    }
                }
            }

            if (vm.running) {
                val total = vm.items.size.coerceAtLeast(1)
                LinearProgressIndicator(
                    progress = { vm.processedCount.toFloat() / total },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        stringResource(R.string.converting, (vm.processedCount + 1).coerceAtMost(total), total),
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedButton(onClick = vm::stop) { Text(stringResource(R.string.cancel)) }
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val done = vm.doneItems
                    if (done.isNotEmpty()) {
                        FilledTonalButton(
                            onClick = { shareImages(context, done.mapNotNull { (it.status as? ItemStatus.Done)?.shareUri }) },
                            modifier = Modifier.height(52.dp),
                        ) {
                            Icon(Icons.Rounded.Share, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text(stringResource(R.string.share_all))
                        }
                    }
                    Button(
                        onClick = onConvert,
                        enabled = vm.items.isNotEmpty(),
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                    ) {
                        Icon(Icons.Rounded.AutoAwesome, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.convert, vm.items.size), style = MaterialTheme.typography.titleSmall)
                    }
                }
            }
        }
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

/** ChoiceRow takes string resources; the format names themselves are not translated. */
private fun formatLabel(format: OutputFormat): Int = when (format) {
    OutputFormat.JPEG -> R.string.format_jpeg
    OutputFormat.PNG -> R.string.format_png
    OutputFormat.WEBP -> R.string.format_webp
}

@Composable
private fun ItemRow(item: ImageItem, enabled: Boolean, onRemove: () -> Unit, onShare: () -> Unit) {
    val context = LocalContext.current
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                model = ImageRequest.Builder(context).data(item.uri).size(192).crossfade(true).build(),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(56.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant),
            )
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
                    ItemStatus.Converting -> {
                        Text(
                            stringResource(R.string.status_converting),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        LinearProgressIndicator(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 6.dp),
                        )
                    }
                    is ItemStatus.Done -> SizeChange(item.size, status.outputSize)
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
                ItemStatus.Converting -> Spacer(Modifier.width(48.dp))
                else -> IconButton(onClick = onRemove, enabled = enabled) {
                    Icon(Icons.Rounded.Close, contentDescription = stringResource(R.string.remove))
                }
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
    val failed = vm.items.count { it.status is ItemStatus.Failed }
    val known = done.filter { it.size >= 0 }
    val before = known.sumOf { it.size }
    val after = known.sumOf { (it.status as ItemStatus.Done).outputSize }
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
                    stringResource(R.string.summary, done.size, formatSize(context, before), formatSize(context, after)),
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

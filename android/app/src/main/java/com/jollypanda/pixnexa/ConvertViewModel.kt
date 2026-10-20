package com.jollypanda.pixnexa

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class ConvertViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = Prefs(app)
    private var nextId = 0L
    private var job: Job? = null

    /** Converted files live here until the next batch, so they can be shared. */
    private val cacheDir = File(app.cacheDir, "converted")

    var items by mutableStateOf<List<ImageItem>>(emptyList())
        private set
    var format by mutableStateOf(prefs.format)
        private set
    var quality by mutableStateOf(prefs.quality)
        private set
    var destination by mutableStateOf(prefs.destination)
        private set
    var folder by mutableStateOf(prefs.folder)
        private set
    var folderName by mutableStateOf<String?>(null)
        private set
    var theme by mutableStateOf(prefs.theme)
        private set
    var running by mutableStateOf(false)
        private set

    init {
        refreshFolderName()
    }

    val doneItems: List<ImageItem> get() = items.filter { it.status is ItemStatus.Done }
    val processedCount: Int get() = items.count { it.status is ItemStatus.Done || it.status is ItemStatus.Failed }

    fun addImages(uris: List<Uri>) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            val known = items.map { it.uri }.toSet()
            val fresh = withContext(Dispatchers.IO) {
                uris.distinct().filter { it !in known }.map { uri ->
                    val (name, size) = describe(uri)
                    ImageItem(id = nextId++, uri = uri, name = name, size = size)
                }
            }
            items = items + fresh
        }
    }

    fun remove(item: ImageItem) {
        if (!running) items = items.filterNot { it.id == item.id }
    }

    fun clear() {
        if (!running) items = emptyList()
    }

    fun updateFormat(value: OutputFormat) {
        format = value
        prefs.format = value
    }

    fun updateQuality(value: Int) {
        quality = value
    }

    fun saveQuality() {
        prefs.quality = quality
    }

    fun updateDestination(value: Destination) {
        destination = value
        prefs.destination = value
    }

    fun updateFolder(uri: Uri) {
        val resolver = getApplication<Application>().contentResolver
        val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        try {
            folder?.takeIf { it != uri }?.let { resolver.releasePersistableUriPermission(it, flags) }
        } catch (ignored: SecurityException) {
        }
        try {
            resolver.takePersistableUriPermission(uri, flags)
        } catch (ignored: SecurityException) {
        }
        folder = uri
        prefs.folder = uri
        updateDestination(Destination.FOLDER)
        refreshFolderName()
    }

    fun updateTheme(value: ThemeMode) {
        theme = value
        prefs.theme = value
        Prefs.applyTheme(value)
    }

    /** True when there is somewhere to save to; otherwise the UI asks for a folder first. */
    fun canSave(): Boolean = destination == Destination.GALLERY || folder != null

    fun start() {
        if (running || items.isEmpty() || !canSave()) return
        val format = format
        val quality = quality
        val destination = destination
        val folder = folder
        val context = getApplication<Application>()

        running = true
        items = items.map { it.copy(status = ItemStatus.Waiting) }
        job = viewModelScope.launch {
            withContext(Dispatchers.IO) { cacheDir.deleteRecursively() }
            try {
                for (item in items.toList()) {
                    ensureActive()
                    setStatus(item.id, ItemStatus.Converting)
                    val status = withContext(Dispatchers.IO) {
                        val outName = item.name.substringBeforeLast('.').ifBlank { "image" } + "." + format.extension
                        // One sub-folder per item, so two "photo.jpg" from different albums do not collide.
                        val outFile = File(File(cacheDir, item.id.toString()), outName)
                        try {
                            ImageConverter.convert(context, item.uri, format, quality, outFile)
                            when (destination) {
                                Destination.GALLERY -> OutputSaver.saveToGallery(context, outFile, outName, format.mimeType)
                                Destination.FOLDER -> OutputSaver.saveToFolder(
                                    context, folder ?: throw ConvertException(R.string.error_folder),
                                    outFile, outName, format.mimeType,
                                )
                            }
                            val shareUri = FileProvider.getUriForFile(context, "${context.packageName}.files", outFile)
                            ItemStatus.Done(outFile.length(), shareUri)
                        } catch (e: ConvertException) {
                            ItemStatus.Failed(e.messageRes)
                        }
                    }
                    setStatus(item.id, status)
                }
            } finally {
                // Stopped half way: whatever did not finish goes back to "waiting".
                items = items.map { if (it.status is ItemStatus.Converting) it.copy(status = ItemStatus.Waiting) else it }
                running = false
            }
        }
    }

    fun stop() {
        job?.cancel()
    }

    private fun setStatus(id: Long, status: ItemStatus) {
        items = items.map { if (it.id == id) it.copy(status = status) else it }
    }

    private fun refreshFolderName() {
        val uri = folder ?: return
        viewModelScope.launch {
            folderName = withContext(Dispatchers.IO) {
                try {
                    DocumentFile.fromTreeUri(getApplication(), uri)?.name
                } catch (ignored: Exception) {
                    null
                }
            } ?: uri.lastPathSegment?.substringAfterLast(':')
        }
    }

    /** Display name and byte size of a content URI, as far as its provider tells. */
    private fun describe(uri: Uri): Pair<String, Long> {
        val resolver = getApplication<Application>().contentResolver
        var name: String? = null
        var size = -1L
        try {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val n = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val s = c.getColumnIndex(OpenableColumns.SIZE)
                    if (n >= 0 && !c.isNull(n)) name = c.getString(n)
                    if (s >= 0 && !c.isNull(s)) size = c.getLong(s)
                }
            }
        } catch (ignored: Exception) {
        }
        if (size < 0) {
            size = try {
                resolver.openAssetFileDescriptor(uri, "r")?.use { it.length } ?: -1L
            } catch (ignored: Exception) {
                -1L
            }
        }
        return (name ?: uri.lastPathSegment?.substringAfterLast('/') ?: "image") to size
    }
}

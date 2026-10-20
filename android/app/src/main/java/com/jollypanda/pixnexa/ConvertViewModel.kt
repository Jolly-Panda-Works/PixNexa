package com.jollypanda.pixnexa

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.max
import kotlin.math.min

class ConvertViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = Prefs(app)
    private var nextId = 0L
    private var job: Job? = null

    /** Converted files live here until the next batch, so they can be shared. */
    private val cacheDir = File(app.cacheDir, "converted")

    var items by mutableStateOf<List<FileItem>>(emptyList())
        private set

    /** Files made from several inputs (images → one PDF, PDFs → one PDF) in the last batch. */
    var combinedResults by mutableStateOf<List<CombinedResult>>(emptyList())
        private set

    var mode by mutableStateOf(prefs.mode)
        private set
    var imageTarget by mutableStateOf(prefs.imageTarget)
        private set
    var quality by mutableStateOf(prefs.quality)
        private set
    var maxEdge by mutableStateOf(prefs.maxEdge)
        private set
    var targetKb by mutableStateOf(prefs.targetKb)
        private set
    var pageSize by mutableStateOf(prefs.pageSize)
        private set
    var videoTarget by mutableStateOf(prefs.videoTarget)
        private set
    var videoRes by mutableStateOf(prefs.videoRes)
        private set
    var compressRes by mutableStateOf(prefs.compressRes)
        private set
    var videoQuality by mutableStateOf(prefs.videoQuality)
        private set
    var audioBitrate by mutableStateOf(prefs.audioBitrate)
        private set
    var pdfTarget by mutableStateOf(prefs.pdfTarget)
        private set
    var pdfDpi by mutableStateOf(prefs.pdfDpi)
        private set
    var pdfQuality by mutableStateOf(prefs.pdfQuality)
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

    /** Whether this phone can encode HEVC; checked once in the background. */
    var hevcSupported by mutableStateOf(false)
        private set

    init {
        refreshFolderName()
        viewModelScope.launch {
            hevcSupported = withContext(Dispatchers.Default) { MediaTranscoder.hevcSupported() }
        }
    }

    /** The categories in the list, in a fixed order, so the panel only shows options that apply. */
    val kinds: List<MediaKind> get() = MediaKind.entries.filter { kind -> items.any { it.kind == kind } }

    fun count(kind: MediaKind): Int = items.count { it.kind == kind }

    val doneItems: List<FileItem> get() = items.filter { it.status is ItemStatus.Done }

    val processedCount: Int
        get() = items.count {
            it.status is ItemStatus.Done || it.status is ItemStatus.Failed || it.status is ItemStatus.Combined
        }

    /** Every finished file of the last batch, for "Share all". */
    val allOutputs: List<OutputFile>
        get() = doneItems.flatMap { (it.status as ItemStatus.Done).outputs } + combinedResults.map { it.output }

    /** The video target that will really be used (HEVC falls back to H.264 when the phone cannot encode it). */
    val effectiveVideoTarget: VideoTarget
        get() = if (videoTarget == VideoTarget.MP4_HEVC && !hevcSupported) VideoTarget.MP4_H264 else videoTarget

    fun addFiles(uris: List<Uri>) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            val known = items.map { it.uri }.toSet()
            val fresh = withContext(Dispatchers.IO) {
                uris.distinct().filter { it !in known }.map { uri ->
                    val info = describe(uri)
                    FileItem(
                        id = nextId++,
                        uri = uri,
                        name = info.name,
                        size = info.size,
                        kind = Kinds.detect(info.mimeType, info.name),
                        mimeType = info.mimeType,
                    )
                }
            }
            items = items + fresh
        }
    }

    fun remove(item: FileItem) {
        if (!running) items = items.filterNot { it.id == item.id }
    }

    fun clear() {
        if (!running) {
            items = emptyList()
            combinedResults = emptyList()
        }
    }

    fun updateMode(value: Mode) {
        mode = value
        prefs.mode = value
    }

    fun updateImageTarget(value: ImageTarget) {
        imageTarget = value
        prefs.imageTarget = value
    }

    fun updateQuality(value: Int) {
        quality = value
    }

    fun saveQuality() {
        prefs.quality = quality
    }

    fun updateMaxEdge(value: MaxEdge) {
        maxEdge = value
        prefs.maxEdge = value
    }

    /** Takes the text of the "target size" field; anything that is not a positive number turns the target off. */
    fun updateTargetKb(text: String) {
        val digits = text.filter { it in '0'..'9' }.take(7)
        targetKb = digits.toIntOrNull() ?: 0
        prefs.targetKb = targetKb
    }

    fun updatePageSize(value: PageSize) {
        pageSize = value
        prefs.pageSize = value
    }

    fun updateVideoTarget(value: VideoTarget) {
        videoTarget = value
        prefs.videoTarget = value
    }

    fun updateVideoRes(value: VideoRes) {
        videoRes = value
        prefs.videoRes = value
    }

    fun updateCompressRes(value: VideoRes) {
        compressRes = value
        prefs.compressRes = value
    }

    fun updateVideoQuality(value: VideoQuality) {
        videoQuality = value
        prefs.videoQuality = value
    }

    fun updateAudioBitrate(value: AudioBitrate) {
        audioBitrate = value
        prefs.audioBitrate = value
    }

    fun updatePdfTarget(value: PdfTarget) {
        pdfTarget = value
        prefs.pdfTarget = value
    }

    fun updatePdfDpi(value: PdfDpi) {
        pdfDpi = value
        prefs.pdfDpi = value
    }

    fun updatePdfQuality(value: Int) {
        pdfQuality = value
    }

    fun savePdfQuality() {
        prefs.pdfQuality = pdfQuality
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

    /** The shared folders the current list and settings will write to, e.g. "Pictures/PixNexa". */
    fun galleryFolders(): List<String> = kinds.map { kind ->
        val mime = when (kind) {
            MediaKind.IMAGE -> if (mode == Mode.CONVERT && imageTarget == ImageTarget.PDF) PDF_MIME else "image/*"
            MediaKind.VIDEO -> if (mode == Mode.CONVERT && effectiveVideoTarget == VideoTarget.M4A) M4A_MIME else "video/*"
            MediaKind.AUDIO -> M4A_MIME
            MediaKind.PDF -> if (mode == Mode.CONVERT && pdfTarget != PdfTarget.MERGE) "image/*" else PDF_MIME
        }
        "${OutputSaver.directoryFor(mime)}/${OutputSaver.ALBUM}"
    }.distinct().ifEmpty { listOf("${Environment.DIRECTORY_PICTURES}/${OutputSaver.ALBUM}") }

    /** Everything the background work needs, read once when the batch starts. */
    private data class Settings(
        val mode: Mode,
        val imageTarget: ImageTarget,
        val quality: Int,
        val maxEdge: MaxEdge,
        val targetKb: Int,
        val pageSize: PageSize,
        val videoTarget: VideoTarget,
        val videoRes: VideoRes,
        val compressRes: VideoRes,
        val videoQuality: VideoQuality,
        val audioBitrate: AudioBitrate,
        val pdfTarget: PdfTarget,
        val pdfDpi: PdfDpi,
        val pdfQuality: Int,
        val destination: Destination,
        val folder: Uri?,
    ) {
        val imagesToOnePdf get() = mode == Mode.CONVERT && imageTarget == ImageTarget.PDF
        val mergePdfs get() = mode == Mode.CONVERT && pdfTarget == PdfTarget.MERGE
    }

    fun start() {
        if (running || items.isEmpty() || !canSave()) return
        val s = Settings(
            mode, imageTarget, quality, maxEdge, targetKb, pageSize, effectiveVideoTarget, videoRes, compressRes,
            videoQuality, audioBitrate, pdfTarget, pdfDpi, pdfQuality, destination, folder,
        )

        running = true
        items = items.map { it.copy(status = ItemStatus.Waiting) }
        combinedResults = emptyList()
        job = viewModelScope.launch {
            withContext(Dispatchers.IO) { cacheDir.deleteRecursively() }
            try {
                val batch = items.toList()
                for (item in batch) {
                    ensureActive()
                    if (item.kind == MediaKind.IMAGE && s.imagesToOnePdf) continue
                    if (item.kind == MediaKind.PDF && s.mergePdfs) continue
                    setStatus(item.id, ItemStatus.Working())
                    val status = try {
                        processOne(item, s)
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: ConvertException) {
                        ItemStatus.Failed(e.messageRes)
                    } catch (e: OutOfMemoryError) {
                        ItemStatus.Failed(R.string.error_memory)
                    } catch (e: Exception) {
                        ItemStatus.Failed(R.string.error_unknown)
                    }
                    setStatus(item.id, status)
                }
                if (s.imagesToOnePdf) imagesToPdf(batch.filter { it.kind == MediaKind.IMAGE }, s)
                if (s.mergePdfs) mergePdfs(batch.filter { it.kind == MediaKind.PDF }, s)
            } finally {
                // Stopped half way: whatever did not finish goes back to "waiting".
                items = items.map { if (it.status is ItemStatus.Working) it.copy(status = ItemStatus.Waiting) else it }
                running = false
            }
        }
    }

    fun stop() {
        job?.cancel()
    }

    /** Converts or compresses one file on its own. */
    private suspend fun processOne(item: FileItem, s: Settings): ItemStatus {
        val context = getApplication<Application>()
        val base = baseName(item)
        // One sub-folder per item, so two "photo.jpg" from different albums do not collide.
        val dir = File(cacheDir, item.id.toString())
        val onProgress: (Float) -> Unit = { p -> postProgress(item.id, p) }

        return when (item.kind) {
            MediaKind.IMAGE -> {
                val format = if (s.mode == Mode.COMPRESS) OutputFormat.sameAs(item.mimeType, item.name)
                else s.imageTarget.format ?: OutputFormat.JPEG
                val name = "$base.${format.extension}"
                val file = File(dir, name)
                withContext(Dispatchers.IO) {
                    ImageConverter.convert(
                        context, item.uri, format, s.quality, s.maxEdge.pixels, s.targetKb * 1024L, file,
                    )
                }
                finish(listOf(file to format.mimeType), s)
            }

            MediaKind.VIDEO -> {
                val request = when {
                    s.mode == Mode.COMPRESS -> MediaTranscoder.Request(
                        videoMimeType = MediaTranscoder.H264,
                        shortSide = s.compressRes.shortSide,
                        bitsPerPixel = s.videoQuality.bitsPerPixel,
                    )
                    s.videoTarget == VideoTarget.M4A -> MediaTranscoder.Request(videoMimeType = null)
                    s.videoTarget == VideoTarget.MP4_HEVC -> MediaTranscoder.Request(MediaTranscoder.HEVC, s.videoRes.shortSide)
                    else -> MediaTranscoder.Request(MediaTranscoder.H264, s.videoRes.shortSide)
                }
                val audioOnly = request.videoMimeType == null
                val file = File(dir, if (audioOnly) "$base.m4a" else "$base.mp4")
                MediaTranscoder.transcode(context, item.uri, request, file, onProgress)
                finish(listOf(file to if (audioOnly) M4A_MIME else MP4_MIME), s)
            }

            MediaKind.AUDIO -> {
                val file = File(dir, "$base.m4a")
                val request = MediaTranscoder.Request(videoMimeType = null, audioBitrate = s.audioBitrate.bitsPerSecond)
                MediaTranscoder.transcode(context, item.uri, request, file, onProgress)
                finish(listOf(file to M4A_MIME), s)
            }

            MediaKind.PDF -> if (s.mode == Mode.COMPRESS) {
                val file = File(dir, "$base.pdf")
                withContext(Dispatchers.IO) {
                    PdfTools.compress(context, item.uri, s.pdfDpi.dpi, s.pdfQuality, file, onProgress)
                }
                finish(listOf(file to PDF_MIME), s)
            } else {
                val format = if (s.pdfTarget == PdfTarget.PNG) OutputFormat.PNG else OutputFormat.JPEG
                val pages = withContext(Dispatchers.IO) {
                    PdfTools.toImages(context, item.uri, format, s.pdfDpi.dpi, s.pdfQuality, dir, base, onProgress)
                }
                finish(pages.map { it to format.mimeType }, s)
            }
        }
    }

    /** Saves the files to the chosen place and returns the "done" status with share links. */
    private suspend fun finish(files: List<Pair<File, String>>, s: Settings): ItemStatus.Done = withContext(Dispatchers.IO) {
        val outputs = files.map { (file, mime) -> save(file, mime, s) }
        ItemStatus.Done(files.sumOf { it.first.length() }, outputs)
    }

    private fun save(file: File, mimeType: String, s: Settings): OutputFile {
        val context = getApplication<Application>()
        when (s.destination) {
            Destination.GALLERY -> OutputSaver.saveToGallery(context, file, file.name, mimeType)
            Destination.FOLDER -> OutputSaver.saveToFolder(
                context, s.folder ?: throw ConvertException(R.string.error_folder), file, file.name, mimeType,
            )
        }
        val shareUri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
        return OutputFile(shareUri, mimeType)
    }

    /** All selected images become the pages of one PDF. Images that cannot be read are skipped. */
    private suspend fun imagesToPdf(images: List<FileItem>, s: Settings) {
        if (images.isEmpty()) return
        val context = getApplication<Application>()
        val name = "PixNexa-${timestamp()}.pdf"
        val file = File(File(cacheDir, "combined"), name)
        images.forEach { setStatus(it.id, ItemStatus.Working()) }
        val failures = HashMap<Long, Int>()
        val added = ArrayList<FileItem>()
        try {
            withContext(Dispatchers.IO) {
                file.parentFile?.mkdirs()
                val writer = JpegPdfWriter(file)
                var closed = false
                try {
                    for (item in images) {
                        ensureActive()
                        try {
                            val page = ImageConverter.jpegForPdf(context, item.uri, s.quality, s.maxEdge.pixels)
                            addImagePage(writer, page, s.pageSize)
                            added += item
                            postProgress(item.id, 1f)
                        } catch (e: ConvertException) {
                            failures[item.id] = e.messageRes
                        } catch (e: OutOfMemoryError) {
                            failures[item.id] = R.string.error_memory
                        }
                    }
                    closed = true
                    writer.close()
                } finally {
                    if (!closed) {
                        try {
                            writer.close()
                        } catch (ignored: IOException) {
                        }
                    }
                }
            }
            if (added.isEmpty()) {
                file.delete()
            } else {
                val output = withContext(Dispatchers.IO) { save(file, PDF_MIME, s) }
                combinedResults = combinedResults + CombinedResult(
                    name = name,
                    inputSize = added.filter { it.size >= 0 }.sumOf { it.size },
                    outputSize = file.length(),
                    output = output,
                )
            }
            images.forEach { item ->
                setStatus(item.id, failures[item.id]?.let { ItemStatus.Failed(it) } ?: ItemStatus.Combined(name))
            }
        } catch (e: CancellationException) {
            file.delete()
            throw e
        } catch (e: ConvertException) {
            file.delete()
            images.forEach { setStatus(it.id, ItemStatus.Failed(e.messageRes)) }
        } catch (e: IOException) {
            file.delete()
            images.forEach { setStatus(it.id, ItemStatus.Failed(R.string.error_save)) }
        }
    }

    /** Places one image on its page: the page is the image's shape (FIT) or A4 with a margin. */
    private fun addImagePage(writer: JpegPdfWriter, page: ImageConverter.JpegPage, pageSize: PageSize) {
        val w = page.width.toFloat()
        val h = page.height.toFloat()
        when (pageSize) {
            PageSize.FIT -> {
                val k = JpegPdfWriter.A4_HEIGHT / max(w, h)
                writer.addPage(page.bytes, page.width, page.height, w * k, h * k)
            }
            PageSize.A4 -> {
                val landscape = w > h
                val pw = if (landscape) JpegPdfWriter.A4_HEIGHT else JpegPdfWriter.A4_WIDTH
                val ph = if (landscape) JpegPdfWriter.A4_WIDTH else JpegPdfWriter.A4_HEIGHT
                val margin = 24f
                val k = min((pw - 2 * margin) / w, (ph - 2 * margin) / h)
                val dw = w * k
                val dh = h * k
                writer.addPage(page.bytes, page.width, page.height, pw, ph, (pw - dw) / 2, (ph - dh) / 2, dw, dh)
            }
        }
    }

    /** All selected PDFs become one PDF (pages are re-rendered as images). */
    private suspend fun mergePdfs(pdfs: List<FileItem>, s: Settings) {
        if (pdfs.isEmpty()) return
        val context = getApplication<Application>()
        val name = "PixNexa-merged-${timestamp()}.pdf"
        val file = File(File(cacheDir, "combined"), name)
        pdfs.forEach { setStatus(it.id, ItemStatus.Working()) }
        try {
            val failures = withContext(Dispatchers.IO) {
                PdfTools.merge(context, pdfs.map { it.uri }, s.pdfDpi.dpi, s.pdfQuality, file) { index, progress ->
                    postProgress(pdfs[index].id, progress)
                }
            }
            val output = withContext(Dispatchers.IO) { save(file, PDF_MIME, s) }
            val included = pdfs.filterIndexed { index, _ -> index !in failures }
            combinedResults = combinedResults + CombinedResult(
                name = name,
                inputSize = included.filter { it.size >= 0 }.sumOf { it.size },
                outputSize = file.length(),
                output = output,
            )
            pdfs.forEachIndexed { index, item ->
                setStatus(item.id, failures[index]?.let { ItemStatus.Failed(it) } ?: ItemStatus.Combined(name))
            }
        } catch (e: CancellationException) {
            file.delete()
            throw e
        } catch (e: ConvertException) {
            file.delete()
            pdfs.forEach { setStatus(it.id, ItemStatus.Failed(e.messageRes)) }
        }
    }

    private fun setStatus(id: Long, status: ItemStatus) {
        items = items.map { if (it.id == id) it.copy(status = status) else it }
    }

    /** Progress may come from a worker thread; the list is only changed on the main thread. */
    private fun postProgress(id: Long, progress: Float) {
        viewModelScope.launch {
            items = items.map {
                if (it.id == id && it.status is ItemStatus.Working) it.copy(status = ItemStatus.Working(progress)) else it
            }
        }
    }

    private fun baseName(item: FileItem): String {
        val fallback = when (item.kind) {
            MediaKind.IMAGE -> "image"
            MediaKind.VIDEO -> "video"
            MediaKind.AUDIO -> "audio"
            MediaKind.PDF -> "document"
        }
        // Keep names safe for every storage provider.
        return item.name.substringBeforeLast('.').replace(Regex("[\\\\/:*?\"<>|]"), "_").trim().ifBlank { fallback }
    }

    private fun timestamp(): String = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())

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

    private class Description(val name: String, val size: Long, val mimeType: String?)

    /** Display name, byte size and MIME type of a content URI, as far as its provider tells. */
    private fun describe(uri: Uri): Description {
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
        val mime = try {
            resolver.getType(uri)
        } catch (ignored: Exception) {
            null
        }
        return Description(name ?: uri.lastPathSegment?.substringAfterLast('/') ?: "file", size, mime)
    }

    companion object {
        const val PDF_MIME = "application/pdf"
        const val MP4_MIME = "video/mp4"
        const val M4A_MIME = "audio/mp4"
    }
}

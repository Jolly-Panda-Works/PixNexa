package com.jollypanda.pixnexa

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.ParcelFileDescriptor
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.io.File
import java.io.IOException
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * PDF work with the platform's PdfRenderer (Android 5+): pages to images, compression and merging.
 * Compressed and merged PDFs are rebuilt from page images, so their text is no longer selectable.
 */
object PdfTools {

    /** A rendered page never gets more pixels than this (about 160 MB), whatever the DPI. */
    private const val MAX_PAGE_PIXELS = 40_000_000.0

    /** Renders every page of [input] to [format] files in [outDir], named "<baseName>-<page>.<ext>". */
    suspend fun toImages(
        context: Context,
        input: Uri,
        format: OutputFormat,
        dpi: Int,
        quality: Int,
        outDir: File,
        baseName: String,
        onProgress: (Float) -> Unit,
    ): List<File> {
        outDir.mkdirs()
        val files = ArrayList<File>()
        try {
            withRenderer(context, input) { renderer ->
                val count = renderer.pageCount
                for (index in 0 until count) {
                    currentCoroutineContext().ensureActive()
                    val bitmap = renderPage(renderer, index, dpi)
                    try {
                        val file = File(outDir, "$baseName-${index + 1}.${format.extension}")
                        file.writeBytes(ImageConverter.encode(bitmap, format, quality))
                        files += file
                    } finally {
                        bitmap.recycle()
                    }
                    onProgress((index + 1f) / count)
                }
            }
        } catch (e: Throwable) {
            files.forEach { it.delete() }
            throw e
        }
        if (files.isEmpty()) throw ConvertException(R.string.error_pdf)
        return files
    }

    /** Rewrites [input] as [output] with every page stored as a JPEG at [dpi] and [quality]. */
    suspend fun compress(context: Context, input: Uri, dpi: Int, quality: Int, output: File, onProgress: (Float) -> Unit) {
        merge(context, listOf(input), dpi, quality, output) { _, progress -> onProgress(progress) }
    }

    /**
     * Writes the pages of all [inputs] into one PDF. Inputs that cannot be read are skipped and
     * reported through the returned map (index → error message); [onProgress] gets (input index, 0..1).
     */
    suspend fun merge(
        context: Context,
        inputs: List<Uri>,
        dpi: Int,
        quality: Int,
        output: File,
        onProgress: (Int, Float) -> Unit,
    ): Map<Int, Int> {
        output.parentFile?.mkdirs()
        val failures = HashMap<Int, Int>()
        val writer = JpegPdfWriter(output)
        try {
            inputs.forEachIndexed { inputIndex, uri ->
                try {
                    withRenderer(context, uri) { renderer ->
                        val count = renderer.pageCount
                        for (index in 0 until count) {
                            currentCoroutineContext().ensureActive()
                            renderer.openPage(index).use { page ->
                                val bitmap = render(page, dpi)
                                try {
                                    val jpeg = ImageConverter.encodeJpeg(bitmap, quality)
                                    // Keep the page size of the original (in points).
                                    writer.addPage(jpeg, bitmap.width, bitmap.height, page.width.toFloat(), page.height.toFloat())
                                } finally {
                                    bitmap.recycle()
                                }
                            }
                            onProgress(inputIndex, (index + 1f) / count)
                        }
                    }
                } catch (e: ConvertException) {
                    if (inputs.size == 1) throw e
                    failures[inputIndex] = e.messageRes
                }
            }
            if (writer.pageCount == 0) throw ConvertException(R.string.error_pdf)
        } catch (e: Throwable) {
            try {
                writer.close()
            } catch (ignored: IOException) {
            }
            output.delete()
            throw e
        }
        try {
            writer.close()
        } catch (e: IOException) {
            output.delete()
            throw ConvertException(R.string.error_save, e)
        }
        return failures
    }

    /** Opens [uri] with PdfRenderer. Errors become [ConvertException]s; cancellation passes through. */
    private suspend fun <T> withRenderer(context: Context, uri: Uri, block: suspend (PdfRenderer) -> T): T {
        var temp: File? = null
        val renderer = try {
            try {
                open(context.contentResolver.openFileDescriptor(uri, "r") ?: throw IOException("no descriptor"))
            } catch (e: IOException) {
                // Some providers hand out pipes, which PdfRenderer cannot seek: copy to the cache first.
                val copy = File(context.cacheDir, "pdf-input-${System.nanoTime()}.pdf")
                temp = copy
                context.contentResolver.openInputStream(uri)?.use { input -> copy.outputStream().use { input.copyTo(it) } }
                    ?: throw IOException("cannot open")
                open(ParcelFileDescriptor.open(copy, ParcelFileDescriptor.MODE_READ_ONLY))
            }
        } catch (e: SecurityException) {
            temp?.delete()
            // PdfRenderer throws SecurityException for password-protected files.
            throw ConvertException(R.string.error_pdf_protected, e)
        } catch (e: OutOfMemoryError) {
            temp?.delete()
            throw ConvertException(R.string.error_memory, e)
        } catch (e: Exception) {
            temp?.delete()
            throw ConvertException(R.string.error_pdf, e)
        }
        try {
            return block(renderer)
        } catch (e: CancellationException) {
            // CancellationException is an IllegalStateException: let it through untouched.
            throw e
        } catch (e: OutOfMemoryError) {
            throw ConvertException(R.string.error_memory, e)
        } catch (e: IOException) {
            throw ConvertException(R.string.error_save, e)
        } catch (e: IllegalStateException) {
            throw ConvertException(R.string.error_pdf, e)
        } finally {
            renderer.close()
            temp?.delete()
        }
    }

    private fun open(descriptor: ParcelFileDescriptor): PdfRenderer = try {
        PdfRenderer(descriptor)
    } catch (e: Throwable) {
        try {
            descriptor.close()
        } catch (ignored: IOException) {
        }
        throw e
    }

    private fun renderPage(renderer: PdfRenderer, index: Int, dpi: Int): Bitmap =
        renderer.openPage(index).use { render(it, dpi) }

    /** Renders [page] on a white background at [dpi] (pages are measured in points, 72 per inch). */
    private fun render(page: PdfRenderer.Page, dpi: Int): Bitmap {
        val pw = max(page.width, 1)
        val ph = max(page.height, 1)
        var scale = dpi / 72.0
        val pixels = pw * scale * ph * scale
        if (pixels > MAX_PAGE_PIXELS) scale *= sqrt(MAX_PAGE_PIXELS / pixels)
        val w = min((pw * scale).roundToInt(), 20_000).coerceAtLeast(1)
        val h = min((ph * scale).roundToInt(), 20_000).coerceAtLeast(1)
        val bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        bitmap.eraseColor(Color.WHITE)
        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
        return bitmap
    }
}

package com.jollypanda.pixnexa

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ImageDecoder
import android.graphics.Matrix
import android.net.Uri
import android.os.Build
import androidx.exifinterface.media.ExifInterface
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sqrt

/** Decodes any image Android can read and re-encodes it as PNG, JPEG or WebP. Runs fully offline. */
object ImageConverter {

    /** Larger images are scaled down to this many pixels (about 256 MB of memory) instead of crashing. */
    private const val MAX_PIXELS = 64_000_000L

    /**
     * Converts [input] to [format]. [maxEdge] > 0 limits the longest side in pixels.
     * [targetBytes] > 0 (JPEG/WebP only) searches for the highest quality up to [quality] that fits.
     */
    fun convert(
        context: Context,
        input: Uri,
        format: OutputFormat,
        quality: Int,
        maxEdge: Int,
        targetBytes: Long,
        output: File,
    ) {
        val bitmap = decodeForFormat(context, input, maxEdge, format)
        try {
            val bytes = if (format.lossy && targetBytes > 0) {
                encodeToTarget(bitmap, format, quality, targetBytes)
            } else {
                encode(bitmap, format, quality)
            }
            output.parentFile?.mkdirs()
            output.writeBytes(bytes)
        } catch (e: OutOfMemoryError) {
            output.delete()
            throw ConvertException(R.string.error_memory, e)
        } catch (e: IOException) {
            output.delete()
            throw ConvertException(R.string.error_save, e)
        } finally {
            bitmap.recycle()
        }
    }

    /** One JPEG ready for [JpegPdfWriter]: the encoded bytes and the pixel size. */
    class JpegPage(val bytes: ByteArray, val width: Int, val height: Int)

    /** Decodes [input] and encodes it as a JPEG (transparent areas become white) for a PDF page. */
    fun jpegForPdf(context: Context, input: Uri, quality: Int, maxEdge: Int): JpegPage {
        val bitmap = decodeForFormat(context, input, maxEdge, OutputFormat.JPEG)
        try {
            return JpegPage(encode(bitmap, OutputFormat.JPEG, quality), bitmap.width, bitmap.height)
        } catch (e: OutOfMemoryError) {
            throw ConvertException(R.string.error_memory, e)
        } finally {
            bitmap.recycle()
        }
    }

    /** Encodes a bitmap that has no transparency (for example a rendered PDF page) as a JPEG. */
    fun encodeJpeg(bitmap: Bitmap, quality: Int): ByteArray = encode(bitmap, OutputFormat.JPEG, quality)

    fun encode(bitmap: Bitmap, format: OutputFormat, quality: Int): ByteArray {
        val stream = ByteArrayOutputStream(max(64 * 1024, bitmap.byteCount / 8))
        if (!bitmap.compress(format.compressFormat, quality.coerceIn(1, 100), stream)) {
            throw IOException("compress() returned false")
        }
        return stream.toByteArray()
    }

    /**
     * Binary search on the quality for the best result that is at most [targetBytes].
     * When even the lowest quality is too big, the image is made smaller step by step.
     */
    private fun encodeToTarget(source: Bitmap, format: OutputFormat, maxQuality: Int, targetBytes: Long): ByteArray {
        val minQuality = 5
        var bitmap = source
        var smallest: ByteArray? = null
        try {
            repeat(6) {
                val top = encode(bitmap, format, maxQuality)
                if (top.size <= targetBytes) return top
                var lo = minQuality
                var hi = maxQuality - 1
                var best: ByteArray? = null
                while (lo <= hi) {
                    val mid = (lo + hi) / 2
                    val bytes = encode(bitmap, format, mid)
                    if (bytes.size <= targetBytes) {
                        best = bytes
                        lo = mid + 1
                    } else {
                        if (smallest == null || bytes.size < smallest!!.size) smallest = bytes
                        hi = mid - 1
                    }
                }
                if (best != null) return best
                // Still too big at the lowest quality: shrink to 75% and try again.
                val w = (bitmap.width * 0.75f).roundToInt()
                val h = (bitmap.height * 0.75f).roundToInt()
                if (w < 32 || h < 32) return smallest ?: top
                val scaled = Bitmap.createScaledBitmap(bitmap, w, h, true)
                if (bitmap !== source) bitmap.recycle()
                bitmap = scaled
            }
            return smallest ?: encode(bitmap, format, minQuality)
        } finally {
            if (bitmap !== source) bitmap.recycle()
        }
    }

    /** Decodes, limits the size and, for JPEG, paints transparent pixels white instead of black. */
    private fun decodeForFormat(context: Context, input: Uri, maxEdge: Int, format: OutputFormat): Bitmap {
        val decoded = try {
            decode(context, input, maxEdge)
        } catch (e: OutOfMemoryError) {
            throw ConvertException(R.string.error_memory, e)
        } catch (e: ConvertException) {
            throw e
        } catch (e: Exception) {
            throw ConvertException(R.string.error_decode, e)
        }
        if (format != OutputFormat.JPEG || !decoded.hasAlpha()) return decoded
        return try {
            flattenOnWhite(decoded)
        } catch (e: OutOfMemoryError) {
            throw ConvertException(R.string.error_memory, e)
        } finally {
            decoded.recycle()
        }
    }

    /** Scale factor (≤ 1) that keeps the image under [MAX_PIXELS] and its longest side under [maxEdge] (0 = no limit). */
    private fun scaleFor(width: Int, height: Int, maxEdge: Int): Double {
        var scale = 1.0
        val pixels = width.toLong() * height
        if (pixels > MAX_PIXELS) scale = sqrt(MAX_PIXELS.toDouble() / pixels)
        val longest = max(width, height)
        if (maxEdge in 1 until longest) scale = min(scale, maxEdge.toDouble() / longest)
        return scale
    }

    private fun decode(context: Context, uri: Uri, maxEdge: Int): Bitmap {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            // ImageDecoder also reads HEIF (Android 9+) and AVIF (Android 12+) and applies the EXIF orientation.
            val source = ImageDecoder.createSource(context.contentResolver, uri)
            return ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                val w = info.size.width
                val h = info.size.height
                val scale = scaleFor(w, h, maxEdge)
                if (scale < 1.0) {
                    decoder.setTargetSize((w * scale).roundToInt().coerceAtLeast(1), (h * scale).roundToInt().coerceAtLeast(1))
                }
            }
        }
        return decodeLegacy(context, uri, maxEdge)
    }

    private fun decodeLegacy(context: Context, uri: Uri, maxEdge: Int): Bitmap {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw IOException("not an image")

        // Power-of-two subsampling while the image stays at least twice the wanted size, then exact scaling.
        val scale = scaleFor(bounds.outWidth, bounds.outHeight, maxEdge)
        var sample = 1
        while (scale * sample * 2 <= 1.0) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        var bitmap = resolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, options) }
            ?: throw IOException("not an image")

        val wantW = (bounds.outWidth * scale).roundToInt().coerceAtLeast(1)
        val wantH = (bounds.outHeight * scale).roundToInt().coerceAtLeast(1)
        if (scale < 1.0 && (bitmap.width > wantW || bitmap.height > wantH)) {
            val scaled = Bitmap.createScaledBitmap(bitmap, wantW, wantH, true)
            if (scaled !== bitmap) bitmap.recycle()
            bitmap = scaled
        }

        val exif = try {
            resolver.openInputStream(uri)?.use { ExifInterface(it) }
        } catch (e: IOException) {
            null
        }
        val rotation = exif?.rotationDegrees ?: 0
        val flipped = exif?.isFlipped ?: false
        if (rotation == 0 && !flipped) return bitmap

        val matrix = Matrix().apply {
            if (flipped) postScale(-1f, 1f)
            postRotate(rotation.toFloat())
        }
        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        if (rotated !== bitmap) bitmap.recycle()
        return rotated
    }

    private fun flattenOnWhite(source: Bitmap): Bitmap {
        val out = Bitmap.createBitmap(source.width, source.height, Bitmap.Config.ARGB_8888)
        Canvas(out).apply {
            drawColor(Color.WHITE)
            drawBitmap(source, 0f, 0f, null)
        }
        return out
    }
}

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
import java.io.File
import java.io.IOException
import kotlin.math.sqrt

/** Decodes any image Android can read and re-encodes it as PNG, JPEG or WebP. Runs fully offline. */
object ImageConverter {

    /** Larger images are scaled down to this many pixels (about 256 MB of memory) instead of crashing. */
    private const val MAX_PIXELS = 64_000_000L

    fun convert(context: Context, input: Uri, format: OutputFormat, quality: Int, output: File) {
        val decoded = try {
            decode(context, input)
        } catch (e: OutOfMemoryError) {
            throw ConvertException(R.string.error_memory, e)
        } catch (e: Exception) {
            throw ConvertException(R.string.error_decode, e)
        }
        // JPEG has no transparency: paint transparent pixels white instead of black.
        val bitmap = if (format == OutputFormat.JPEG && decoded.hasAlpha()) flattenOnWhite(decoded) else decoded
        try {
            output.parentFile?.mkdirs()
            val ok = output.outputStream().use { bitmap.compress(format.compressFormat, quality.coerceIn(1, 100), it) }
            if (!ok) throw IOException("compress() returned false")
        } catch (e: OutOfMemoryError) {
            output.delete()
            throw ConvertException(R.string.error_memory, e)
        } catch (e: IOException) {
            output.delete()
            throw ConvertException(R.string.error_save, e)
        } finally {
            if (bitmap !== decoded) bitmap.recycle()
            decoded.recycle()
        }
    }

    private fun decode(context: Context, uri: Uri): Bitmap {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            // ImageDecoder also reads HEIF/AVIF and applies the EXIF orientation by itself.
            val source = ImageDecoder.createSource(context.contentResolver, uri)
            return ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                val w = info.size.width.toLong()
                val h = info.size.height.toLong()
                if (w * h > MAX_PIXELS) {
                    val scale = sqrt(MAX_PIXELS.toDouble() / (w * h))
                    decoder.setTargetSize((w * scale).toInt().coerceAtLeast(1), (h * scale).toInt().coerceAtLeast(1))
                }
            }
        }
        return decodeLegacy(context, uri)
    }

    private fun decodeLegacy(context: Context, uri: Uri): Bitmap {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw IOException("not an image")

        var sample = 1
        while (bounds.outWidth.toLong() * bounds.outHeight / (sample.toLong() * sample) > MAX_PIXELS) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val bitmap = resolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, options) }
            ?: throw IOException("not an image")

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

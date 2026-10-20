package com.jollypanda.pixnexa

import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import androidx.annotation.StringRes

/** What a picked file is. Decides which formats and options the bottom panel offers. */
enum class MediaKind { IMAGE, VIDEO, AUDIO, PDF }

/** Convert = change the format. Compress = keep the format and make the file smaller. */
enum class Mode { CONVERT, COMPRESS }

enum class OutputFormat(val extension: String, val mimeType: String, val lossy: Boolean) {
    JPEG("jpg", "image/jpeg", lossy = true),
    PNG("png", "image/png", lossy = false),
    WEBP("webp", "image/webp", lossy = true);

    @Suppress("DEPRECATION")
    val compressFormat: Bitmap.CompressFormat
        get() = when (this) {
            JPEG -> Bitmap.CompressFormat.JPEG
            PNG -> Bitmap.CompressFormat.PNG
            // Before Android 11 the plain WEBP format is lossy and honours the quality value.
            WEBP -> if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Bitmap.CompressFormat.WEBP_LOSSY
            else Bitmap.CompressFormat.WEBP
        }

    companion object {
        /** Compress mode keeps the format; formats Android cannot write (HEIC, AVIF, GIF, BMP...) become JPEG. */
        fun sameAs(mimeType: String?, name: String): OutputFormat {
            val mime = mimeType?.lowercase().orEmpty()
            val ext = name.substringAfterLast('.', "").lowercase()
            return when {
                mime == "image/png" || ext == "png" -> PNG
                mime == "image/webp" || ext == "webp" -> WEBP
                else -> JPEG
            }
        }
    }
}

/** Convert-mode targets for images. PDF combines every selected image into one file. */
enum class ImageTarget(val format: OutputFormat?) {
    JPEG(OutputFormat.JPEG),
    PNG(OutputFormat.PNG),
    WEBP(OutputFormat.WEBP),
    PDF(null),
}

/** Longest side of the output image in pixels; 0 keeps the original size. */
enum class MaxEdge(val pixels: Int) { ORIGINAL(0), UHD(3840), FHD(1920), HD(1280) }

/** Page size of a PDF made from images. */
enum class PageSize { FIT, A4 }

enum class VideoTarget { MP4_H264, MP4_HEVC, M4A }

/** Short side of the output video (1080 = 1080p); 0 keeps the original resolution. */
enum class VideoRes(val shortSide: Int) { ORIGINAL(0), P1080(1080), P720(720), P480(480) }

/** Bits per pixel and frame used to pick the video bitrate when compressing. */
enum class VideoQuality(val bitsPerPixel: Float) { HIGH(0.10f), MEDIUM(0.065f), LOW(0.04f) }

enum class AudioBitrate(val bitsPerSecond: Int) {
    K64(64_000), K96(96_000), K128(128_000), K192(192_000), K256(256_000)
}

/** Convert-mode targets for PDF files. MERGE combines every selected PDF into one file. */
enum class PdfTarget { JPEG, PNG, MERGE }

enum class PdfDpi(val dpi: Int) { LOW(72), MEDIUM(150), HIGH(300) }

enum class Destination { GALLERY, FOLDER }

enum class ThemeMode { SYSTEM, LIGHT, DARK }

/** One finished file in the cache, ready to share. */
data class OutputFile(val shareUri: Uri, val mimeType: String)

sealed interface ItemStatus {
    data object Waiting : ItemStatus

    /** [progress] is 0..1, or negative while it is not known. */
    data class Working(val progress: Float = -1f) : ItemStatus

    /** [outputSize] is the total of all [outputs] (a PDF turned into images has one output per page). */
    data class Done(val outputSize: Long, val outputs: List<OutputFile>) : ItemStatus

    /** The item went into a combined file (images → one PDF, PDFs → one PDF). */
    data class Combined(val resultName: String) : ItemStatus

    data class Failed(@StringRes val message: Int) : ItemStatus
}

data class FileItem(
    val id: Long,
    val uri: Uri,
    val name: String,
    /** Size of the original file in bytes, or -1 when the provider does not tell. */
    val size: Long,
    val kind: MediaKind,
    val mimeType: String?,
    val status: ItemStatus = ItemStatus.Waiting,
)

/** A file made from several inputs, shown as its own card above the list. */
data class CombinedResult(
    val name: String,
    val inputSize: Long,
    val outputSize: Long,
    val output: OutputFile,
)

/** Thrown by the converters and the saver with a message the UI can show. */
class ConvertException(@StringRes val messageRes: Int, cause: Throwable? = null) : Exception(cause)

object Kinds {
    private val imageExt = setOf(
        "jpg", "jpeg", "jfif", "png", "webp", "gif", "bmp", "heic", "heif", "avif", "ico", "dng", "wbmp",
    )
    private val videoExt = setOf("mp4", "m4v", "mov", "3gp", "3g2", "mkv", "webm", "ts", "avi", "mpg", "mpeg")
    private val audioExt = setOf("mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac", "amr", "3ga", "mka", "wma")

    /** Category of a file from its MIME type, or from its extension when the MIME type is missing or generic. */
    fun detect(mimeType: String?, name: String): MediaKind {
        val mime = mimeType?.lowercase().orEmpty()
        when {
            mime.startsWith("image/") -> return MediaKind.IMAGE
            mime.startsWith("video/") -> return MediaKind.VIDEO
            mime.startsWith("audio/") -> return MediaKind.AUDIO
            mime == "application/pdf" -> return MediaKind.PDF
        }
        return when (name.substringAfterLast('.', "").lowercase()) {
            in videoExt -> MediaKind.VIDEO
            in audioExt -> MediaKind.AUDIO
            "pdf" -> MediaKind.PDF
            in imageExt -> MediaKind.IMAGE
            else -> MediaKind.IMAGE
        }
    }
}

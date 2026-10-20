package com.jollypanda.pixnexa

import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import androidx.annotation.StringRes

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
}

enum class Destination { GALLERY, FOLDER }

enum class ThemeMode { SYSTEM, LIGHT, DARK }

sealed interface ItemStatus {
    data object Waiting : ItemStatus
    data object Converting : ItemStatus
    data class Done(val outputSize: Long, val shareUri: Uri) : ItemStatus
    data class Failed(@StringRes val message: Int) : ItemStatus
}

data class ImageItem(
    val id: Long,
    val uri: Uri,
    val name: String,
    /** Size of the original file in bytes, or -1 when the provider does not tell. */
    val size: Long,
    val status: ItemStatus = ItemStatus.Waiting,
)

/** Thrown by the converter and the saver with a message the UI can show. */
class ConvertException(@StringRes val messageRes: Int, cause: Throwable? = null) : Exception(cause)

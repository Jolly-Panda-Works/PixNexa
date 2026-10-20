package com.jollypanda.pixnexa

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.annotation.RequiresApi
import androidx.documentfile.provider.DocumentFile
import java.io.File

/**
 * Copies a finished file from the app cache to the shared storage collection that fits its type
 * (Pictures, Movies, Music or Download, each in a "PixNexa" folder) or to a folder the user picked.
 */
object OutputSaver {

    const val ALBUM = "PixNexa"

    /**
     * The MIME type Android itself links to this file name's extension, so MediaStore and the
     * documents provider do not append a second extension (for example "song.m4a.mp4").
     */
    fun platformMimeType(displayName: String, fallback: String): String {
        val ext = displayName.substringAfterLast('.', "").lowercase()
        val known = if (ext.isEmpty()) null else MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext)
        return if (known != null && known.substringBefore('/') == fallback.substringBefore('/')) known else fallback
    }

    /** Public folder for a MIME type, e.g. "Movies" for video/mp4. */
    fun directoryFor(mimeType: String): String = when {
        mimeType.startsWith("video/") -> Environment.DIRECTORY_MOVIES
        mimeType.startsWith("audio/") -> Environment.DIRECTORY_MUSIC
        mimeType.startsWith("image/") -> Environment.DIRECTORY_PICTURES
        else -> Environment.DIRECTORY_DOWNLOADS
    }

    fun saveToGallery(context: Context, file: File, displayName: String, mimeType: String): Uri = try {
        val mime = platformMimeType(displayName, mimeType)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) saveWithMediaStore(context, file, displayName, mime)
        else saveLegacy(context, file, displayName, mime)
    } catch (e: ConvertException) {
        throw e
    } catch (e: SecurityException) {
        throw ConvertException(R.string.error_permission, e)
    } catch (e: Exception) {
        throw ConvertException(R.string.error_save, e)
    }

    fun saveToFolder(context: Context, tree: Uri, file: File, displayName: String, mimeType: String): Uri {
        try {
            val folder = DocumentFile.fromTreeUri(context, tree) ?: throw ConvertException(R.string.error_folder)
            // The documents provider adds " (1)" when the name is taken, so nothing is overwritten.
            val target = folder.createFile(platformMimeType(displayName, mimeType), displayName)
                ?: throw ConvertException(R.string.error_save)
            val out = context.contentResolver.openOutputStream(target.uri) ?: throw ConvertException(R.string.error_save)
            out.use { stream -> file.inputStream().use { it.copyTo(stream) } }
            return target.uri
        } catch (e: ConvertException) {
            throw e
        } catch (e: SecurityException) {
            throw ConvertException(R.string.error_folder, e)
        } catch (e: Exception) {
            throw ConvertException(R.string.error_save, e)
        }
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun collectionFor(mimeType: String): Uri = when {
        mimeType.startsWith("video/") -> MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        mimeType.startsWith("audio/") -> MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        mimeType.startsWith("image/") -> MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        else -> MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun saveWithMediaStore(context: Context, file: File, displayName: String, mimeType: String): Uri {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, displayName)
            put(MediaStore.MediaColumns.MIME_TYPE, mimeType)
            put(MediaStore.MediaColumns.RELATIVE_PATH, "${directoryFor(mimeType)}/$ALBUM")
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri = resolver.insert(collectionFor(mimeType), values) ?: throw ConvertException(R.string.error_save)
        try {
            val out = resolver.openOutputStream(uri) ?: throw ConvertException(R.string.error_save)
            out.use { stream -> file.inputStream().use { it.copyTo(stream) } }
            resolver.update(uri, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
            return uri
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            throw e
        }
    }

    @Suppress("DEPRECATION")
    private fun saveLegacy(context: Context, file: File, displayName: String, mimeType: String): Uri {
        val dir = File(Environment.getExternalStoragePublicDirectory(directoryFor(mimeType)), ALBUM)
        if (!dir.isDirectory && !dir.mkdirs()) throw ConvertException(R.string.error_save)
        val target = uniqueFile(dir, displayName)
        file.copyTo(target)
        MediaScannerConnection.scanFile(context, arrayOf(target.absolutePath), arrayOf(mimeType), null)
        return Uri.fromFile(target)
    }

    /** photo.png, photo (1).png, photo (2).png ... */
    private fun uniqueFile(dir: File, name: String): File {
        val base = name.substringBeforeLast('.')
        val ext = name.substringAfterLast('.', "")
        var candidate = File(dir, name)
        var n = 1
        while (candidate.exists()) {
            candidate = File(dir, if (ext.isEmpty()) "$base ($n)" else "$base ($n).$ext")
            n++
        }
        return candidate
    }
}

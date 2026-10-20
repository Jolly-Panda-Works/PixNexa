package com.jollypanda.pixnexa

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.documentfile.provider.DocumentFile
import java.io.File

/** Copies a converted file from the app cache to the gallery or to a folder the user picked. */
object OutputSaver {

    const val GALLERY_ALBUM = "PixNexa"

    fun saveToGallery(context: Context, file: File, displayName: String, mimeType: String): Uri = try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) saveWithMediaStore(context, file, displayName, mimeType)
        else saveLegacy(context, file, displayName, mimeType)
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
            val target = folder.createFile(mimeType, displayName) ?: throw ConvertException(R.string.error_save)
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

    @androidx.annotation.RequiresApi(Build.VERSION_CODES.Q)
    private fun saveWithMediaStore(context: Context, file: File, displayName: String, mimeType: String): Uri {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, displayName)
            put(MediaStore.Images.Media.MIME_TYPE, mimeType)
            put(MediaStore.Images.Media.RELATIVE_PATH, "${Environment.DIRECTORY_PICTURES}/$GALLERY_ALBUM")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val uri = resolver.insert(collection, values) ?: throw ConvertException(R.string.error_save)
        try {
            val out = resolver.openOutputStream(uri) ?: throw ConvertException(R.string.error_save)
            out.use { stream -> file.inputStream().use { it.copyTo(stream) } }
            resolver.update(uri, ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }, null, null)
            return uri
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            throw e
        }
    }

    @Suppress("DEPRECATION")
    private fun saveLegacy(context: Context, file: File, displayName: String, mimeType: String): Uri {
        val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), GALLERY_ALBUM)
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

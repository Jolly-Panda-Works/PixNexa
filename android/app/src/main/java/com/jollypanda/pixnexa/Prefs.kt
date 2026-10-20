package com.jollypanda.pixnexa

import android.content.Context
import android.net.Uri
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.content.edit

/** The user's last choices, kept on the device only. */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var mode: Mode
        get() = enumOr(sp.getString("mode", null), Mode.CONVERT)
        set(value) = sp.edit { putString("mode", value.name) }

    /** Version 1 stored "format" (JPEG/PNG/WEBP); those names are also ImageTarget names. */
    var imageTarget: ImageTarget
        get() = enumOr(sp.getString("image_target", null) ?: sp.getString("format", null), ImageTarget.WEBP)
        set(value) = sp.edit { putString("image_target", value.name) }

    var quality: Int
        get() = sp.getInt("quality", 85)
        set(value) = sp.edit { putInt("quality", value) }

    var maxEdge: MaxEdge
        get() = enumOr(sp.getString("max_edge", null), MaxEdge.ORIGINAL)
        set(value) = sp.edit { putString("max_edge", value.name) }

    /** 0 = no target size. */
    var targetKb: Int
        get() = sp.getInt("target_kb", 0)
        set(value) = sp.edit { putInt("target_kb", value) }

    var pageSize: PageSize
        get() = enumOr(sp.getString("page_size", null), PageSize.FIT)
        set(value) = sp.edit { putString("page_size", value.name) }

    var videoTarget: VideoTarget
        get() = enumOr(sp.getString("video_target", null), VideoTarget.MP4_H264)
        set(value) = sp.edit { putString("video_target", value.name) }

    var videoRes: VideoRes
        get() = enumOr(sp.getString("video_res", null), VideoRes.ORIGINAL)
        set(value) = sp.edit { putString("video_res", value.name) }

    /** Compress mode never keeps the original resolution, so it has its own setting. */
    var compressRes: VideoRes
        get() = enumOr(sp.getString("compress_res", null), VideoRes.P720).takeIf { it != VideoRes.ORIGINAL } ?: VideoRes.P720
        set(value) = sp.edit { putString("compress_res", value.name) }

    var videoQuality: VideoQuality
        get() = enumOr(sp.getString("video_quality", null), VideoQuality.MEDIUM)
        set(value) = sp.edit { putString("video_quality", value.name) }

    var audioBitrate: AudioBitrate
        get() = enumOr(sp.getString("audio_bitrate", null), AudioBitrate.K128)
        set(value) = sp.edit { putString("audio_bitrate", value.name) }

    var pdfTarget: PdfTarget
        get() = enumOr(sp.getString("pdf_target", null), PdfTarget.JPEG)
        set(value) = sp.edit { putString("pdf_target", value.name) }

    var pdfDpi: PdfDpi
        get() = enumOr(sp.getString("pdf_dpi", null), PdfDpi.MEDIUM)
        set(value) = sp.edit { putString("pdf_dpi", value.name) }

    var pdfQuality: Int
        get() = sp.getInt("pdf_quality", 70)
        set(value) = sp.edit { putInt("pdf_quality", value) }

    var destination: Destination
        get() = enumOr(sp.getString("destination", null), Destination.GALLERY)
        set(value) = sp.edit { putString("destination", value.name) }

    var folder: Uri?
        get() = sp.getString("folder", null)?.let(Uri::parse)
        set(value) = sp.edit { putString("folder", value?.toString()) }

    var theme: ThemeMode
        get() = enumOr(sp.getString("theme", null), ThemeMode.SYSTEM)
        set(value) = sp.edit { putString("theme", value.name) }

    private inline fun <reified T : Enum<T>> enumOr(name: String?, default: T): T =
        enumValues<T>().firstOrNull { it.name == name } ?: default

    companion object {
        fun applyTheme(mode: ThemeMode) {
            AppCompatDelegate.setDefaultNightMode(
                when (mode) {
                    ThemeMode.SYSTEM -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
                    ThemeMode.LIGHT -> AppCompatDelegate.MODE_NIGHT_NO
                    ThemeMode.DARK -> AppCompatDelegate.MODE_NIGHT_YES
                }
            )
        }
    }
}

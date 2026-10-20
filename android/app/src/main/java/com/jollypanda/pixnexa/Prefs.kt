package com.jollypanda.pixnexa

import android.content.Context
import android.net.Uri
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.content.edit

/** The user's last choices, kept on the device only. */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var format: OutputFormat
        get() = enumOr(sp.getString("format", null), OutputFormat.WEBP)
        set(value) = sp.edit { putString("format", value.name) }

    var quality: Int
        get() = sp.getInt("quality", 85)
        set(value) = sp.edit { putInt("quality", value) }

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

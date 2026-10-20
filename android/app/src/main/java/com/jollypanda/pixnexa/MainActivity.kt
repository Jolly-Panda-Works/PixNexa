package com.jollypanda.pixnexa

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.activity.compose.setContent
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.IntentCompat
import com.jollypanda.pixnexa.ui.MainScreen
import com.jollypanda.pixnexa.ui.PixNexaTheme

class MainActivity : AppCompatActivity() {

    private val viewModel: ConvertViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        Prefs.applyTheme(Prefs(this).theme)
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // Images shared to PixNexa ("Share → PixNexa"). Skipped after a rotation or language change.
        if (savedInstanceState == null) viewModel.addImages(sharedImages(intent))
        setContent {
            PixNexaTheme {
                MainScreen(viewModel)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        viewModel.addImages(sharedImages(intent))
    }

    private fun sharedImages(intent: Intent?): List<Uri> {
        intent ?: return emptyList()
        val uris = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
            Intent.ACTION_SEND_MULTIPLE ->
                IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java).orEmpty()
            Intent.ACTION_VIEW -> listOfNotNull(intent.data)
            else -> emptyList()
        }
        if (uris.isNotEmpty()) return uris
        val clip = intent.clipData ?: return emptyList()
        return (0 until clip.itemCount).mapNotNull { clip.getItemAt(it).uri }
    }
}

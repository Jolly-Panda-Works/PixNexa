package com.jollypanda.pixnexa.ui

import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.DarkMode
import androidx.compose.material.icons.rounded.LightMode
import androidx.compose.material.icons.rounded.PhoneAndroid
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.os.LocaleListCompat
import com.jollypanda.pixnexa.BuildConfig
import com.jollypanda.pixnexa.ConvertViewModel
import com.jollypanda.pixnexa.R
import com.jollypanda.pixnexa.ThemeMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsSheet(vm: ConvertViewModel, onDismiss: () -> Unit) {
    val context = LocalContext.current
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surfaceContainer,
    ) {
        Column(
            Modifier
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(stringResource(R.string.settings), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)

            Label(stringResource(R.string.theme))
            ChoiceRow(
                options = listOf(
                    Triple(ThemeMode.SYSTEM, R.string.theme_system, Icons.Rounded.PhoneAndroid),
                    Triple(ThemeMode.LIGHT, R.string.theme_light, Icons.Rounded.LightMode),
                    Triple(ThemeMode.DARK, R.string.theme_dark, Icons.Rounded.DarkMode),
                ),
                selected = vm.theme,
                onSelect = vm::updateTheme,
            )

            Label(stringResource(R.string.language))
            // "" = follow the phone's language. AppCompat stores the choice and recreates the screen.
            val language = AppCompatDelegate.getApplicationLocales().toLanguageTags().substringBefore('-').substringBefore(',')
            ChoiceRow(
                options = listOf(
                    Triple("", R.string.lang_system, null),
                    Triple("fa", R.string.lang_fa, null),
                    Triple("en", R.string.lang_en, null),
                ),
                selected = language,
                onSelect = { tag ->
                    AppCompatDelegate.setApplicationLocales(
                        if (tag.isEmpty()) LocaleListCompat.getEmptyLocaleList() else LocaleListCompat.forLanguageTags(tag)
                    )
                },
            )

            HorizontalDivider(Modifier.padding(vertical = 8.dp), color = MaterialTheme.colorScheme.outlineVariant)

            Label(stringResource(R.string.about))
            Row(verticalAlignment = Alignment.CenterVertically) {
                AppLogo(48.dp)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("PixNexa Mobile", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(
                        stringResource(R.string.version, BuildConfig.VERSION_NAME),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Text(stringResource(R.string.about_text), style = MaterialTheme.typography.bodyMedium)
            Row {
                Icon(
                    Icons.Rounded.CloudOff,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier
                        .padding(top = 2.dp)
                        .size(18.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    stringResource(R.string.privacy_text),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            OutlinedButton(onClick = { openWebsite(context) }) {
                Text(stringResource(R.string.website))
            }
        }
    }
}

@Composable
private fun Label(text: String) {
    Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

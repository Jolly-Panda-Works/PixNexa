# PixNexa Mobile (Android)

Android edition of PixNexa: package `com.jollypanda.pixnexa`, Kotlin + Jetpack Compose, Android 7.0 (API 24) and newer.

## Features (v1)

- Convert between **PNG, JPEG and WebP** (input: anything Android can decode, including HEIC on Android 9+)
- Pick **many images at once** (system photo picker) and convert them as a batch
- **Quality slider** for JPEG/WebP, with the file size **before → after** and the percentage for every image
- Save to the **gallery** (`Pictures/PixNexa`) or to **any folder** you choose; nothing is overwritten
- **Share** the results through the Android Share menu, and receive images from other apps ("Share → PixNexa")
- **Fully offline**: the app has no `INTERNET` permission
- **Dark / light / system theme**, **Persian (RTL) and English** UI

## Build

```
cd android
./gradlew assembleDebug        # app/build/outputs/apk/debug/
./gradlew assembleRelease      # app/build/outputs/apk/release/
```

Needs JDK 17+ and the Android SDK (platform 35). Version on CI: `versionName` = the shared PixNexa version (root `VERSION` file, `MAJOR.MINOR.<run number>`),
`versionCode` = 1000 + run number.

## GitHub Actions

The Android job of [`.github/workflows/build.yml`](../.github/workflows/build.yml) builds the APK and the App Bundle on every push.
On `main` they are published in the same GitHub Release as PixNexa Desktop (`vMAJOR.MINOR.N`), so the newest APK is always at
`https://github.com/Usef-Farahmand/image-format-converter/releases/latest/download/PixNexa.apk`.

## Release signing (do this once)

Android only installs an update when it is signed with the same key as the installed app. Without the secrets below,
CI signs with a throw-away debug key that changes on every run, so users would have to uninstall before each update.

1. Create a key (keep the file and passwords safe; losing them means you can never update the app again):

   ```
   keytool -genkeypair -v -keystore pixnexa-release.jks -alias pixnexa -keyalg RSA -keysize 4096 -validity 10000
   ```

2. In the repository go to **Settings → Secrets and variables → Actions** and add:

   | Secret | Value |
   | ------ | ----- |
   | `ANDROID_KEYSTORE_BASE64` | output of `base64 -w0 pixnexa-release.jks` |
   | `ANDROID_KEYSTORE_PASSWORD` | keystore password |
   | `ANDROID_KEY_ALIAS` | `pixnexa` |
   | `ANDROID_KEY_PASSWORD` | key password |

Never commit the `.jks` file (it is in `.gitignore`).

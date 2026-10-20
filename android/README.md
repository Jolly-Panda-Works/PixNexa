# PixNexa Mobile (Android)

Android edition of PixNexa: package `com.jollypanda.pixnexa`, Kotlin + Jetpack Compose, Android 7.0 (API 24) and newer.

## Features

PixNexa Mobile is an offline converter **and** compressor for images, video, audio and PDF
(ideas from the open-source [Filee](https://github.com/KnifeLemon/Filee) desktop converter).

- **Any file in**: the photo picker (photos and videos) or **Files** (system document picker: images, video, audio, PDF),
  and "Share → PixNexa" / "Open with → PixNexa" from other apps. Each file is sorted into image, video, audio or PDF
  by its MIME type (or its extension)
- **Convert / Compress** switch. The bottom panel shows only the formats and options that fit the files in the list;
  a mixed list gets one compact block per category
- **Images**: anything Android decodes (JPEG, PNG, WebP, GIF, BMP, HEIC/HEIF on Android 9+, AVIF on Android 12+)
  → JPEG, PNG, WebP, or **all images in ONE PDF** (page = image shape or A4). Quality slider, **max size**
  (Original / 4K / 1080p / 720p longest side) and **target size in KB** (binary search on the JPEG/WebP quality,
  then smaller dimensions if needed)
- **Video** (Media3 Transformer, hardware codecs): → MP4 H.264/AAC, MP4 HEVC (only offered when the phone has an
  HEVC encoder), resolution Original / 1080p / 720p / 480p, or **extract the audio** to M4A. Compress: H.264 at
  1080p / 720p / 480p with High / Medium / Smallest bitrate. Videos are never upscaled
- **Audio** (MP3, AAC/M4A, WAV, FLAC, OGG/Opus, AMR … whatever the phone decodes) → **M4A (AAC)** at 64–256 kbps
- **PDF**: → JPEG or PNG (one image per page, 72 / 150 / 300 dpi), **merge several PDFs into one**, and **compress**
  (pages re-rendered as JPEG at the chosen DPI and quality)
- Per-file progress (video/audio show a percentage) and **Stop** at any time
- File size **before → after** with the percentage for every file and for the whole batch
- Saves into the right shared folder: images → `Pictures/PixNexa`, video → `Movies/PixNexa`, audio → `Music/PixNexa`,
  PDF → `Download/PixNexa` (MediaStore on Android 10+, public folders on Android 7–9), or into **any folder you choose**.
  Nothing is overwritten
- **Share** any result (or all of them) with the right MIME type
- **Fully offline**: no `INTERNET` permission (the manifest also strips `ACCESS_NETWORK_STATE`, which Media3 would add)
- **Dark / light / system theme**, **Persian (RTL) and English** UI

## Formats

| Input | Convert to | Compress (keeps the type) |
| ----- | ---------- | ------------------------- |
| JPEG, PNG, WebP, GIF, BMP, HEIC/HEIF (9+), AVIF (12+) | JPEG, PNG, WebP, one combined PDF | Same format (JPEG/PNG/WebP; other formats become JPEG): quality, max size, target KB |
| MP4, MOV, 3GP, MKV, WebM … (decoders of the phone) | MP4 (H.264 + AAC), MP4 (HEVC + AAC), M4A (audio only) | MP4 H.264 at 1080p/720p/480p, lower bitrate |
| MP3, M4A/AAC, WAV, FLAC, OGG, Opus, AMR … | M4A (AAC), 64–256 kbps | M4A (AAC), 64–256 kbps |
| PDF | JPEG or PNG per page, one merged PDF | PDF with pages as JPEG images |

## Limitations

- **No MP3, OGG or FLAC output**: Android has no built-in encoders for them and PixNexa uses no native code.
  Audio is always written as AAC in an `.m4a` file.
- Video/audio support depends on the phone's hardware codecs. HEVC output only appears when an HEVC encoder exists.
  HDR videos are kept as HDR; on phones that cannot encode HDR, Media3 may fall back to SDR or the export may fail.
  The compress bitrate is estimated for 30 fps.
- **Compressed and merged PDFs contain page images**: text can no longer be selected or searched and links are lost.
  PDFs with a password cannot be opened (PdfRenderer limitation).
- Images keep no EXIF metadata (location, camera data); the orientation is applied to the pixels. Animated GIF/WebP
  become a still image (first frame). Very large images are scaled down to 64 megapixels.
- Images → PDF and PDF output are written by a small built-in writer that embeds JPEG data directly
  (android.graphics.pdf.PdfDocument would store bitmaps losslessly and ignore the quality setting).

## Libraries

| Library | Version | License | Used for |
| ------- | ------- | ------- | -------- |
| AndroidX (Core, AppCompat, Activity, Lifecycle, DocumentFile, ExifInterface), Jetpack Compose + Material 3 | see `app/build.gradle.kts` | Apache-2.0 | App and UI |
| Coil (`coil-compose`, `coil-video`) | 2.7.0 | Apache-2.0 | Thumbnails (images and video frames) |
| AndroidX Media3 (`media3-transformer`, `media3-effect`, `media3-common`) | 1.4.1 | Apache-2.0 | Video and audio conversion |

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

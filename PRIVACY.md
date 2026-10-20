# Privacy Policy for PixNexa Desktop

PixNexa Desktop is an open-source, local-first utility.

- **No data collection:** it does not collect, transmit, store, or sell any personal data, analytics, or telemetry.
- **Local processing:** every file (images, PDF, video, audio, documents, archives, fonts, subtitles, data) is read
  and converted on your own computer. Nothing is uploaded.
- **No network access:** the app never connects to the internet. The "Website", "GitHub", "Releases" and
  "Get LibreOffice" buttons simply open those pages in your web browser.
- **Helper programs run locally:** video, audio and HEIC output use the FFmpeg program that ships with PixNexa
  (`ffmpeg\ffmpeg.exe`); Office documents use LibreOffice if you installed it. PixNexa starts them on your computer
  with the file you chose and no network options. LibreOffice gets its own settings folder for this
  (`%TEMP%\PixNexa-LibreOffice-profile`), separate from your own LibreOffice settings.
- **Temporary files:** some conversions use a temporary folder in `%TEMP%` that is deleted when the conversion
  ends. Results are written next to the original (or to the folder you chose) and never replace the original file.
- **Metadata:** by default, "Remove metadata" drops EXIF data (camera, GPS location, date) from converted pictures,
  and PDF compression can remove the author, title and XMP data.
- **Settings:** your last-used options (mode, formats, quality, output folder, switches) are stored in
  `%APPDATA%\PixNexa\settings.json` on your computer. Delete the folder to remove them.

## PixNexa Mobile (Android)

- The app has **no internet permission**; images are decoded and converted on the phone.
- Converted files are written only where you choose (the `Pictures/PixNexa` album or a folder you pick), plus a
  temporary copy in the app's private cache that is used for sharing and cleared at the next conversion.
- Your options (format, quality, destination, theme, language) are stored in the app's private storage and are
  excluded from cloud backup.

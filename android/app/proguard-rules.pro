# Compose, AndroidX, Coil and Media3 ship their own consumer rules (Media3's also cover Guava),
# and PixNexa uses no reflection of its own, so nothing app-specific is needed.
# Media3 marks optional extensions (FFmpeg, VP9 ...) that are not part of this app:
-dontwarn androidx.media3.decoder.**

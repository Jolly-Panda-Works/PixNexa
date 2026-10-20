# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **PixNexa Mobile**, the Android app (`android/`, package `com.jollypanda.pixnexa`): batch PNG/JPEG/WebP conversion, quality slider with before/after sizes, save to the gallery or a chosen folder, Android Share menu (both ways), fully offline, dark theme, Persian and English UI.
- `android.yml`: builds the APK and AAB on every push; every push to `main` publishes a release tagged `android-v1.0.N`.
- Website (`site/`) with features, downloads and an Android install guide, deployed to GitHub Pages by `pages.yml`.

## [2.0.0] - 2026-10-14

Image Format Converter is now a real Windows desktop app, built and released by GitHub Actions.

### Added
- Desktop app with a dark-and-orange interface (same theme as SnapshotAll): `image_converter_gui.py`.
- Batch conversion: add files, add a folder, or drag and drop. Every image is listed with a thumbnail and its details.
- Explorer right-click menu: **Convert with Image Format Converter** opens the app with the clicked image(s). Offered by the installer and in Settings → Windows Explorer (per user, no admin rights). The app runs as a single window; extra launches pass their files to it.
- `--register-menu` / `--unregister-menu` command-line switches (used by the installer).
- Images are converted one by one, each with its own progress bar, in addition to the overall bar.
- WEBP output, and a quality slider for JPG and WEBP.
- Animated GIF ⇄ WEBP conversion that keeps all frames.
- Choice of output folder, and a switch for replacing files with the same name (default: never overwrite, use `name (1).ext`).
- EXIF orientation is applied; transparency is painted on white for JPG and BMP.
- Settings dialog with About information; options are remembered in `%APPDATA%\ImageFormatConverter`.
- GitHub Actions: `build.yml` tags every branch build with its version, builds the exe, the installer (`ImageFormatConverter_Setup.exe`) and a portable zip, creates `SHA256SUMS.txt` and publishes releases; `ci.yml` lints and tests.
- Inno Setup installer script, `build_exe.bat`, `run_gui.bat`, `tools/set_version.py` (one version everywhere), Dependabot config.
- Test suite (engine, version tool, window smoke test), `CODE_SIGNING.md`, `PRIVACY.md`.

### Changed
- The conversion engine moved from PowerShell/`System.Drawing` to Pillow (`converter_core.py`). The ICO builder still writes PNG-compressed 16/32/48/256 px icons.
- Documentation, issue templates and the pull request template were rewritten for the new app.

### Removed
- `convert-image.cmd` and `convert-image.ps1`. They remain available in the tags `v1.0.0` and `v1.1.0`.

## [1.1.0] - 2026-08-16

### Changed
- The `.cmd` script now lets you pick the target format from a numbered menu (`[1] jpg` ... `[6] ico`) using `choice`, instead of typing the format name.

## [1.0.0] - 2026-08-16

### Added
- Initial release of the Image Format Converter.
- `.cmd` launcher with an interactive menu (drag-and-drop or typed path, format prompt, convert-another loop).
- `.ps1` conversion engine using `System.Drawing`, supporting output to jpg, jpeg, png, bmp, gif, tiff/tif, and ico.
- Manual multi-resolution ICO builder (16x16, 32x32, 48x48, 256x256) that avoids the known `Bitmap.GetHicon()` corruption bug and preserves transparency.
- README with usage instructions, supported/unsupported formats, troubleshooting, and requirements.
- MIT License.

[Unreleased]: https://github.com/Usef-Farahmand/image-format-converter/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/Usef-Farahmand/image-format-converter/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/Usef-Farahmand/image-format-converter/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Usef-Farahmand/image-format-converter/releases/tag/v1.0.0

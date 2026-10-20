# PixNexa: status of the "full converter" work (paused)

Branch `claude/nifty-planck-77bnb4`, paused on 2026-10-20 at the owner's request. Nothing here is merged into `main` yet.
The repository now lives at **Jolly-Panda-Works/PixNexa** (the old `Usef-Farahmand/image-format-converter` URL redirects).

## 1. One workflow, one release — done, needs one more CI run

`.github/workflows/build.yml` ("Build and release PixNexa") replaces the separate Windows and Android workflows
(`android.yml` is deleted). Jobs: `version` → `windows` + `android` → `publish`.

- One version for every app: `VERSION` = 2.1.0 → releases `v2.1.<run>`; Android `versionCode` = 1000 + run.
- A push to `main` publishes **one release** with `PixNexa_Setup.exe`, `PixNexa_Portable.zip`, `PixNexa.apk`,
  `PixNexa-<version>.apk`, `PixNexa-<version>.aab` and `SHA256SUMS.txt`. Stable links:
  `https://github.com/Jolly-Panda-Works/PixNexa/releases/latest/download/<file>`.
- Last CI run on this branch (run 39467225193): **Windows ✅, Android ✅, Publish ❌**. Publish failed because
  `upload-artifact` kept the `Output/` sub-folder. The fix (flatten `dist/` before `sha256sum`) is in this commit
  but has **not been run in CI yet**.

## 2. PixNexa Mobile (Android) — done, builds in CI, not tested on a device

Code in `android/` (see `android/README.md` for the full format matrix).

- Any image / video / audio / PDF in (photo picker, file picker, Share, Open with); Convert / Compress switch.
- Images → JPEG / PNG / WebP / one PDF; resize; target size in KB.
- Video and audio with Media3 Transformer 1.4.1: MP4 H.264 (HEVC when the phone supports it), M4A, smaller
  resolutions and bitrates. MP3 output is not possible on Android without native code.
- PDF → JPEG/PNG pages, merge, compress (pages re-rendered as JPEG, text no longer selectable).
- Outputs go to Pictures / Movies / Music / Download `…/PixNexa`, or a chosen folder.
- **Verified:** the release APK and AAB build in GitHub Actions (R8 + lint-vital pass).
- **To check on a phone:** video resize for portrait clips, HEVC, large files, PDF compress quality.

## 3. PixNexa Web — done, tested in headless Chromium

Code in `site/converter.js`, `site/engines/`, `site/vendor/` (versions and licenses: `site/vendor/README.md`).

- Images (incl. AVIF output, HEIC input, MozJPEG/OxiPNG, target size), PDF (merge, split, to images/TXT, compress),
  video and audio (ffmpeg.wasm, ~31 MB core loaded from jsDelivr on first use), data (JSON/YAML/CSV/XML/TOML),
  subtitles (SRT/VTT/ASS), archives (ZIP/TAR extract, ZIP create). Nothing is uploaded.
- **Verified:** 43 conversion cases end to end in Playwright Chromium, outputs checked with Python/ffprobe.
- **Open points:** jsDelivr could not be reached from the build sandbox (the core was served locally in tests) and may be
  filtered for some users in Iran; then video/audio do not work and the core would need self-hosting. Not tested in
  Safari or Firefox.
- The website is published by `pages.yml` only from `main`. After the move to Jolly-Panda-Works its address becomes
  `https://jolly-panda-works.github.io/PixNexa/`; the links in `site/`, `README.md`, the Android app (`ui/Components.kt`,
  `WEBSITE`) and the release notes still point at the old `usef-farahmand.github.io/image-format-converter` address and
  must be updated.

## 4. PixNexa Desktop (Windows) — mostly done, stopped mid-way, NOT built or tested on Windows

New engine package `pixnexa_engines/` (registry, images incl. HEIC/AVIF, PDF, media via FFmpeg, office via LibreOffice,
data, archives, fonts, subtitles), a reworked GUI in `image_converter_gui.py` (any file type, Convert / Compress),
`self_test.py` (`PixNexa.exe --self-test`), `tools/fetch_ffmpeg.ps1` (pinned, checksum-verified FFmpeg build bundled in
`dist/PixNexa/ffmpeg/`), `THIRD-PARTY-NOTICES.md`, and updated README / PRIVACY / SECURITY / requirements.

- **Verified on Linux:** `python -m pytest` → 199 passed, 1 skipped; `ruff check .` clean.
- **Not verified:** the window itself, the PyInstaller build with the new packages, the FFmpeg download step and the
  self-test step in CI, the installer. The work was stopped before its author finished reviewing it, so expect fixes.
- Documents (DOCX/XLSX/PPTX…) need LibreOffice installed on the PC; the app says so when it is missing.

## How to continue

1. Push this branch and let CI run; fix the Windows job (FFmpeg download, PyInstaller, self-test) until it is green.
2. Try the desktop window and the Android APK by hand (artifacts of the run).
3. Update every link to `Jolly-Panda-Works/PixNexa` and `jolly-panda-works.github.io/PixNexa`.
4. Decide about self-hosting the ffmpeg.wasm core for the website.
5. Open a pull request into `main`; the first merge publishes release `v2.1.<run>` with all files.
6. Pending from the owner: screenshots of jollypanda.ir to restyle the website (the site could not be reached from here).

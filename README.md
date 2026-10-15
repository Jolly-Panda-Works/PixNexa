<p align="center">
  <img src="assets/logo.png" alt="Image Format Converter logo" width="120">
</p>

# Image Format Converter

**Convert images between JPG, PNG, WEBP, BMP, GIF, TIFF and ICO. Drop in one file or a hundred, pick a format, press Convert.**

[![Build](https://github.com/Usef-Farahmand/image-format-converter/actions/workflows/build.yml/badge.svg)](https://github.com/Usef-Farahmand/image-format-converter/actions/workflows/build.yml)
[![CI](https://github.com/Usef-Farahmand/image-format-converter/actions/workflows/ci.yml/badge.svg)](https://github.com/Usef-Farahmand/image-format-converter/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/Usef-Farahmand/image-format-converter?display_name=tag&color=F97316)](https://github.com/Usef-Farahmand/image-format-converter/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Usef-Farahmand/image-format-converter/total?color=F97316)](https://github.com/Usef-Farahmand/image-format-converter/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/Usef-Farahmand/image-format-converter/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/Usef-Farahmand/image-format-converter#run-from-source)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](https://github.com/Usef-Farahmand/image-format-converter#download-and-install-windows)

[Download](https://github.com/Usef-Farahmand/image-format-converter/releases/latest) · [Report a bug](https://github.com/Usef-Farahmand/image-format-converter/issues/new?template=bug_report.md) · [Request a feature](https://github.com/Usef-Farahmand/image-format-converter/issues/new?template=feature_request.md)

![Image Format Converter](docs/screenshot-main.png)

*Screenshot uses demo data.*

---

## Table of contents

- [Features](#features)
- [Supported formats](#supported-formats)
- [Download and install (Windows)](#download-and-install-windows)
- [How to use it](#how-to-use-it)
- [Run from source](#run-from-source)
- [How the GitHub Action builds it](#how-the-github-action-builds-it)
- [Build it yourself](#build-it-yourself)
- [Project structure](#project-structure)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing) · [Security](#security) · [Privacy](#privacy) · [License](#license)

## Features

- **Batch conversion**: add many images at once (**Add images…**, **Add folder…**, or drag and drop). Each one is shown with a **thumbnail**, its name, format, size and file size.
- **Live progress**: images are converted one after another; every row has its own progress bar and status (✓ new file name / ✗ reason), plus an overall bar at the bottom.
- **7 output formats**: JPG, PNG, WEBP, BMP, GIF, TIFF and ICO.
- **Quality slider** for JPG and WEBP.
- **Real Windows icons**: ICO output contains 16, 32, 48 and 256 px sizes, keeps the aspect ratio and the transparency.
- **Transparency handled properly**: kept for PNG, WEBP, GIF, TIFF and ICO; painted on white for JPG and BMP.
- **Animated GIF ⇄ WEBP** keep every frame and its timing.
- **Camera rotation** (EXIF orientation) is applied, so photos never come out sideways.
- **Safe by default**: an existing file is never overwritten (you get `photo (1).png`) unless you switch that on.
- **Right-click menu in Explorer**: right-click an image → **Convert with Image Format Converter**. The app opens with that image already added; select several images and they all land in the same window.
- **Save next to the original** or into a folder of your choice.
- Works with **Persian and other non-English file names**, and Ctrl+C / Ctrl+V work with any keyboard layout.
- **Private**: everything runs on your computer, there is no network access and no telemetry.
- Modern dark-and-orange interface, built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

## Supported formats

**Input:** PNG, JPG/JPEG, WEBP, BMP, GIF, TIFF, ICO, TGA, PCX, PPM/PGM/PBM (anything [Pillow](https://python-pillow.org/) can read; the "All files" option in the file dialog lets you try other files).

**Output:**

| Format | Notes |
| ------ | ----- |
| `jpg`  | Quality slider. Transparency becomes white. |
| `png`  | Lossless, keeps transparency. |
| `webp` | Quality slider, keeps transparency and animation. |
| `bmp`  | Uncompressed. Transparency becomes white. |
| `gif`  | 256 colors, keeps simple transparency and animation. |
| `tiff` | Lossless (LZW compressed). |
| `ico`  | Multi-size Windows icon (16, 32, 48, 256 px). |

**Not supported: SVG.** SVG is a *vector* format. Turning a raster image into SVG needs vectorization (tracing), which is a very different job from changing the file format. Use a dedicated tool such as [Inkscape](https://inkscape.org/) or [Potrace](https://potrace.sourceforge.net/).

## Download and install (Windows)

1. Open the [**Releases**](https://github.com/Usef-Farahmand/image-format-converter/releases/latest) page.
2. Download one of:
   - `ImageFormatConverter_Setup.exe`: installer (Start menu + desktop shortcut, no admin rights needed)
   - `ImageFormatConverter_Portable.zip`: no installation; unzip and run `ImageFormatConverter.exe`
3. Run it.

> **Windows SmartScreen warning?** The app is not code-signed yet. Click **More info → Run anyway**. Every release ships with `SHA256SUMS.txt` so you can verify your download; see [CODE_SIGNING.md](CODE_SIGNING.md).
> You can always review the source code and build the app yourself (see below).

## How to use it

1. Add images: click **Add images…** (or press `Ctrl+O`), **Add folder…**, drag files and folders onto the window, or right-click an image in Explorer (see below).
2. Choose the target format on the right. For JPG and WEBP, set the quality.
3. Choose where to save: **Next to the original** (default) or a **Custom folder**.
4. Press **Convert**. Each row shows ✓ with the new file name, or ✗ with the reason it failed.
5. The folder opens when it is finished (can be turned off).

Your options are remembered. **Settings → Reset options** brings the defaults back.

### Right-click menu in Windows Explorer

Right-click an image → **Convert with Image Format Converter**. The app opens (or comes to the front if it is already open) with the image added; you pick the format and press Convert there.

- The installer offers this as an option (on by default) and removes it again when you uninstall.
- With the portable version, or when running from source, turn it on in **Settings → Windows Explorer**. It is stored for your user only: no administrator rights are needed.
- On **Windows 11** the item is in the classic menu: right-click → **Show more options**.
- Select several images and right-click: they all open in one window (Windows itself may ask for confirmation when you select a large number of files).
- If the item ever points to an old location (you moved the app), the app repairs it the next time it starts.

## Run from source

Requirements: **Python 3.10+** on Windows (Linux and macOS also work, but only Windows is supported and tested in releases).

```
git clone https://github.com/Usef-Farahmand/image-format-converter.git
cd image-format-converter
pip install -r requirements.txt
python image_converter_gui.py
```

On Windows you can also double-click `run_gui.bat`: it creates a virtual environment and installs everything on the first run.

Use the converter from your own Python code:

```python
from converter_core import convert_image

convert_image("photo.jpg", "png")                            # -> photo.png next to the original
convert_image("logo.png", "ico", out_dir="icons")            # multi-size icon in another folder
convert_image("photo.png", "webp", quality=80, overwrite=True)
```

Run the tests:

```
pip install -r requirements-dev.txt
python -m pytest
```

## How the GitHub Action builds it

[`.github/workflows/build.yml`](.github/workflows/build.yml) runs on a Windows runner. It installs the dependencies, runs the tests, builds the app with PyInstaller, creates the installer with Inno Setup and zips the portable version.

| Trigger | Result |
| ------- | ------ |
| Pull request | Build + tests. Files are kept as **Artifacts** of the run for 14 days (Actions → the run → Artifacts). No tag, no release. |
| Push to `develop` | Same, plus a git tag `vMAJOR.MINOR.0-dev.<build number>`. No release. |
| Push to `main` | Same, plus a git tag and a public **GitHub Release** `vMAJOR.MINOR.<build number>` with `ImageFormatConverter_Setup.exe`, `ImageFormatConverter_Portable.zip` and `SHA256SUMS.txt`. |
| Push of a tag `vX.Y.Z` | A release named exactly after the tag. |
| *Run workflow* button | Same as a push to the selected branch. |

Every build of a branch therefore gets its own git tag with its version number.

Pushes that only change docs (`*.md`, `docs/`, issue templates ...) do not start a build. To start a new release line, change the number in the [`VERSION`](VERSION) file (for example `2.1.0`). The same version string is shown in the app, in the file properties of the exe, in the installer and in the release name.

[`ci.yml`](.github/workflows/ci.yml) additionally lints with Ruff and runs the tests on Windows and Linux.

## Build it yourself

On Windows, double-click `build_exe.bat`. It creates `dist\ImageFormatConverter\ImageFormatConverter.exe`, and if [Inno Setup](https://jrsoftware.org/isinfo.php) is installed also `Output\ImageFormatConverter_Setup.exe`.

## Project structure

```
image-format-converter/
├── image_converter_gui.py   # desktop app: window, drag and drop, settings (customtkinter)
├── converter_core.py        # conversion engine (Pillow, no GUI code)
├── shell_integration.py     # Explorer right-click menu entry (per-user registry keys)
├── single_instance.py       # one window only; later launches hand their files to it
├── app_common.py            # app name, version, author, links
├── VERSION                  # the version number (single source of truth)
├── tools/
│   ├── set_version.py       # decides the build version and injects it everywhere
│   └── make_icons.py        # draws the logo, icon and social-preview image
├── tests/                   # pytest: engine, version tool, window smoke test
├── assets/                  # logo and icons
├── docs/                    # README images
├── installer.iss            # Inno Setup installer script
├── run_gui.bat              # run from source on Windows
├── build_exe.bat            # build the exe locally on Windows
├── requirements.txt         # runtime dependencies
├── requirements-dev.txt     # + pytest and ruff
├── CODE_SIGNING.md          # code-signing policy and SmartScreen guide
└── .github/                 # workflows, issue and PR templates, Dependabot
```

## Limitations

- **SVG** input and output are not supported (see above). HEIC/HEIF and RAW camera files are not supported either.
- **Animation** is kept only for GIF ⇄ WEBP. Converting an animated image to any other format uses its first frame.
- **Metadata** (EXIF, GPS, camera info) is not copied to the new file. Color profiles are kept for JPG, PNG, WEBP and TIFF.
- Converting to **JPG/WEBP** is lossy; converting to **GIF** reduces the image to 256 colors.
- Folders are added without their sub-folders.
- The Explorer right-click item is for single files or a selection of files, not for folders, and it is not shown in Windows 11's new compact menu (only under **Show more options**).
- No code signing yet, so Windows SmartScreen may warn on first launch.

## Troubleshooting

| Problem | Fix |
| ------- | --- |
| "Windows protected your PC" | Click **More info → Run anyway**. See [CODE_SIGNING.md](CODE_SIGNING.md). |
| A row says ✗ "Not a supported image file" | The file is damaged or is not a raster image (for example SVG or a PDF). |
| Drag and drop does nothing | Use **Add images…** instead. Dropping onto an app that runs as administrator is blocked by Windows. |
| The right-click item is missing | Turn it on in **Settings → Windows Explorer**. On Windows 11 look under **Show more options**. |
| Ctrl+V does not paste into the folder field | Right-click the field → Paste. |
| Output is next to the original but the file has `(1)` in its name | A file with that name already existed. Turn on **Replace files with the same name** to overwrite it. |

## Contributing

Contributions are very welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Found a vulnerability? Please do **not** open a public issue; see [SECURITY.md](SECURITY.md).

## Privacy

Everything happens on your computer; see [PRIVACY.md](PRIVACY.md).

## History

Versions 1.x were a small `.cmd` + PowerShell script. They are still available in the tags [`v1.0.0`](https://github.com/Usef-Farahmand/image-format-converter/releases/tag/v1.0.0) and [`v1.1.0`](https://github.com/Usef-Farahmand/image-format-converter/releases/tag/v1.1.0). Version 2 is a full desktop app. See [CHANGELOG.md](CHANGELOG.md).

## License

Released under the [MIT License](LICENSE) © 2026 [Usef Farahmand](https://github.com/Usef-Farahmand) · [useffarahmand.com](https://www.useffarahmand.com/).

## Acknowledgments

[Pillow](https://python-pillow.org/) · [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) · [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) · [PyInstaller](https://pyinstaller.org/) · [Inno Setup](https://jrsoftware.org/isinfo.php). The build pipeline and the dark-and-orange theme follow [SnapshotAll](https://github.com/Usef-Farahmand/SnapshotAll).

# Image Format Converter (CMD Script)

[![Version](https://img.shields.io/github/v/release/Usef-Farahmand/image-format-converter?label=version)](https://github.com/Usef-Farahmand/image-format-converter/releases/latest)
[![Release](https://img.shields.io/github/v/tag/Usef-Farahmand/image-format-converter?label=release)](https://github.com/Usef-Farahmand/image-format-converter/releases)
[![License](https://img.shields.io/github/license/Usef-Farahmand/image-format-converter)](https://github.com/Usef-Farahmand/image-format-converter/blob/main/LICENSE)
[![CI](https://github.com/Usef-Farahmand/image-format-converter/actions/workflows/ci.yml/badge.svg)](https://github.com/Usef-Farahmand/image-format-converter/actions/workflows/ci.yml)

A simple Windows `.cmd` script that converts an image from one format to another — **no third-party software required**. It uses PowerShell and the built-in .NET `System.Drawing` library, both of which ship with Windows.

## Features

- Prompts you for an image path (you can also drag and drop the file into the console window)
- Prompts you for the target format
- Converts the image and saves it next to the original file
- No installation, no dependencies, no internet connection needed

## Supported Formats

**Input:** any format supported by `System.Drawing` (jpg, png, bmp, gif, tiff, and most common raster formats)

**Output:**
- `jpg` / `jpeg`
- `png`
- `bmp`
- `gif`
- `tiff` / `tif`
- `ico`

## Not Supported

- **svg** — SVG is a *vector* format, not a raster format. Converting a raster image (jpg, png, etc.) to SVG requires vectorization/tracing, which is a fundamentally different (and much more complex) process than a simple format conversion. Windows has no built-in tool for this. If you need SVG output, use a dedicated tool such as [Inkscape](https://inkscape.org/) (free) or [Potrace](http://potrace.sourceforge.net/).

## Files

- `convert-image.cmd` — the script you run
- `convert-image.ps1` — does the actual conversion (must stay in the **same folder** as the `.cmd` file)

## Usage

1. Download both `convert-image.cmd` and `convert-image.ps1` and keep them in the same folder.
2. Double-click `convert-image.cmd` to run it.
3. Enter the path to your image (or drag and drop the image file into the console window and press Enter).
4. Choose the desired output format from the numbered menu (e.g. press `2` for `png`).
5. The converted file is created in the same folder as the original, and that folder opens automatically with the new file selected.
6. Press `C` to convert another image, or `X` to exit.

### Troubleshooting

If you see an error like `execution of scripts is disabled on this system`, your PowerShell execution policy is blocking the script. The `.cmd` file already runs PowerShell with `-ExecutionPolicy Bypass`, which should avoid this in most cases. If it still happens, open PowerShell as Administrator and run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Example

```
Enter the image file path: C:\Users\me\Pictures\photo.jpg

Select the target format:
  [1] jpg
  [2] png
  [3] bmp
  [4] gif
  [5] tiff
  [6] ico

Enter your choice (1-6): 2

Converting...
Conversion completed successfully.
Output file: C:\Users\me\Pictures\photo.png
```

## Notes on ICO conversion

Converting to `.ico` produces a proper multi-resolution icon containing four standard sizes (16x16, 32x32, 48x48, 256x256), each embedded as PNG data (the modern ICO format supported since Windows Vista). The source image is automatically fitted into each square canvas while preserving its aspect ratio and transparency.

Earlier versions of this script used .NET's `Bitmap.GetHicon()`, which has a known bug that produces corrupted `.ico` files for non-standard image dimensions. This has been fixed by building the ICO file manually.

## Requirements

- Windows with PowerShell available (included by default on Windows 7 and later)
- No admin rights or installation needed

## Version

Current version: **1.1.0** (see [CHANGELOG.md](CHANGELOG.md) for release history)

Download the latest release from the [Releases page](https://github.com/Usef-Farahmand/image-format-converter/releases/latest).

## Author

**Usef Farahmand**
GitHub: [https://github.com/Usef-Farahmand](https://github.com/Usef-Farahmand)

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
development setup, code style, and how to submit a pull request. This
project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Found a security issue? Please see [SECURITY.md](SECURITY.md) for how to
report it responsibly instead of opening a public issue.

## License

[MIT](https://github.com/Usef-Farahmand/image-format-converter/blob/main/LICENSE) — feel free to use, modify, and share.

# Third-party notices: PixNexa Desktop

PixNexa Desktop itself is released under the [MIT License](LICENSE). The Windows installer and the portable zip
also contain the open-source components below. Each keeps its own license; the full license texts are in the
`_internal` folder next to `PixNexa.exe` (in each package's `*.dist-info` folder) or at the links given.

No GPL or AGPL library is linked into PixNexa. **FFmpeg** is shipped as a separate program (`ffmpeg\ffmpeg.exe`)
that PixNexa starts like any other program; it is not linked. **LibreOffice** is never shipped: PixNexa uses it
only when you have installed it yourself.

## Programs shipped next to PixNexa

| Component | Version | License | Source |
| --------- | ------- | ------- | ------ |
| **FFmpeg** (`ffmpeg\ffmpeg.exe`), Windows x64 "gpl" build by BtbN/FFmpeg-Builds, release `autobuild-2026-09-30-13-08` | n9.0.2-17-g2a571b6068 | **GPL-3.0** (the build includes GPL libraries such as x264 and x265). The license text is `ffmpeg\LICENSE.txt`. | FFmpeg: <https://github.com/FFmpeg/FFmpeg/tree/2a571b6068> and <https://ffmpeg.org/download.html#releases>. Build scripts and the versions of every library inside: <https://github.com/BtbN/FFmpeg-Builds> (release page: <https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-09-30-13-08>). `ffmpeg\SOURCE.txt` repeats these links. |

You may replace `ffmpeg\ffmpeg.exe` with any other FFmpeg build; PixNexa will use it. As required by the GPL,
the complete corresponding source code is available from the links above; if they ever stop working, open an
issue in this repository and the maintainer will provide it.

## Python libraries inside the app

| Package | Used for | License |
| ------- | -------- | ------- |
| [CPython](https://www.python.org/) 3.11 and its standard library | runtime | PSF-2.0 |
| [Tcl/Tk](https://www.tcl.tk/) (bundled with Python) | window toolkit | Tcl/Tk license (BSD-style) |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | interface | MIT (CC0-1.0 in newer releases) |
| [darkdetect](https://github.com/albertosottile/darkdetect) | CustomTkinter dependency | BSD-3-Clause |
| [packaging](https://github.com/pypa/packaging) | dependency of CustomTkinter and pikepdf | Apache-2.0 OR BSD-2-Clause |
| [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) (with the tkdnd Tcl extension) | drag and drop | MIT (tkdnd: BSD-style) |
| [Pillow](https://python-pillow.org/) | images | MIT-CMU (HPND). Its wheels include libjpeg-turbo (IJG / BSD-3-Clause), libpng (libpng license), zlib (zlib), libtiff (libtiff license), libwebp (BSD-3-Clause), FreeType (FreeType License), Little CMS (MIT), OpenJPEG (BSD-2-Clause), HarfBuzz (MIT), Brotli (MIT), libavif (BSD-2-Clause), libaom (BSD-2-Clause + AOM patent license) and dav1d (BSD-2-Clause) |
| [pi-heif](https://github.com/bigcat88/pillow_heif) | reading HEIC / HEIF (decode-only build) | BSD-3-Clause; bundled libheif and libde265 are **LGPL-3.0** (dynamically loaded libraries, replaceable) |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | PDF pages to pictures, PDF text | Apache-2.0 OR BSD-3-Clause; bundled [PDFium](https://pdfium.googlesource.com/pdfium/) is BSD-3-Clause with its third-party parts (FreeType, libjpeg-turbo, Little CMS, OpenJPEG, zlib, ICU, Abseil: permissive licenses, see `pypdfium2_raw` in `_internal`) |
| [pikepdf](https://github.com/pikepdf/pikepdf) | PDF merge, split, pages, compression, pictures to PDF | **MPL-2.0**; bundled [qpdf](https://github.com/qpdf/qpdf) is Apache-2.0, plus libjpeg-turbo and zlib |
| [lxml](https://lxml.de/) | pikepdf dependency | BSD-3-Clause (libxml2 and libxslt: MIT) |
| [py7zr](https://github.com/miurahr/py7zr) | 7Z archives | **LGPL-2.1-or-later** (Python package, used unmodified) |
| [pyppmd](https://github.com/miurahr/pyppmd), [pybcj](https://github.com/miurahr/pybcj), [inflate64](https://github.com/miurahr/inflate64), [multivolumefile](https://github.com/miurahr/multivolume) | py7zr dependencies | **LGPL-2.1-or-later** |
| [backports.zstd](https://github.com/Rogdham/backports.zstd) (or pyzstd on older setups) | py7zr dependency | PSF-2.0 (bundled Zstandard: BSD-3-Clause) |
| [pycryptodomex](https://www.pycryptodome.org/) | py7zr dependency | BSD-2-Clause / Public Domain |
| [psutil](https://github.com/giampaolo/psutil) | py7zr dependency | BSD-3-Clause |
| [texttable](https://github.com/foutaise/texttable) | py7zr dependency | MIT |
| [fontTools](https://github.com/fonttools/fonttools) | fonts | MIT |
| [Brotli](https://github.com/google/brotli) | WOFF2 | MIT |
| [pysubs2](https://github.com/tkarabela/pysubs2) | subtitles | MIT |
| [PyYAML](https://pyyaml.org/) | YAML | MIT |
| [tomli-w](https://github.com/hukkin/tomli-w) (and [tomli](https://github.com/hukkin/tomli) on Python 3.10) | TOML | MIT |
| [openpyxl](https://openpyxl.readthedocs.io/) and [et-xmlfile](https://foss.heptapod.net/openpyxl/et_xmlfile) | XLSX | MIT |
| [Python-Markdown](https://python-markdown.github.io/) | Markdown to HTML | BSD-3-Clause |

The LGPL-licensed parts (libheif, libde265, py7zr and its compression modules) are used unmodified, are
separate files inside `_internal`, and can be replaced by the user with other builds of the same version. Their
source code is available from the project pages linked above.

## Build tools (not part of the app's code)

| Tool | License |
| ---- | ------- |
| [PyInstaller](https://pyinstaller.org/) (its bootloader is part of `PixNexa.exe`) | GPL-2.0-or-later **with the PyInstaller bootloader exception**, which allows distributing the bootloader with programs under any license |
| [Inno Setup](https://jrsoftware.org/isinfo.php) (builds `PixNexa_Setup.exe`) | Inno Setup License (free, permissive) |

## Optional program that PixNexa uses but does not ship

| Program | License | Notes |
| ------- | ------- | ----- |
| [LibreOffice](https://www.libreoffice.org/) | MPL-2.0 | Used for DOCX / DOC / ODT / RTF / XLSX / XLS / ODS / PPTX / PPT / ODP conversions when it is installed. PixNexa starts `soffice --headless --convert-to` and never downloads it. |

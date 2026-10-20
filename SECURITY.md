# Security Policy

## Supported Versions

Only the latest released version is actively supported with security fixes.

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

PixNexa Desktop is a local Windows app with no network access and no telemetry. It reads many kinds of files
(images, PDF, video, audio, Office documents, archives, fonts, subtitles, JSON / YAML / TOML / XML / CSV), so the
most relevant problems are in how files are decoded and written: for example a crafted file that crashes the app,
an archive that writes outside its target folder, unsafe handling of file paths, or a problem in a bundled
dependency (Pillow, pi-heif, pypdfium2, pikepdf, py7zr, fontTools, FFmpeg, ...; see
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)).

What PixNexa already does:

- **Archives** are listed before anything is extracted. Entries with `..`, absolute paths or drive letters stop the
  job ("points outside the target folder") before a single file is written; symbolic links are never created;
  password-protected archives are refused; an archive that would unpack to more than the free disk space or
  with more than 1,000,000 entries is refused; a ZIP or TAR entry that unpacks to more data than it declares is
  stopped.
- **Results are written to a temporary name first** and renamed when complete, so a failed or stopped conversion
  never leaves half-written files, and the original file is never overwritten.
- **External programs** (FFmpeg, LibreOffice) are started with an argument list (never through a shell) and can be
  stopped at any time. Text that looks like a formula is stored as text in XLSX output.
- **Pictures** larger than Pillow's decompression-bomb limit are refused.

If you find a security issue, please report it privately rather than opening a public issue:

1. Open a [GitHub Security Advisory](https://github.com/Usef-Farahmand/image-format-converter/security/advisories/new) for this repository, **or**
2. Contact the maintainer directly through their GitHub profile ([@Usef-Farahmand](https://github.com/Usef-Farahmand)).

Please include:
- A description of the issue and its potential impact
- Steps to reproduce (a sample file helps)
- The affected version (**Settings → About**, or the release tag)

You should expect an initial response within a few days. If the issue is confirmed, a fix will be released and
credited to you (unless you prefer to remain anonymous) in the `CHANGELOG.md`.

Please do **not** open a public issue for security reports.

Dependabot keeps the dependencies and GitHub Actions up to date; every release is built from source by GitHub Actions.

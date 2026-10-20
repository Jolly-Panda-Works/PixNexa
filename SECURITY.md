# Security Policy

## Supported Versions

Only the latest released version is actively supported with security fixes.

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

PixNexa Desktop is a local Windows app with no network access and no telemetry. It does read image
files, so the most relevant problems are in how files are decoded and written (for example a crafted image that
crashes the app, unsafe handling of file paths, or a problem in a bundled dependency such as Pillow). If you
find a security issue, please report it privately rather than opening a public issue:

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

# Security Policy

## Supported Versions

Only the latest released version is actively supported with security fixes.

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

## Reporting a Vulnerability

This project is a local Windows `.cmd`/`.ps1` tool with no network access, no
external dependencies, and no telemetry — the attack surface is intentionally
small. That said, if you find a security issue (for example, unsafe handling
of file paths, or a way the script could be tricked into executing unintended
code), please report it privately rather than opening a public issue:

1. Open a [GitHub Security Advisory](https://github.com/Usef-Farahmand/image-format-converter/security/advisories/new)
   for this repository, **or**
2. Contact the maintainer directly through their GitHub profile
   ([@Usef-Farahmand](https://github.com/Usef-Farahmand)).

Please include:
- A description of the issue and its potential impact
- Steps to reproduce
- The affected version (`VERSION` file / release tag)

You should expect an initial response within a few days. If the issue is
confirmed, a fix will be released and credited to you (unless you prefer to
remain anonymous) in the `CHANGELOG.md`.

Please do **not** open a public issue for security reports.

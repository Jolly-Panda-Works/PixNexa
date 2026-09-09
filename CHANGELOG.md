# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source project scaffolding: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- GitHub issue templates (bug report, feature request) and a pull request template.
- CI workflow (`.github/workflows/ci.yml`) that lints `convert-image.ps1` with PSScriptAnalyzer and sanity-checks `convert-image.cmd` on every push/PR.

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

[Unreleased]: https://github.com/Usef-Farahmand/image-format-converter/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Usef-Farahmand/image-format-converter/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Usef-Farahmand/image-format-converter/releases/tag/v1.0.0

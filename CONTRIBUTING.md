# Contributing to Image Format Converter

Thanks for taking the time to contribute! This is a small, focused project (a
`.cmd` launcher + a `.ps1` conversion engine), so the bar for contributing is
low and PRs are very welcome.

## Ways to contribute

- **Report a bug** — open an [issue](https://github.com/Usef-Farahmand/image-format-converter/issues/new?template=bug_report.md).
- **Suggest a feature** — open a [feature request](https://github.com/Usef-Farahmand/image-format-converter/issues/new?template=feature_request.md).
- **Improve the docs** — README fixes, clearer troubleshooting steps, etc. are
  always appreciated.
- **Submit code** — bug fixes, new output formats, or quality-of-life
  improvements to the scripts.

## Development setup

You'll need Windows with PowerShell (the scripts rely on `System.Drawing`,
which is Windows-only via .NET Framework).

1. Fork and clone the repo.
2. Keep `convert-image.cmd` and `convert-image.ps1` in the same folder.
3. Run `convert-image.cmd` to test your changes manually.

There's no build step — the scripts run as-is.

## Code style

- **`.ps1`**: prefer clear, explicit variable names; avoid aliases (`%`, `?`)
  in committed code; add comments for anything non-obvious (see the ICO
  builder for an example). If you add a rule that
  [PSScriptAnalyzer](https://github.com/PowerShell/PSScriptAnalyzer) flags,
  either fix it or explain the suppression in a comment.
- **`.cmd`**: keep it a thin wrapper — user prompts, argument passing, and
  exit-code handling. The actual conversion logic belongs in the `.ps1` file.
- Match the existing line-ending style (CRLF) since these are Windows batch
  and PowerShell files.

## Adding a new output format

1. Add the format to the `switch` handling in `convert-image.ps1`.
2. Update the "Supported formats" list in `convert-image.cmd`.
3. Update the **Supported Formats** section of `README.md`.
4. Add an entry under `[Unreleased]` in `CHANGELOG.md`.

## Submitting a pull request

1. Create a branch from `main`: `git checkout -b my-fix`.
2. Make your changes and test them locally on Windows.
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. Open a PR against `main` and fill out the PR template.
5. CI will lint the PowerShell script with PSScriptAnalyzer — make sure it's
   green before requesting review.

## Reporting bugs

Please include:
- Windows version and PowerShell version (`$PSVersionTable.PSVersion`)
- The exact command / steps you ran
- The full error output
- Sample input file details (format, dimensions) if relevant — not the file
  itself unless needed to reproduce

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you're expected to uphold it.

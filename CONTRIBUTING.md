# Contributing to Image Format Converter

Thanks for taking the time to contribute! This is a small, focused project (a Pillow-based
conversion engine and a CustomTkinter window), so the bar for contributing is low and PRs are very welcome.

## Ways to contribute

- **Report a bug**: open an [issue](https://github.com/Usef-Farahmand/image-format-converter/issues/new?template=bug_report.md).
- **Suggest a feature**: open a [feature request](https://github.com/Usef-Farahmand/image-format-converter/issues/new?template=feature_request.md).
- **Improve the docs**: README fixes, clearer troubleshooting steps, etc. are always appreciated.
- **Submit code**: bug fixes, new formats, or quality-of-life improvements.

## Development setup

You need **Python 3.10+**. The app is built and released for Windows, but the engine and tests also run on Linux/macOS.

```
git clone https://github.com/Usef-Farahmand/image-format-converter.git
cd image-format-converter
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python image_converter_gui.py
```

Before you open a pull request:

```
ruff check .
python -m pytest
```

The window test (`tests/test_gui_smoke.py`) skips itself when there is no display.

## Code style

- Keep **GUI code** in `image_converter_gui.py` and **conversion logic** in `converter_core.py`.
  `converter_core.py` must not import `tkinter` or `customtkinter`, so it stays testable.
- Follow the Ruff configuration in `ruff.toml` (line length 120).
- Use the colors defined at the top of `image_converter_gui.py`; do not hard-code new ones in widgets.
- Line endings: LF, except `*.bat` and `*.iss` which use CRLF (see `.gitattributes`).

## Adding a new output format

1. Add an `OutputFormat` entry to `FORMATS` in `converter_core.py` and handle it in `_save_still`.
2. Add tests in `tests/test_converter_core.py` (the "every target format" test picks it up automatically).
3. Update the **Supported formats** section of `README.md`.
4. Add an entry under `[Unreleased]` in `CHANGELOG.md`.

The format buttons in the window are created from `FORMATS`, so no GUI change is needed (the grid fits up to 8 formats).

## Submitting a pull request

1. Create a branch from `main`: `git checkout -b my-fix`.
2. Make your changes and add or update tests.
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. Open a PR against `main` and fill out the PR template.
5. CI lints and tests your change, and the *Build* workflow builds the installer; make sure both are green.
   You can download the built installer from the **Artifacts** of the workflow run to try it.

## Releases

Pushes to `main` publish a release automatically (see the README, "How the GitHub Action builds it").
To start a new release line, change the number in the `VERSION` file.

## Reporting bugs

Please include:
- Windows version and the app version (**Settings → About**)
- The steps you took and the format you converted to
- The exact error text shown in the list
- Details of the source image (format, dimensions); not the file itself unless needed to reproduce

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you're expected to uphold it.

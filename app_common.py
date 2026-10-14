"""Shared constants for Image Format Converter (name, version, author, links)."""
from pathlib import Path

APP_NAME = "Image Format Converter"
APP_SLUG = "ImageFormatConverter"          # exe / installer / settings-folder name
APP_AUTHOR = "Usef Farahmand"
APP_URL = "https://github.com/Usef-Farahmand"
APP_WEBSITE = "https://www.useffarahmand.com/"
APP_REPO = "https://github.com/Usef-Farahmand/image-format-converter"
APP_LICENSE = "MIT License"


def _read_default_version():
    """The VERSION file is the one place to change the version by hand (see tools/set_version.py)."""
    try:
        return (Path(__file__).resolve().parent / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


try:  # written at build time, so the app, exe properties, installer and release all show the same version
    from _build_version import APP_VERSION  # noqa: F401
except ImportError:
    APP_VERSION = _read_default_version()

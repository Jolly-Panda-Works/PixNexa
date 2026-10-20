"""Fonts: TTF / OTF <-> WOFF / WOFF2 with fontTools (WOFF2 uses Brotli). Lossless both ways."""
from __future__ import annotations

from pathlib import Path

from .base import ConversionError, Options, ProgressCallback, atomic_output, report, target_path

INPUT_EXT = (".ttf", ".otf", ".woff", ".woff2")
TARGETS = ("ttf", "woff", "woff2")       # "ttf" means the desktop font: .ttf or .otf, whichever the outlines are


def convert(src, target: str, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    from fontTools.ttLib import TTFont, TTLibError

    src = Path(src)
    target = target.lower()
    try:
        font = TTFont(str(src), recalcBBoxes=False, recalcTimestamp=False)
    except (TTLibError, OSError, ValueError, AssertionError) as exc:
        raise ConversionError(f"Not a readable font file ({exc.__class__.__name__}).") from None
    except ImportError:
        raise ConversionError("WOFF2 support (brotli) is missing from this build.") from None
    try:
        if target in ("ttf", "otf", "desktop"):
            font.flavor = None
            ext = "otf" if ("CFF " in font or "CFF2" in font) else "ttf"
        elif target in ("woff", "woff2"):
            font.flavor = target
            ext = target
        else:
            raise ConversionError(f"Unsupported target format: {target}")
        report(progress, 0.3)
        dst = target_path(src, ext, options)
        with atomic_output(dst) as temp:
            try:
                font.save(str(temp), reorderTables=None)
            except ImportError:
                raise ConversionError("WOFF2 support (brotli) is missing from this build.") from None
    finally:
        font.close()
    report(progress, 1)
    return [dst]

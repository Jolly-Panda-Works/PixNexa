"""Subtitles with pysubs2: SRT, ASS, SSA, WebVTT, MicroDVD (.sub) and TTML <-> each other; SAMI (.smi) is read.

Files are read as UTF-8 (with or without BOM) or UTF-16, else as Windows-1252; everything is written as UTF-8.
MicroDVD counts frames: it is read at the rate its first line states (else 23.976) and written at 23.976 fps.
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import ConversionError, Options, ProgressCallback, atomic_output, report, target_path

INPUT_EXT = (".srt", ".ass", ".ssa", ".vtt", ".sub", ".smi", ".sami", ".ttml", ".dfxp")
TARGETS = ("srt", "ass", "ssa", "vtt", "sub", "ttml")      # SAMI is read only
FORMAT_ID = {"srt": "srt", "ass": "ass", "ssa": "ssa", "vtt": "vtt", "sub": "microdvd", "smi": "sami",
             "sami": "sami", "ttml": "ttml", "dfxp": "ttml"}
FPS = 23.976


def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")


def load(path: Path):
    import pysubs2

    text = _decode(path.read_bytes())
    fmt = FORMAT_ID.get(path.suffix.lower().lstrip("."))
    try:
        if fmt == "microdvd":
            # A first line "{1}{1}25" (or "{0}{0}25") states the frame rate; older pysubs2 versions read it as a cue.
            fps = FPS
            lines = text.lstrip("\ufeff").splitlines()
            m = re.fullmatch(r"\s*[{\[][01][}\]][{\[][01][}\]]\s*(\d+(?:[.,]\d+)?)\s*", lines[0]) if lines else None
            if m:
                fps = float(m.group(1).replace(",", "."))
                text = "\n".join(lines[1:])
            return pysubs2.SSAFile.from_string(text, format_="microdvd", fps=fps)
        try:
            return pysubs2.SSAFile.from_string(text, format_=fmt)
        except (pysubs2.exceptions.FormatAutodetectionError, pysubs2.exceptions.UnknownFormatIdentifierError):
            return pysubs2.SSAFile.from_string(text)
    except Exception as exc:
        raise ConversionError(f"Not a readable subtitle file ({exc.__class__.__name__}).") from None


def convert(src, target: str, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    src = Path(src)
    target = target.lower()
    if target not in TARGETS:
        raise ConversionError(f"Unsupported target format: {target}")
    subs = load(src)
    if not subs.events:
        raise ConversionError("No subtitles found in this file.")
    report(progress, 0.5)
    kwargs = {"fps": FPS} if FORMAT_ID[target] == "microdvd" else {}
    try:
        text = subs.to_string(FORMAT_ID[target], **kwargs)
    except Exception as exc:
        raise ConversionError(f"Could not write {target.upper()}: {exc}") from None
    dst = target_path(src, target, options)
    with atomic_output(dst) as temp:
        temp.write_text(text, encoding="utf-8", newline="")
    report(progress, 1)
    return [dst]

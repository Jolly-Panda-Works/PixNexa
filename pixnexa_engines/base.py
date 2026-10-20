"""Shared pieces of every engine: options, output names, safe writing, external programs.

Nothing here talks to the network. External programs (FFmpeg, LibreOffice) run as separate processes
with no console window on Windows.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from converter_core import ConversionError, unique_path

ProgressCallback = Callable[[float], None]

__all__ = ["ConversionError", "Options", "ProgressCallback", "Cancelled", "target_path", "target_folder",
           "atomic_output", "atomic_folder", "app_dir", "run_process", "report", "check_cancel", "human_size"]


class Cancelled(ConversionError):
    """The user pressed Stop while a long conversion was running."""

    def __init__(self, message="Stopped."):
        super().__init__(message)


@dataclass
class Options:
    """Everything a converter may look at. Unknown or unused fields are simply ignored."""

    out_dir: str | os.PathLike | None = None     # None: next to the original
    overwrite: bool = False                      # replace "name.ext"; otherwise "name (1).ext"
    suffix: str = ""                             # added to the file name, e.g. "-compressed"

    # images
    quality: int = 90                            # 1-100 for JPG / WEBP / AVIF / HEIC (and PDF images)
    resize_mode: str = "none"                    # "none" | "max" (fit inside width x height) | "percent"
    max_width: int = 0
    max_height: int = 0
    percent: int = 100
    grayscale: bool = False
    strip_metadata: bool = True                  # drop EXIF / GPS / camera data (the colour profile stays)
    target_kb: int = 0                           # compress: aim for at most this many KB (0 = off)
    png_palette: bool = False                    # compress PNG to 256 colours

    # PDF
    dpi: int = 150                               # PDF -> image resolution, and the PDF compress limit
    pages: str = ""                              # "" = all, or "1-3, 5"
    page_size: str = "image"                     # images -> PDF: "image" | "a4" | "letter"

    # video / audio
    video_quality: str = "balanced"              # "high" | "balanced" | "small"
    video_codec: str = "h264"                    # "h264" | "h265"
    max_height_px: int = 0                       # 0 = keep, else 1080 / 720 / 480 (only ever scales down)
    audio_bitrate: int = 192                     # kbit/s for lossy audio

    # archives
    archive_format: str = "zip"                  # for "files -> one archive"

    cancel: threading.Event | None = field(default=None, repr=False, compare=False)

    def clamp(self) -> Options:
        self.quality = max(1, min(100, int(self.quality or 90)))
        self.percent = max(1, min(1000, int(self.percent or 100)))
        self.dpi = max(36, min(1200, int(self.dpi or 150)))
        self.max_width = max(0, int(self.max_width or 0))
        self.max_height = max(0, int(self.max_height or 0))
        self.target_kb = max(0, int(self.target_kb or 0))
        self.audio_bitrate = max(32, min(512, int(self.audio_bitrate or 192)))
        return self


def check_cancel(options: Options | None):
    if options is not None and options.cancel is not None and options.cancel.is_set():
        raise Cancelled()


def report(progress: ProgressCallback | None, value: float):
    if progress is not None:
        try:
            progress(max(0.0, min(1.0, float(value))))
        except Exception:  # a broken progress display must never break a conversion
            pass


def human_size(n: float) -> str:
    if n < 1024:
        return f"{int(n)} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
    return f"{n:.1f} GB"  # pragma: no cover


# ───────────────────────── output names ─────────────────────────

def _folder_for(src: Path, options: Options) -> Path:
    return Path(options.out_dir) if options.out_dir else src.parent


def _same(a: Path, b: Path) -> bool:
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def target_path(src, extension: str, options: Options, stem: str | None = None) -> Path:
    """The file to write for `src`: same name, new extension, never the source itself, never an existing file
    (unless overwrite is on)."""
    src = Path(src)
    base = f"{stem if stem is not None else src.stem}{options.suffix}"
    extension = extension.lstrip(".")
    folder = _folder_for(src, options)
    dst = folder / f"{base}.{extension}"
    if options.overwrite and not _same(src, dst) and not dst.is_dir():
        return dst
    if "." not in extension:
        return unique_path(dst)
    for i in range(1, 10_000):            # "backup (1).tar.gz", not "backup.tar (1).gz"
        if not dst.exists():
            return dst
        dst = folder / f"{base} ({i}).{extension}"
    raise ConversionError("Too many files with the same name in the output folder.")


def target_folder(src, options: Options, name: str | None = None) -> Path:
    """A new folder for results that are several files (pages of a PDF, an extracted archive)."""
    src = Path(src)
    folder = _folder_for(src, options) / (name or f"{src.stem}{options.suffix}")
    return unique_path(folder)


@contextlib.contextmanager
def atomic_output(dst: Path) -> Iterator[Path]:
    """Yield a temporary path next to `dst`; on success it is renamed to `dst`, on any error it is removed.

    The temporary name keeps the extension, because FFmpeg and LibreOffice pick the format from it.
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    temp = dst.with_name(f"{dst.stem}.part{dst.suffix}")
    temp = unique_path(temp)
    try:
        yield temp
        if not temp.exists():
            raise ConversionError("Nothing was written.")
        os.replace(temp, dst)
    except BaseException:
        with contextlib.suppress(OSError):
            temp.unlink()
        raise


@contextlib.contextmanager
def atomic_folder(dst: Path) -> Iterator[Path]:
    """Like atomic_output, for a folder: built hidden next to the target, renamed into place when complete."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_path(dst.with_name(f".{dst.name}.part"))
    temp.mkdir()
    try:
        yield temp
        os.replace(temp, dst)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


# ───────────────────────── external programs ─────────────────────────

def app_dir() -> Path:
    """Folder of PixNexa.exe when frozen, else the source folder. Bundled tools live below it."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _no_window_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run_process(args, *, options: Options | None = None, timeout: float | None = None,
                on_stdout_line: Callable[[str], None] | None = None, cwd=None) -> tuple[int, str]:
    """Run a program without a console window. Returns (exit code, stderr text).

    stdout is read line by line (for FFmpeg's -progress output); Stop kills the process.
    """
    try:
        proc = subprocess.Popen([str(a) for a in args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=cwd, creationflags=_no_window_flags())
    except FileNotFoundError:
        raise ConversionError(f"Program not found: {Path(str(args[0])).name}") from None
    except OSError as exc:
        raise ConversionError(f"Could not start {Path(str(args[0])).name}: {exc}") from None

    err_chunks: list[bytes] = []
    reader = threading.Thread(target=lambda: err_chunks.append(proc.stderr.read()), daemon=True)
    reader.start()
    cancelled = threading.Event()

    def watch():
        while proc.poll() is None:
            if options is not None and options.cancel is not None and options.cancel.wait(0.2):
                cancelled.set()
                with contextlib.suppress(OSError):
                    proc.kill()
                return
            if options is None or options.cancel is None:
                return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    timer = None
    if timeout:
        timer = threading.Timer(timeout, lambda: proc.poll() is None and proc.kill())
        timer.daemon = True
        timer.start()
    try:
        for raw in proc.stdout:
            if on_stdout_line is not None:
                on_stdout_line(raw.decode("utf-8", "replace").strip())
        proc.wait()
    finally:
        if timer is not None:
            timer.cancel()
        reader.join(5)
    if cancelled.is_set():
        raise Cancelled()
    stderr = b"".join(err_chunks).decode("utf-8", "replace")
    return proc.returncode, stderr

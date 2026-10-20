"""Video and audio with FFmpeg, run as a separate program (never linked into PixNexa).

FFmpeg is looked for, in this order:
  1. the PIXNEXA_FFMPEG environment variable (full path of ffmpeg / ffmpeg.exe),
  2. <app folder>/ffmpeg/ffmpeg.exe - the copy the installer and the portable zip ship,
  3. ffmpeg on PATH.
When none is found, conversions fail with a clear message instead of crashing.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .base import (
    ConversionError,
    Options,
    ProgressCallback,
    _no_window_flags,
    app_dir,
    atomic_output,
    report,
    run_process,
    target_path,
)

EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
MISSING = ("FFmpeg was not found, so video and audio cannot be converted. Reinstall PixNexa (it includes "
           "FFmpeg), or put ffmpeg.exe in the 'ffmpeg' folder next to PixNexa.exe.")

VIDEO_TARGETS = ("mp4", "webm", "mkv", "mov", "avi", "gif")
AUDIO_TARGETS = ("mp3", "m4a", "wav", "flac", "ogg", "opus")
LOSSY_AUDIO = {".mp3": "mp3", ".m4a": "m4a", ".aac": "m4a", ".ogg": "ogg", ".oga": "ogg", ".opus": "opus"}

CRF = {"h264": {"high": 20, "balanced": 23, "small": 28},
       "h265": {"high": 22, "balanced": 26, "small": 30},
       "vp9": {"high": 28, "balanced": 33, "small": 38}}
GIF_SIZE = {"high": (15, 640), "balanced": (12, 480), "small": (10, 320)}


def find_ffmpeg() -> str | None:
    env = os.environ.get("PIXNEXA_FFMPEG", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for candidate in (app_dir() / "ffmpeg" / EXE, app_dir() / EXE):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffmpeg")


def require_ffmpeg() -> str:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise ConversionError(MISSING)
    return ffmpeg


def run_ffmpeg_bytes(args, data: bytes, timeout: float = 300) -> bytes:
    """Run FFmpeg with `data` on stdin and return stdout (used for single pictures)."""
    try:
        proc = subprocess.run([str(a) for a in args], input=data, capture_output=True, timeout=timeout,
                              creationflags=_no_window_flags())
    except FileNotFoundError:
        raise ConversionError(MISSING) from None
    except subprocess.TimeoutExpired:
        raise ConversionError("FFmpeg took too long.") from None
    if proc.returncode != 0 or not proc.stdout:
        raise ConversionError(_last_error(proc.stderr.decode("utf-8", "replace")) or "FFmpeg failed.")
    return proc.stdout


@dataclass
class MediaInfo:
    duration: float          # seconds, 0 if unknown
    has_video: bool
    has_audio: bool
    width: int = 0
    height: int = 0


_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_SIZE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})")


def probe(src) -> MediaInfo:
    """What FFmpeg says about a file (from `ffmpeg -i`, so no ffprobe is needed)."""
    ffmpeg = require_ffmpeg()
    try:
        proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(src)], capture_output=True, timeout=60,
                              stdin=subprocess.DEVNULL, creationflags=_no_window_flags())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ConversionError(f"FFmpeg could not read the file: {exc}") from None
    text = proc.stderr.decode("utf-8", "replace")
    if "Invalid data found" in text or ("Stream #" not in text):
        raise ConversionError("Not a video or audio file FFmpeg can read.")
    duration = 0.0
    m = _DURATION.search(text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    streams = [line for line in text.splitlines() if line.strip().startswith("Stream #")]
    # cover art in MP3 / M4A files shows up as a video stream with "(attached pic)"
    video = [s for s in streams if "Video:" in s and "attached pic" not in s]
    width = height = 0
    if video:
        sm = _SIZE.search(video[0])
        if sm:
            width, height = int(sm.group(1)), int(sm.group(2))
    return MediaInfo(duration, bool(video), any("Audio:" in s for s in streams), width, height)


def _last_error(stderr: str) -> str:
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    for line in reversed(lines):
        if not line.startswith(("frame=", "size=", "Press [q]", "video:", "[out#")):
            return line[:300]
    return ""


def _scale_filter(options: Options, even: bool = True) -> str:
    h = int(options.max_height_px or 0)
    if h > 0:
        return f"scale=-2:'min({h},trunc(ih/2)*2)'"
    return "scale='trunc(iw/2)*2':'trunc(ih/2)*2'" if even else ""


def _audio_args(fmt: str, bitrate: int) -> list[str]:
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", f"{min(bitrate, 320)}k"]
    if fmt == "m4a":
        return ["-c:a", "aac", "-b:a", f"{bitrate}k", "-movflags", "+faststart"]
    if fmt == "wav":
        return ["-c:a", "pcm_s16le"]
    if fmt == "flac":
        return ["-c:a", "flac"]
    if fmt == "ogg":
        return ["-c:a", "libvorbis", "-b:a", f"{min(bitrate, 320)}k"]
    if fmt == "opus":
        return ["-c:a", "libopus", "-b:a", f"{min(bitrate, 256)}k"]
    raise ConversionError(f"Unsupported audio format: {fmt}")


def _video_args(fmt: str, options: Options, has_audio: bool) -> list[str]:
    quality = options.video_quality if options.video_quality in ("high", "balanced", "small") else "balanced"
    audio_kbps = {"high": 192, "balanced": 160, "small": 128}[quality]
    maps = ["-map", "0:v:0"] + (["-map", "0:a:0"] if has_audio else [])
    if fmt == "gif":
        fps, width = GIF_SIZE[quality]
        if options.max_height_px:
            width = min(width, int(options.max_height_px * 16 / 9))
        graph = (f"fps={fps},scale='min({width},iw)':-1:flags=lanczos,split[a][b];"
                 "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
        return ["-map", "0:v:0", "-vf", graph, "-loop", "0", "-an"]
    if fmt == "webm":
        crf = CRF["vp9"][quality]
        args = maps + ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0", "-row-mt", "1",
                       "-deadline", "good", "-cpu-used", "4", "-pix_fmt", "yuv420p"]
        scale = _scale_filter(options, even=False)
        if scale:
            args += ["-vf", scale]
        return args + (["-c:a", "libopus", "-b:a", f"{audio_kbps}k"] if has_audio else ["-an"])
    if fmt == "avi":
        q = {"high": 3, "balanced": 5, "small": 8}[quality]
        args = maps + ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", str(q), "-vf", _scale_filter(options)]
        return args + (["-c:a", "libmp3lame", "-b:a", f"{audio_kbps}k"] if has_audio else ["-an"])
    # mp4, mov, mkv: H.264 (or H.265) + AAC
    codec = "h265" if options.video_codec == "h265" else "h264"
    crf = CRF[codec][quality]
    args = maps + ["-vf", _scale_filter(options), "-pix_fmt", "yuv420p"]
    if codec == "h265":
        args += ["-c:v", "libx265", "-preset", "medium", "-crf", str(crf), "-x265-params", "log-level=error"]
        if fmt in ("mp4", "mov"):
            args += ["-tag:v", "hvc1"]      # the tag Apple players need
    else:
        args += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf)]
    if fmt in ("mp4", "mov"):
        args += ["-movflags", "+faststart"]
    return args + (["-c:a", "aac", "-b:a", f"{audio_kbps}k"] if has_audio else ["-an"])


def _run(src: Path, dst: Path, codec_args: list[str], duration: float, options: Options,
         progress: ProgressCallback | None) -> Path:
    ffmpeg = require_ffmpeg()
    with atomic_output(dst) as temp:
        args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
                "-map_metadata", "0", "-sn", "-dn", *codec_args, "-progress", "pipe:1", "-nostats", str(temp)]

        def on_line(line: str):
            key, _, value = line.partition("=")
            if key in ("out_time_us", "out_time_ms") and duration > 0:
                try:
                    report(progress, int(value) / 1_000_000 / duration * 0.99)   # both keys are in microseconds
                except ValueError:
                    pass
            elif key == "progress" and value == "end":
                report(progress, 1.0)

        code, stderr = run_process(args, options=options, on_stdout_line=on_line)
        if code != 0:
            raise ConversionError(_last_error(stderr) or f"FFmpeg failed (exit code {code}).")
    return dst


def convert(src, target: str, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """Video -> MP4 / WEBM / MKV / MOV / AVI / GIF or its sound track; audio -> MP3 / M4A / WAV / FLAC / OGG / OPUS."""
    src = Path(src)
    target = target.lower()
    info = probe(src)
    if target in AUDIO_TARGETS:
        if not info.has_audio:
            raise ConversionError("This file has no sound track.")
        codec = ["-map", "0:a:0", "-vn", *_audio_args(target, options.audio_bitrate)]
    elif target in VIDEO_TARGETS:
        if not info.has_video:
            raise ConversionError("This file has no video picture.")
        codec = _video_args(target, options, info.has_audio)
    else:
        raise ConversionError(f"Unsupported target format: {target}")
    dst = target_path(src, target, options)
    return [_run(src, dst, codec, info.duration, options, progress)]


def compress_video(src, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """Re-encode as MP4 (H.264 or H.265) at a CRF preset, optionally scaled down to 1080p / 720p / 480p."""
    src = Path(src)
    info = probe(src)
    if not info.has_video:
        raise ConversionError("This file has no video picture.")
    dst = target_path(src, "mp4", options)
    return [_run(src, dst, _video_args("mp4", options, info.has_audio), info.duration, options, progress)]


def compress_audio(src, options: Options, progress: ProgressCallback | None = None, target: str = "") -> list[Path]:
    """Re-encode at the chosen bitrate; lossless or rare formats become MP3."""
    src = Path(src)
    info = probe(src)
    if not info.has_audio:
        raise ConversionError("This file has no sound track.")
    fmt = target if target in ("mp3", "m4a", "ogg", "opus") else LOSSY_AUDIO.get(src.suffix.lower(), "mp3")
    dst = target_path(src, fmt, options)
    codec = ["-map", "0:a:0", "-vn", *_audio_args(fmt, options.audio_bitrate)]
    return [_run(src, dst, codec, info.duration, options, progress)]

"""Image conversion engine for PixNexa Desktop.

Pure Pillow, no GUI imports, so it can be tested and reused on its own:

    from converter_core import convert_image
    convert_image("photo.jpg", "png")                       # -> photo.png next to the original
    convert_image("logo.png", "ico", out_dir="C:/icons")    # multi-size icon in another folder
"""
from __future__ import annotations

import io
import os
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError


class ConversionError(Exception):
    """A file could not be read or converted. The message is safe to show to the user."""


@dataclass(frozen=True)
class OutputFormat:
    key: str             # what the user picks: "jpg", "png", ...
    label: str           # shown on the button
    extension: str       # file extension written to disk (no dot)
    pil_format: str      # name Pillow uses
    description: str     # one-line hint shown under the format buttons
    has_quality: bool = False


FORMATS = {f.key: f for f in (
    OutputFormat("jpg", "JPG", "jpg", "JPEG", "Small photos. No transparency (it becomes white).", True),
    OutputFormat("png", "PNG", "png", "PNG", "Lossless, keeps transparency. Best for screenshots and logos."),
    OutputFormat("webp", "WEBP", "webp", "WEBP", "Modern web format: small files, keeps transparency.", True),
    OutputFormat("bmp", "BMP", "bmp", "BMP", "Uncompressed bitmap. Large files, no transparency."),
    OutputFormat("gif", "GIF", "gif", "GIF", "256 colors, keeps simple transparency and animation."),
    OutputFormat("tiff", "TIFF", "tiff", "TIFF", "Lossless, for printing and archiving."),
    OutputFormat("ico", "ICO", "ico", "ICO", "Windows icon with 16, 32, 48 and 256 px sizes."),
)}
FORMAT_KEYS = tuple(FORMATS)

# Used for the file dialog and for filtering dropped folders. Pillow decodes by content, so a file
# with an unusual extension still converts if it is a real image.
INPUT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".jpe", ".jfif", ".bmp", ".dib", ".gif", ".tif", ".tiff",
                    ".ico", ".webp", ".tga", ".pcx", ".ppm", ".pgm", ".pbm")

ICO_SIZES = (16, 32, 48, 256)
DEFAULT_QUALITY = 90
_WHITE = (255, 255, 255)


# ───────────────────────── small helpers ─────────────────────────

def is_supported_input(path) -> bool:
    return Path(path).suffix.lower() in INPUT_EXTENSIONS


def list_images(folder) -> list[Path]:
    """Image files directly inside a folder (not its sub-folders), sorted by name."""
    folder = Path(folder)
    try:
        return sorted((p for p in folder.iterdir() if p.is_file() and is_supported_input(p)),
                      key=lambda p: p.name.lower())
    except OSError:
        return []


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def unique_path(path: Path) -> Path:
    """photo.png -> photo (1).png -> photo (2).png ... the first name that is free."""
    path = Path(path)
    if not path.exists():
        return path
    for i in range(1, 10_000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise ConversionError("Too many files with the same name in the output folder.")


def output_path_for(src, fmt_key: str, out_dir=None, overwrite: bool = False) -> Path:
    """Where the converted file will be written."""
    fmt = _get_format(fmt_key)
    src = Path(src)
    folder = Path(out_dir) if out_dir else src.parent
    dst = folder / f"{src.stem}.{fmt.extension}"
    if overwrite and not _same_file(src, dst):
        return dst
    return unique_path(dst)   # never overwrite by accident, and never overwrite the source itself


_ALIASES = {"jpeg": "jpg", "jpe": "jpg", "jfif": "jpg", "tif": "tiff"}


def _get_format(fmt_key: str) -> OutputFormat:
    key = str(fmt_key).strip().lower().lstrip(".")
    key = _ALIASES.get(key, key)
    try:
        return FORMATS[key]
    except KeyError:
        raise ConversionError(f"Unsupported target format: {fmt_key!r}") from None


@dataclass(frozen=True)
class ImageInfo:
    format: str
    width: int
    height: int
    size_bytes: int


def describe_image(path) -> ImageInfo:
    """Read just the header of an image. Raises ConversionError if it is not a readable image."""
    path = Path(path)
    try:
        with Image.open(path) as img:
            return ImageInfo(img.format or "?", img.width, img.height, path.stat().st_size)
    except UnidentifiedImageError:
        raise ConversionError("Not a supported image file.") from None
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ConversionError(_friendly(exc)) from None


def _friendly(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return "Permission denied."
    if isinstance(exc, FileNotFoundError):
        return "File not found."
    if isinstance(exc, Image.DecompressionBombError):
        return "The image is too large to open safely."
    if isinstance(exc, MemoryError):
        return "Not enough memory to convert this image."
    return str(exc) or exc.__class__.__name__


# ───────────────────────── pixel preparation ─────────────────────────

def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info


def _normalize(img: Image.Image) -> Image.Image:
    """Bring unusual modes (16-bit, CMYK, palette, 1-bit ...) to RGB / RGBA / L / LA."""
    if img.mode.startswith("I;16"):
        img = img.convert("I")
    if img.mode == "I":
        img = img.point(lambda v: v * (1 / 256)).convert("L")     # 16-bit -> 8-bit
    elif img.mode == "F":
        img = img.convert("L")
    if img.mode not in ("RGB", "RGBA", "L", "LA"):
        img = img.convert("RGBA" if _has_alpha(img) else "RGB")
    return img


def _flatten(img: Image.Image, background=_WHITE) -> Image.Image:
    """Remove transparency by painting the image on a solid background (JPEG and BMP cannot store it)."""
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, background + (255,))
        base.alpha_composite(rgba)
        return base.convert("RGB")
    return img.convert("RGB")


def _fit_square(img: Image.Image, size: int) -> Image.Image:
    """Fit the image into a transparent size x size canvas, keeping its aspect ratio."""
    rgba = img.convert("RGBA")
    ratio = min(size / rgba.width, size / rgba.height)
    width, height = max(1, round(rgba.width * ratio)), max(1, round(rgba.height * ratio))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(rgba.resize((width, height), Image.LANCZOS), ((size - width) // 2, (size - height) // 2))
    return canvas


def build_ico(img: Image.Image, sizes=ICO_SIZES) -> bytes:
    """Build a multi-resolution .ico with PNG-compressed images (supported since Windows Vista).

    Written by hand instead of Pillow's ICO writer so that non-square images are fitted (not stretched)
    and every standard size is always present, even for small sources.
    """
    pngs = []
    for size in sizes:
        buf = io.BytesIO()
        _fit_square(img, size).save(buf, format="PNG", optimize=True)
        pngs.append((size, buf.getvalue()))

    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, len(pngs)))                  # ICONDIR: reserved, type = icon, count
    offset = 6 + 16 * len(pngs)
    for size, data in pngs:
        dim = 0 if size >= 256 else size                              # 0 means 256 in the ICO format
        out.write(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    for _, data in pngs:
        out.write(data)
    return out.getvalue()


# ───────────────────────── conversion ─────────────────────────

def convert_image(src, fmt_key: str, out_dir=None, *, quality: int = DEFAULT_QUALITY,
                  overwrite: bool = False) -> Path:
    """Convert one image and return the path of the new file.

    src        path of the source image (any format Pillow can read)
    fmt_key    "jpg", "png", "webp", "bmp", "gif", "tiff" or "ico"
    out_dir    folder for the result; default: next to the original
    quality    1-100, used by jpg and webp
    overwrite  replace an existing file of the same name; otherwise "name (1).ext" is used
    """
    fmt = _get_format(fmt_key)
    src = Path(src)
    if not src.is_file():
        raise ConversionError("File not found.")
    quality = max(1, min(100, int(quality)))

    dst = output_path_for(src, fmt.key, out_dir, overwrite)
    temp = dst.with_name(dst.name + ".part")      # write next to the target, then rename: no half-written files
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as img:
            animated = getattr(img, "is_animated", False) and fmt.key in ("gif", "webp")
            if animated:
                _save_animated(img, temp, fmt, quality)
            else:
                img.load()
                _save_still(img, temp, fmt, quality)
        os.replace(temp, dst)
    except ConversionError:
        _remove(temp)
        raise
    except UnidentifiedImageError:
        _remove(temp)
        raise ConversionError("Not a supported image file.") from None
    except Exception as exc:                       # Pillow raises many kinds of errors for damaged files
        _remove(temp)
        raise ConversionError(_friendly(exc)) from exc
    return dst


def _remove(path: Path):
    try:
        path.unlink()
    except OSError:
        pass


def _save_still(img: Image.Image, target: Path, fmt: OutputFormat, quality: int):
    icc = img.info.get("icc_profile") if img.mode in ("RGB", "RGBA", "L", "LA", "P", "PA") else None
    img = ImageOps.exif_transpose(img) or img      # honour the camera's rotation flag
    img = _normalize(img)

    if fmt.key == "ico":
        target.write_bytes(build_ico(img))
    elif fmt.key == "jpg":
        _flatten(img).save(target, format="JPEG", quality=quality, optimize=True, icc_profile=icc)
    elif fmt.key == "bmp":
        _flatten(img).save(target, format="BMP")
    elif fmt.key == "png":
        img.save(target, format="PNG", optimize=True, icc_profile=icc)
    elif fmt.key == "webp":
        img.save(target, format="WEBP", quality=quality, icc_profile=icc)
    elif fmt.key == "gif":
        img.convert("RGBA" if _has_alpha(img) else "RGB").save(target, format="GIF")
    elif fmt.key == "tiff":
        img.save(target, format="TIFF", compression="tiff_lzw", icc_profile=icc)
    else:  # pragma: no cover - guarded by _get_format
        raise ConversionError(f"Unsupported target format: {fmt.key}")


def _save_animated(img: Image.Image, target: Path, fmt: OutputFormat, quality: int):
    """GIF <-> WEBP keep every frame and its timing; other targets use only the first frame."""
    frames, durations = [], []
    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert("RGBA"))
        durations.append(frame.info.get("duration", 100))
    options = {"save_all": True, "append_images": frames[1:], "duration": durations,
               "loop": img.info.get("loop", 0)}
    if fmt.key == "gif":
        frames[0].save(target, format="GIF", disposal=2, **options)
    else:
        frames[0].save(target, format="WEBP", quality=quality, **options)

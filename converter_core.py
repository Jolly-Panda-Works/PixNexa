"""Image conversion engine for PixNexa Desktop.

Pillow (plus pi-heif for reading HEIC / HEIF), no GUI imports, so it can be tested and reused on its own:

    from converter_core import convert_image
    convert_image("photo.jpg", "png")                       # -> photo.png next to the original
    convert_image("logo.png", "ico", out_dir="C:/icons")    # multi-size icon in another folder
    convert_image("big.jpg", "jpg", target_kb=300, suffix="-compressed")   # smaller file, at most ~300 KB

Every other kind of file (PDF, video, documents, archives, ...) is handled by the `pixnexa_engines` package,
which builds on the helpers here.
"""
from __future__ import annotations

import io
import os
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

try:  # HEIC / HEIF reading (decode only; the permissive pi-heif build has no GPL encoder in it)
    import pi_heif

    pi_heif.register_heif_opener()
    HEIF_READ = True
except Exception:  # pragma: no cover - depends on the installed packages
    HEIF_READ = False


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
    OutputFormat("avif", "AVIF", "avif", "AVIF", "Newest web format: the smallest files, keeps transparency.", True),
    OutputFormat("heic", "HEIC", "heic", "HEIF", "iPhone photo format: small files. No transparency.", True),
    OutputFormat("bmp", "BMP", "bmp", "BMP", "Uncompressed bitmap. Large files, no transparency."),
    OutputFormat("gif", "GIF", "gif", "GIF", "256 colors, keeps simple transparency and animation."),
    OutputFormat("tiff", "TIFF", "tiff", "TIFF", "Lossless, for printing and archiving."),
    OutputFormat("ico", "ICO", "ico", "ICO", "Windows icon with 16, 32, 48 and 256 px sizes."),
    OutputFormat("tga", "TGA", "tga", "TGA", "Targa, used by games and 3D tools. Keeps transparency."),
    OutputFormat("pdf", "PDF", "pdf", "PDF", "A PDF document with the picture as its page."),
)}
FORMAT_KEYS = tuple(FORMATS)
LOSSY_KEYS = ("jpg", "webp", "avif", "heic")

# Used for the file dialog and for filtering dropped folders. Pillow decodes by content, so a file
# with an unusual extension still converts if it is a real image.
INPUT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".jpe", ".jfif", ".bmp", ".dib", ".gif", ".tif", ".tiff",
                    ".ico", ".webp", ".tga", ".pcx", ".ppm", ".pgm", ".pbm", ".pnm",
                    ".avif", ".heic", ".heif", ".hif", ".apng", ".psd", ".jp2", ".j2k", ".jpx", ".jpf",
                    ".icns", ".cur", ".dds", ".qoi", ".sgi", ".rgb", ".xbm", ".mpo")

ICO_SIZES = (16, 32, 48, 256)
DEFAULT_QUALITY = 90
_WHITE = (255, 255, 255)
_SOURCE_FORMAT = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png", "WEBP": "webp", "AVIF": "avif", "HEIF": "heic",
                  "BMP": "bmp", "GIF": "gif", "TIFF": "tiff", "ICO": "ico", "TGA": "tga"}


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


def output_path_for(src, fmt_key: str, out_dir=None, overwrite: bool = False, suffix: str = "") -> Path:
    """Where the converted file will be written."""
    fmt = _get_format(fmt_key)
    src = Path(src)
    folder = Path(out_dir) if out_dir else src.parent
    dst = folder / f"{src.stem}{suffix}.{fmt.extension}"
    if overwrite and not _same_file(src, dst):
        return dst
    return unique_path(dst)   # never overwrite by accident, and never overwrite the source itself


_ALIASES = {"jpeg": "jpg", "jpe": "jpg", "jfif": "jpg", "tif": "tiff", "heif": "heic", "targa": "tga"}


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
            if img.format == "PDF":     # Pillow can write PDFs but not read them as pictures
                raise ConversionError("Not a supported image file.")
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


def resized_size(width: int, height: int, resize) -> tuple[int, int]:
    """The new size for a resize setting: None, ("max", w, h) - fit inside, never enlarge - or ("percent", p)."""
    if not resize:
        return width, height
    kind = resize[0]
    if kind == "percent":
        factor = max(1, int(resize[1])) / 100
    elif kind == "max":
        max_w, max_h = int(resize[1] or 0), int(resize[2] or 0)
        factor = 1.0
        if max_w > 0:
            factor = min(factor, max_w / width)
        if max_h > 0:
            factor = min(factor, max_h / height)
    else:
        return width, height
    return max(1, round(width * factor)), max(1, round(height * factor))


def _apply_edits(img: Image.Image, resize=None, grayscale=False) -> Image.Image:
    size = resized_size(img.width, img.height, resize)
    if size != img.size:
        img = img.resize(size, Image.LANCZOS)
    if grayscale:
        img = img.convert("LA" if _has_alpha(img) else "L")
    return img


# ───────────────────────── encoding ─────────────────────────

def _encode_still(img: Image.Image, fmt: OutputFormat, quality: int, icc=None, exif=None,
                  palette: bool = False) -> bytes:
    """Encode an already prepared (normalized, edited) image in memory."""
    buf = io.BytesIO()
    extra = {}
    if icc:
        extra["icc_profile"] = icc
    if exif and fmt.key in ("jpg", "png", "webp", "avif"):
        extra["exif"] = exif
    if fmt.key == "ico":
        return build_ico(img)
    if fmt.key == "heic":
        from pixnexa_engines.heif import encode_heic
        return encode_heic(_flatten(img), quality)
    if fmt.key == "pdf":
        from pixnexa_engines.pdf import image_to_pdf_bytes
        return image_to_pdf_bytes(img, quality)
    if fmt.key == "jpg":
        _flatten(img).save(buf, format="JPEG", quality=quality, optimize=True, **extra)
    elif fmt.key == "bmp":
        _flatten(img).save(buf, format="BMP")
    elif fmt.key == "png":
        if palette and img.mode not in ("L",):
            img = _quantize(img)
        img.save(buf, format="PNG", optimize=True, **extra)
    elif fmt.key == "webp":
        img.save(buf, format="WEBP", quality=quality, method=6, **extra)
    elif fmt.key == "avif":
        img.save(buf, format="AVIF", quality=quality, **extra)
    elif fmt.key == "gif":
        img.convert("RGBA" if _has_alpha(img) else "RGB").save(buf, format="GIF", optimize=True)
    elif fmt.key == "tiff":
        img.save(buf, format="TIFF", compression="tiff_lzw", **extra)
    elif fmt.key == "tga":
        img.convert("RGBA" if _has_alpha(img) else ("L" if img.mode == "L" else "RGB")).save(
            buf, format="TGA", compression="tga_rle")
    else:  # pragma: no cover - guarded by _get_format
        raise ConversionError(f"Unsupported target format: {fmt.key}")
    return buf.getvalue()


def _quantize(img: Image.Image) -> Image.Image:
    """256 colours with dithering; keeps transparency (much smaller PNGs for graphics and screenshots)."""
    if _has_alpha(img):
        return img.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
    return img.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)


def _encode_to_target(img: Image.Image, fmt: OutputFormat, quality: int, target_bytes: int, **kw) -> bytes:
    """Find the best quality (binary search) whose file fits in target_bytes; shrink the picture if even the
    lowest quality is too big. Returns the smallest result found if the target cannot be reached."""
    best = None
    work = img
    for _attempt in range(8):
        if fmt.key in LOSSY_KEYS:
            low, high, fit = 5, max(5, quality), None
            data = _encode_still(work, fmt, high, **kw)
            if len(data) <= target_bytes:
                return data
            smallest = _encode_still(work, fmt, low, **kw)
            if len(smallest) <= target_bytes:
                fit = smallest
                while high - low > 2:
                    mid = (low + high) // 2
                    data = _encode_still(work, fmt, mid, **kw)
                    if len(data) <= target_bytes:
                        low, fit = mid, data
                    else:
                        high = mid
                return fit
            candidate = smallest
        else:
            candidate = _encode_still(work, fmt, quality, **kw)
            if len(candidate) > target_bytes and fmt.key in ("png", "gif", "tiff") and not kw.get("palette"):
                kw = dict(kw, palette=True)
                candidate = min(candidate, _encode_still(work, fmt, quality, **kw), key=len)
            if len(candidate) <= target_bytes:
                return candidate
        if best is None or len(candidate) < len(best):
            best = candidate
        if work.width <= 16 or work.height <= 16 or fmt.key == "ico":
            break
        work = work.resize((max(1, round(work.width * 0.8)), max(1, round(work.height * 0.8))), Image.LANCZOS)
    return best


# ───────────────────────── conversion ─────────────────────────

def convert_image(src, fmt_key: str, out_dir=None, *, quality: int = DEFAULT_QUALITY,
                  overwrite: bool = False, resize=None, grayscale: bool = False, strip_metadata: bool = True,
                  target_kb: int = 0, png_palette: bool = False, suffix: str = "",
                  never_bigger: bool = False) -> Path:
    """Convert one image and return the path of the new file.

    src            path of the source image (any format Pillow or pi-heif can read)
    fmt_key        one of FORMAT_KEYS: "jpg", "png", "webp", "avif", "heic", "bmp", "gif", "tiff", "ico",
                   "tga", "pdf"  (HEIC output needs FFmpeg, see pixnexa_engines.media)
    out_dir        folder for the result; default: next to the original
    quality        1-100, used by jpg, webp, avif, heic (and pictures inside a PDF)
    overwrite      replace an existing file of the same name; otherwise "name (1).ext" is used
    resize         None, ("max", width, height) to fit inside a box (never enlarges), or ("percent", 50)
    grayscale      convert to shades of gray
    strip_metadata drop EXIF (camera, GPS, date); the colour profile is always kept
    target_kb      aim for a file of at most this many KB (lower quality, then a smaller picture)
    png_palette    PNG / GIF / TIFF: reduce to 256 colours (much smaller graphics)
    suffix         added to the name: "photo-compressed.jpg"
    never_bigger   when the result is not smaller than the source in the same format, keep the original bytes
    """
    fmt = _get_format(fmt_key)
    src = Path(src)
    if not src.is_file():
        raise ConversionError("File not found.")
    quality = max(1, min(100, int(quality)))

    dst = output_path_for(src, fmt.key, out_dir, overwrite, suffix)
    temp = dst.with_name(dst.name + ".part")      # write next to the target, then rename: no half-written files
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as img:
            if img.format == "PDF":
                raise ConversionError("Not a supported image file.")
            source_key = _SOURCE_FORMAT.get(img.format or "")
            animated = getattr(img, "is_animated", False) and fmt.key in ("gif", "webp")
            if animated:
                _save_animated(img, temp, fmt, quality, resize, grayscale)
            else:
                img.load()
                data = _encode_prepared(img, fmt, quality, resize, grayscale, strip_metadata, target_kb,
                                        png_palette)
                temp.write_bytes(data)
        if (never_bigger and source_key == fmt.key and not resize and not grayscale
                and temp.stat().st_size >= src.stat().st_size):
            temp.write_bytes(src.read_bytes())    # it could not be made smaller: keep the original as it was
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


def prepare_image(img: Image.Image, resize=None, grayscale=False) -> Image.Image:
    """Rotate by the camera's orientation flag, bring the mode to RGB(A)/L(A), apply resize / grayscale."""
    img = ImageOps.exif_transpose(img) or img      # honour the camera's rotation flag
    img = _normalize(img)
    return _apply_edits(img, resize, grayscale)


def _encode_prepared(img, fmt, quality, resize, grayscale, strip_metadata, target_kb, png_palette) -> bytes:
    icc = img.info.get("icc_profile") if img.mode in ("RGB", "RGBA", "L", "LA", "P", "PA") else None
    exif = None
    if not strip_metadata:
        try:
            ex = img.getexif()
            if len(ex):
                ex[0x0112] = 1                     # the pixels are rotated upright below
                exif = ex.tobytes()
        except Exception:
            exif = None
    img = prepare_image(img, resize, grayscale)
    if grayscale and icc:
        icc = None                                 # an RGB profile does not fit gray pixels
    kw = {"icc": icc, "exif": exif, "palette": png_palette}
    if target_kb and target_kb > 0:
        return _encode_to_target(img, fmt, quality, int(target_kb) * 1024, **kw)
    return _encode_still(img, fmt, quality, **kw)


def _save_animated(img: Image.Image, target: Path, fmt: OutputFormat, quality: int, resize=None, grayscale=False):
    """GIF <-> WEBP keep every frame and its timing; other targets use only the first frame."""
    frames, durations = [], []
    for frame in ImageSequence.Iterator(img):
        durations.append(frame.info.get("duration", img.info.get("duration", 100)) or 100)
        frame = _apply_edits(frame.convert("RGBA"), resize, False)
        if grayscale:
            frame = frame.convert("LA").convert("RGBA")
        frames.append(frame)
    options = {"save_all": True, "append_images": frames[1:], "duration": durations,
               "loop": img.info.get("loop", 0)}
    if fmt.key == "gif":
        frames[0].save(target, format="GIF", disposal=2, **options)
    else:
        frames[0].save(target, format="WEBP", quality=quality, **options)

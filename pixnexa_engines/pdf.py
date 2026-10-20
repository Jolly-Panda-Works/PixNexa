"""PDF: pages to images (pypdfium2), text, merge / split / page ranges and compression (pikepdf),
pictures to PDF (pikepdf, JPEG photos are embedded as they are, without re-encoding)."""
from __future__ import annotations

import io
import math
import re
import shutil
import zlib
from pathlib import Path

from PIL import Image, ImageOps

from .base import (
    ConversionError,
    Options,
    ProgressCallback,
    atomic_folder,
    atomic_output,
    check_cancel,
    report,
    target_folder,
    target_path,
)

PAGE_SIZES = {"a4": (595.28, 841.89), "letter": (612.0, 792.0)}
MAX_RENDER_PIXELS = 120_000_000          # one page image at most ~120 MP (a huge DPI on a poster PDF)
_PASSWORD = "This PDF is password-protected. Remove the password first (open it and save an unprotected copy)."


# ───────────────────────── page ranges ─────────────────────────

def parse_pages(text: str, count: int) -> list[int]:
    """'' -> every page; '1-3, 5, 8-' -> zero-based page indices, in the order given, without repeats."""
    text = (text or "").strip()
    if not text or text.lower() == "all":
        return list(range(count))
    pages: list[int] = []
    for part in re.split(r"[,;\s]+", text):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if m:
            start = int(m.group(1)) if m.group(1) else 1
            end = int(m.group(2)) if m.group(2) else count
        elif part.isdigit():
            start = end = int(part)
        else:
            raise ConversionError(f"Page range not understood: {part!r}. Use e.g. 1-3, 5")
        if start < 1 or end < start:
            raise ConversionError(f"Page range not understood: {part!r}. Use e.g. 1-3, 5")
        for p in range(start, min(end, count) + 1):
            if p - 1 not in pages:
                pages.append(p - 1)
    if not pages:
        raise ConversionError(f"The PDF has only {count} page{'s' if count != 1 else ''}.")
    return pages


def _open_pdfium(src: Path):
    import pypdfium2 as pdfium
    try:
        return pdfium.PdfDocument(str(src))
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise ConversionError(_PASSWORD) from None
        raise ConversionError("Not a readable PDF file.") from None


def _open_pikepdf(src: Path):
    import pikepdf
    try:
        return pikepdf.open(str(src))
    except pikepdf.PasswordError:
        raise ConversionError(_PASSWORD) from None
    except (pikepdf.PdfError, OSError, ValueError) as exc:
        raise ConversionError(f"Not a readable PDF file ({exc.__class__.__name__}).") from None


def page_count(src) -> int:
    doc = _open_pdfium(Path(src))
    try:
        return len(doc)
    finally:
        doc.close()


def thumbnail(src, size: int) -> Image.Image | None:
    """The first page, small. None when the PDF cannot be drawn."""
    try:
        doc = _open_pdfium(Path(src))
    except ConversionError:
        return None
    try:
        page = doc[0]
        w, h = page.get_size()
        img = page.render(scale=size * 2 / max(w, h, 1)).to_pil()
        page.close()
        return img
    except Exception:
        return None
    finally:
        doc.close()


# ───────────────────────── PDF -> images / text ─────────────────────────

def render(src, fmt: str, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """Every page (or the page range) as PNG or JPG at options.dpi. One page: next to the PDF; several: a folder."""
    src = Path(src)
    fmt = "jpg" if fmt in ("jpg", "jpeg") else "png"
    doc = _open_pdfium(src)
    try:
        pages = parse_pages(options.pages, len(doc))
        single = len(pages) == 1

        def draw(index: int, path: Path):
            page = doc[index]
            try:
                w, h = page.get_size()
                scale = options.dpi / 72
                if w * h * scale * scale > MAX_RENDER_PIXELS:
                    scale = math.sqrt(MAX_RENDER_PIXELS / (w * h))
                img = page.render(scale=scale, may_draw_forms=True).to_pil()
            finally:
                page.close()
            if fmt == "jpg":
                img.convert("RGB").save(path, format="JPEG", quality=options.quality, optimize=True,
                                        dpi=(options.dpi, options.dpi))
            else:
                img.save(path, format="PNG", optimize=False, dpi=(options.dpi, options.dpi))

        if single:
            stem = src.stem if len(doc) == 1 else f"{src.stem}-{pages[0] + 1}"
            dst = target_path(src, fmt, options, stem=stem)
            with atomic_output(dst) as temp:
                draw(pages[0], temp)
            report(progress, 1)
            return [dst]

        folder = target_folder(src, options)
        digits = max(3, len(str(len(doc))))
        with atomic_folder(folder) as temp:
            for n, index in enumerate(pages):
                check_cancel(options)
                draw(index, temp / f"{src.stem}-{index + 1:0{digits}d}.{fmt}")
                report(progress, (n + 1) / len(pages))
        return [folder]
    finally:
        doc.close()


def to_text(src, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    src = Path(src)
    doc = _open_pdfium(src)
    try:
        pages = parse_pages(options.pages, len(doc))
        parts = []
        for n, index in enumerate(pages):
            check_cancel(options)
            page = doc[index]
            textpage = page.get_textpage()
            parts.append(textpage.get_text_bounded().replace("\r\n", "\n").strip())
            textpage.close()
            page.close()
            report(progress, (n + 1) / len(pages))
    finally:
        doc.close()
    text = "\n\n\f".join(parts).strip()
    if not text:
        raise ConversionError("This PDF has no text layer (it is probably scanned pictures).")
    dst = target_path(src, "txt", options)
    with atomic_output(dst) as temp:
        temp.write_text(text + "\n", encoding="utf-8")
    return [dst]


# ───────────────────────── merge / split / ranges ─────────────────────────

def _save(pdf, path: Path):
    import pikepdf
    pdf.save(str(path), compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)


def merge(sources, dst: Path, options: Options, progress: ProgressCallback | None = None) -> Path:
    import pikepdf
    sources = [Path(s) for s in sources]
    out = pikepdf.Pdf.new()
    opened = []
    try:
        for n, s in enumerate(sources):
            check_cancel(options)
            pdf = _open_pikepdf(s)
            opened.append(pdf)
            out.pages.extend(pdf.pages)
            report(progress, (n + 1) / (len(sources) + 1))
        with atomic_output(dst) as temp:
            _save(out, temp)
    finally:
        for pdf in opened:
            pdf.close()
    report(progress, 1)
    return dst


def split(src, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """One PDF per page (of the page range) in a new folder."""
    import pikepdf
    src = Path(src)
    pdf = _open_pikepdf(src)
    try:
        pages = parse_pages(options.pages, len(pdf.pages))
        folder = target_folder(src, options, f"{src.stem}{options.suffix} (pages)")
        digits = max(3, len(str(len(pdf.pages))))
        with atomic_folder(folder) as temp:
            for n, index in enumerate(pages):
                check_cancel(options)
                one = pikepdf.Pdf.new()
                one.pages.append(pdf.pages[index])
                _save(one, temp / f"{src.stem}-{index + 1:0{digits}d}.pdf")
                report(progress, (n + 1) / len(pages))
    finally:
        pdf.close()
    return [folder]


def extract_pages(src, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """The pages of the range, in that order, as one new PDF."""
    import pikepdf
    src = Path(src)
    if not (options.pages or "").strip():
        raise ConversionError("Enter the pages to keep, e.g. 1-3, 5.")
    pdf = _open_pikepdf(src)
    try:
        pages = parse_pages(options.pages, len(pdf.pages))
        out = pikepdf.Pdf.new()
        for index in pages:
            out.pages.append(pdf.pages[index])
        label = re.sub(r"[^0-9,\- ]", "", options.pages).replace(" ", "")[:40] or "pages"
        dst = target_path(src, "pdf", options, stem=f"{src.stem} (pages {label})")
        with atomic_output(dst) as temp:
            _save(out, temp)
    finally:
        pdf.close()
    report(progress, 1)
    return [dst]


# ───────────────────────── pictures -> PDF ─────────────────────────

def _image_stream(pdf, img: Image.Image, quality: int, raw_jpeg: bytes | None = None):
    """A PDF image XObject for a prepared (upright, RGB/RGBA/L/LA) picture."""
    import pikepdf
    name = pikepdf.Name
    if raw_jpeg is not None:
        cs = name.DeviceGray if img.mode == "L" else name.DeviceRGB
        return pikepdf.Stream(pdf, raw_jpeg, Type=name.XObject, Subtype=name.Image, Width=img.width,
                              Height=img.height, ColorSpace=cs, BitsPerComponent=8, Filter=name.DCTDecode)
    alpha = None
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A")
        if alpha.getextrema() == (255, 255):
            alpha = None
        img = img.convert("RGB" if img.mode == "RGBA" else "L")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    gray = img.mode == "L"
    cs = name.DeviceGray if gray else name.DeviceRGB
    photo = img.getcolors(4096) is None
    if photo:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        stream = pikepdf.Stream(pdf, buf.getvalue(), Filter=name.DCTDecode)
    else:
        stream = pikepdf.Stream(pdf, zlib.compress(img.tobytes(), 9), Filter=name.FlateDecode)
    stream.Type, stream.Subtype = name.XObject, name.Image
    stream.Width, stream.Height, stream.ColorSpace, stream.BitsPerComponent = img.width, img.height, cs, 8
    if alpha is not None:
        mask = pikepdf.Stream(pdf, zlib.compress(alpha.tobytes(), 9), Type=name.XObject, Subtype=name.Image,
                              Width=alpha.width, Height=alpha.height, ColorSpace=name.DeviceGray,
                              BitsPerComponent=8, Filter=name.FlateDecode)
        stream.SMask = mask
    return stream


def _add_image_page(pdf, xobj, px_w: int, px_h: int, page_size: str, dpi_info=None):
    import pikepdf
    if page_size in PAGE_SIZES:
        pw, ph = PAGE_SIZES[page_size]
        if (px_w > px_h) != (pw > ph):            # landscape pictures get a landscape page
            pw, ph = ph, pw
        margin = 28.35                            # 1 cm
        scale = min((pw - 2 * margin) / px_w, (ph - 2 * margin) / px_h)
        w, h = px_w * scale, px_h * scale
        x, y = (pw - w) / 2, (ph - h) / 2
    else:
        dpi = 96.0
        if dpi_info:
            try:
                d = float(dpi_info[0])
                if 30 <= d <= 2400:
                    dpi = d
            except (TypeError, ValueError, IndexError):
                pass
        w, h = px_w * 72 / dpi, px_h * 72 / dpi
        if max(w, h) > 14400:                     # PDF's page size limit (200 inches)
            f = 14400 / max(w, h)
            w, h = w * f, h * f
        pw, ph, x, y = w, h, 0.0, 0.0
    content = f"q {w:.4f} 0 0 {h:.4f} {x:.4f} {y:.4f} cm /Im0 Do Q".encode()
    page = pikepdf.Dictionary(Type=pikepdf.Name.Page, MediaBox=[0, 0, round(pw, 4), round(ph, 4)],
                              Resources=pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=xobj)),
                              Contents=pikepdf.Stream(pdf, content))
    pdf.pages.append(pikepdf.Page(page))


def _load_for_pdf(path: Path, options: Options):
    """(prepared picture, original JPEG bytes when they can be embedded unchanged, dpi)."""
    import converter_core as core
    try:
        with Image.open(path) as im:
            if im.format == "PDF":
                raise ConversionError("Not a supported image file.")
            dpi = im.info.get("dpi")
            orientation = im.getexif().get(0x0112, 1) if hasattr(im, "getexif") else 1
            raw = None
            resize = _resize_of(options)
            if (im.format == "JPEG" and im.mode in ("RGB", "L") and orientation in (0, 1) and not resize
                    and not options.grayscale):
                raw = path.read_bytes()
            im.load()
            img = core.prepare_image(im, resize, options.grayscale)
            return img, raw, dpi
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"{path.name}: not a readable image ({exc.__class__.__name__}).") from None


def _resize_of(options: Options):
    if options.resize_mode == "max" and (options.max_width or options.max_height):
        return ("max", options.max_width, options.max_height)
    if options.resize_mode == "percent" and options.percent != 100:
        return ("percent", options.percent)
    return None


def images_to_pdf(sources, dst: Path, options: Options, progress: ProgressCallback | None = None) -> Path:
    """All pictures as the pages of one PDF, in the order given."""
    import pikepdf
    sources = [Path(s) for s in sources]
    pdf = pikepdf.Pdf.new()
    for n, path in enumerate(sources):
        check_cancel(options)
        img, raw, dpi = _load_for_pdf(path, options)
        xobj = _image_stream(pdf, img, options.quality, raw)
        _add_image_page(pdf, xobj, img.width, img.height, options.page_size, dpi)
        report(progress, (n + 1) / (len(sources) + 1))
    with atomic_output(dst) as temp:
        _save(pdf, temp)
    report(progress, 1)
    return dst


def image_to_pdf_bytes(img: Image.Image, quality: int = 90, page_size: str = "image") -> bytes:
    """One prepared picture as a one-page PDF (used by converter_core for the PDF target)."""
    import pikepdf
    pdf = pikepdf.Pdf.new()
    _add_image_page(pdf, _image_stream(pdf, img, quality), img.width, img.height, page_size, img.info.get("dpi"))
    buf = io.BytesIO()
    pdf.save(buf, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return buf.getvalue()


# ───────────────────────── compression ─────────────────────────

def _mul(m, n):
    """PDF matrix product m x n (6-element [a b c d e f])."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def _drawn_sizes(pdf) -> dict:
    """Largest size (points) each picture is drawn at, by following q / Q / cm / Do through pages and forms."""
    import pikepdf
    sizes: dict = {}

    def walk(stream_owner, resources, ctm, depth):
        if depth > 6:
            return
        try:
            ops = pikepdf.parse_content_stream(stream_owner, "q Q cm Do")
        except Exception:
            return
        stack, current = [], ctm
        xobjects = resources.get("/XObject", {}) if resources is not None else {}
        for operands, op in ops:
            op = str(op)
            if op == "q":
                stack.append(current)
            elif op == "Q":
                current = stack.pop() if stack else ctm
            elif op == "cm" and len(operands) == 6:
                try:
                    current = _mul(tuple(float(v) for v in operands), current)
                except (TypeError, ValueError):
                    pass
            elif op == "Do" and operands:
                try:
                    xobj = xobjects.get(str(operands[0]))
                except Exception:
                    xobj = None
                if xobj is None:
                    continue
                subtype = xobj.get("/Subtype")
                if subtype == "/Image":
                    w = math.hypot(current[0], current[1])
                    h = math.hypot(current[2], current[3])
                    key = xobj.objgen
                    old = sizes.get(key, (0, 0))
                    sizes[key] = (max(old[0], w), max(old[1], h))
                elif subtype == "/Form":
                    matrix = tuple(float(v) for v in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0]))
                    walk(xobj, xobj.get("/Resources", resources), _mul(matrix, current), depth + 1)

    for page in pdf.pages:
        try:
            walk(page, page.obj.get("/Resources"), (1, 0, 0, 1, 0, 0), 0)
        except Exception:
            continue
    return sizes


def compress(src, options: Options, progress: ProgressCallback | None = None) -> tuple[list[Path], str]:
    """Recompress pictures as JPEG at options.quality, scale them down to options.dpi where they are drawn,
    remove thumbnails, private application data and (optionally) metadata, and write object streams.
    Returns (outputs, note). The result is never bigger than the original."""
    import pikepdf
    src = Path(src)
    pdf = _open_pikepdf(src)
    try:
        drawn = _drawn_sizes(pdf)
        largest_page = (612.0, 792.0)
        try:
            boxes = [tuple(float(v) for v in p.mediabox) for p in pdf.pages]
            largest_page = max(((b[2] - b[0], b[3] - b[1]) for b in boxes), key=lambda s: s[0] * s[1])
        except Exception:
            pass

        masks = set()
        images = []
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == "/Image":
                images.append(obj)
                for key in ("/SMask", "/Mask"):
                    m = obj.get(key)
                    if isinstance(m, pikepdf.Stream):
                        masks.add(m.objgen)

        for n, obj in enumerate(images):
            check_cancel(options)
            report(progress, n / max(1, len(images)) * 0.9)
            if obj.objgen in masks:
                continue
            try:
                _recompress_image(pdf, obj, drawn.get(obj.objgen, largest_page), options)
            except Exception:
                continue                           # a picture we cannot handle stays exactly as it was

        for page in pdf.pages:
            for key in ("/Thumb", "/PieceInfo"):
                if key in page.obj:
                    del page.obj[key]
        if "/PieceInfo" in pdf.Root:
            del pdf.Root["/PieceInfo"]
        if options.strip_metadata:
            if "/Metadata" in pdf.Root:
                del pdf.Root["/Metadata"]
            for obj in images:
                if "/Metadata" in obj:
                    del obj["/Metadata"]
            try:
                for key in list(pdf.docinfo.keys()):
                    del pdf.docinfo[key]
            except Exception:
                pass
        try:
            pdf.remove_unreferenced_resources()
        except Exception:
            pass

        dst = target_path(src, "pdf", options)
        with atomic_output(dst) as temp:
            pikepdf.settings.set_flate_compression_level(9)
            pdf.save(str(temp), compress_streams=True, recompress_flate=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate)
            note = ""
            if temp.stat().st_size >= src.stat().st_size:
                shutil.copyfile(src, temp)        # never bigger: keep the original
                note = "already as small as it gets"
    finally:
        pdf.close()
    report(progress, 1)
    return [dst], note


_SUPPORTED_FILTERS = {None, "/DCTDecode", "/FlateDecode", "/RunLengthDecode", "/LZWDecode"}


def _recompress_image(pdf, obj, drawn_pt, options: Options):
    import pikepdf
    name = pikepdf.Name
    if obj.get("/ImageMask", False) or "/Decode" in obj or int(obj.get("/BitsPerComponent", 8)) != 8:
        return
    filt = obj.get("/Filter")
    if isinstance(filt, pikepdf.Array):
        if len(filt) != 1:
            return
        filt = filt[0]
    if (str(filt) if filt is not None else None) not in _SUPPORTED_FILTERS:
        return
    cs = obj.get("/ColorSpace")
    keep_cs = None
    if cs == "/DeviceRGB":
        channels = 3
    elif cs == "/DeviceGray":
        channels = 1
    elif isinstance(cs, pikepdf.Array) and len(cs) == 2 and cs[0] == "/ICCBased":
        channels = int(cs[1].get("/N", 0))
        if channels not in (1, 3):
            return
        keep_cs = cs
    else:
        return                                     # CMYK, indexed, spot colours ... stay as they are

    raw_len = len(obj.read_raw_bytes())
    img = pikepdf.PdfImage(obj).as_pil_image()
    img = img.convert("L" if channels == 1 else "RGB")

    w_pt, h_pt = drawn_pt
    max_w = max(1, round(w_pt / 72 * options.dpi)) if w_pt > 0 else img.width
    max_h = max(1, round(h_pt / 72 * options.dpi)) if h_pt > 0 else img.height
    scaled = False
    if img.width > max_w * 1.25 or img.height > max_h * 1.25:
        factor = min(max_w / img.width, max_h / img.height)
        img = img.resize((max(1, round(img.width * factor)), max(1, round(img.height * factor))), Image.LANCZOS)
        scaled = True
    if options.grayscale and img.mode != "L":
        img = ImageOps.grayscale(img)
        keep_cs = None
        scaled = True

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=options.quality, optimize=True)
    data, new_filter = buf.getvalue(), name.DCTDecode
    if img.getcolors(256) is not None:            # few colours (chart, logo, screenshot): stay lossless if
        flate = zlib.compress(img.tobytes(), 9)   # that is not much bigger than a JPEG
        if len(flate) <= len(data) * 1.5:
            data, new_filter = flate, name.FlateDecode
    if new_filter == name.DCTDecode and filt == "/DCTDecode" and not scaled and len(data) > raw_len * 0.9:
        return                                     # re-encoding a JPEG must be worth it
    if len(data) >= raw_len:
        return
    obj.write(data, filter=new_filter)
    if "/DecodeParms" in obj:
        del obj["/DecodeParms"]
    obj.Width, obj.Height, obj.BitsPerComponent = img.width, img.height, 8
    obj.ColorSpace = keep_cs if (keep_cs is not None and img.mode == ("L" if channels == 1 else "RGB")) else (
        name.DeviceGray if img.mode == "L" else name.DeviceRGB)

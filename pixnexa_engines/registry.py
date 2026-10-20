"""Which files PixNexa reads, what each kind can become, and the one entry point that runs a conversion.

    from pixnexa_engines import registry, Options
    cat = registry.category_of("clip.mov")              # -> Category "video"
    registry.convert_file("clip.mov", "mp4", Options()).outputs
    registry.compress_file("scan.pdf", Options(quality=60, dpi=150)).outputs
    registry.images_to_pdf(["a.jpg", "b.png"], Options())

Engines are imported only when used, so listing formats is fast and never loads FFmpeg, pikepdf, etc.
"""
from __future__ import annotations

import dataclasses
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import converter_core as core

from .base import ConversionError, Options, ProgressCallback, target_path


@dataclass(frozen=True)
class Target:
    key: str
    label: str
    description: str = ""
    needs: str = ""              # "ffmpeg" | "libreoffice" | ""


@dataclass(frozen=True)
class Category:
    key: str
    label: str                   # "Images"
    extensions: tuple[str, ...]
    targets: tuple[Target, ...]
    compress_targets: tuple[Target, ...] = ()       # empty: cannot be compressed
    needs: str = ""
    default: str = ""

    def target(self, key: str) -> Target | None:
        return next((t for t in self.targets + self.compress_targets if t.key == key), None)

    @property
    def can_compress(self) -> bool:
        return bool(self.compress_targets)


@dataclass
class Result:
    outputs: list[Path] = field(default_factory=list)
    note: str = ""


def _t(key, label, description="", needs=""):
    return Target(key, label, description, needs)


IMAGE_TARGETS = tuple(_t(f.key, f.label, f.description, "ffmpeg" if f.key == "heic" else "")
                      for f in core.FORMATS.values())
VIDEO_TARGETS = (
    _t("mp4", "MP4", "H.264 video + AAC sound. Plays everywhere."),
    _t("webm", "WEBM", "VP9 + Opus, for the web."),
    _t("mkv", "MKV", "Matroska with H.264 + AAC."),
    _t("mov", "MOV", "QuickTime with H.264 + AAC, for Apple apps."),
    _t("avi", "AVI", "Xvid + MP3, for old players."),
    _t("gif", "GIF", "Animated picture without sound (short clips)."),
    _t("mp3", "MP3", "Only the sound, as MP3."),
    _t("m4a", "M4A", "Only the sound, as AAC."),
    _t("wav", "WAV", "Only the sound, uncompressed."),
    _t("flac", "FLAC", "Only the sound, lossless."),
    _t("ogg", "OGG", "Only the sound, as Vorbis."),
    _t("opus", "OPUS", "Only the sound, as Opus."),
)
AUDIO_TARGETS = (
    _t("mp3", "MP3", "Plays everywhere."),
    _t("m4a", "M4A", "AAC: better than MP3 at the same size."),
    _t("wav", "WAV", "Uncompressed, for editing."),
    _t("flac", "FLAC", "Lossless and about half the size of WAV."),
    _t("ogg", "OGG", "Vorbis, open format."),
    _t("opus", "OPUS", "Best quality for small files."),
)
DOC_DESC = "Needs LibreOffice for most conversions."

CATEGORIES: dict[str, Category] = {c.key: c for c in (
    Category("image", "Images", core.INPUT_EXTENSIONS, IMAGE_TARGETS,
             (_t("keep", "Same", "Keep each picture's format."), _t("jpg", "JPG", "Smallest for photos."),
              _t("webp", "WEBP", "Small, keeps transparency."), _t("avif", "AVIF", "Smallest, newer apps only."),),
             default="png"),
    Category("pdf", "PDF", (".pdf",), (
        _t("png", "PNG", "Every page as a picture (lossless)."),
        _t("jpg", "JPG", "Every page as a photo-size picture."),
        _t("txt", "TXT", "The text of the pages."),
        _t("split", "Split", "One PDF per page, in a new folder."),
        _t("extract", "Pages", "Only the pages you enter, as a new PDF."),
    ), (_t("pdf", "PDF", "Smaller PDF: pictures recompressed and scaled down."),), default="png"),
    Category("video", "Video", (".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpg", ".mpeg",
                                ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".mxf", ".dv", ".asf"),
             VIDEO_TARGETS, (_t("mp4", "MP4", "Smaller MP4 (H.264 or H.265)."),), needs="ffmpeg", default="mp4"),
    Category("audio", "Audio", (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma", ".aiff",
                                ".aif", ".amr", ".ape", ".wv", ".mka", ".ac3", ".caf", ".m4b"),
             AUDIO_TARGETS, (_t("keep", "Same", "MP3, M4A, OGG and OPUS stay; others become MP3."),
                             _t("mp3", "MP3"), _t("m4a", "M4A"), _t("opus", "OPUS")), needs="ffmpeg",
             default="mp3"),
    Category("document", "Documents", (".docx", ".docm", ".dotx", ".doc", ".odt", ".ott", ".fodt", ".rtf", ".txt",
                                       ".wpd", ".wps", ".pages", ".md", ".markdown", ".html", ".htm", ".xhtml"), (
        _t("pdf", "PDF", DOC_DESC, "libreoffice"),
        _t("docx", "DOCX", "Microsoft Word. " + DOC_DESC, "libreoffice"),
        _t("odt", "ODT", "OpenDocument text. " + DOC_DESC, "libreoffice"),
        _t("rtf", "RTF", "Rich Text, opens in any word processor. " + DOC_DESC, "libreoffice"),
        _t("doc", "DOC", "Word 97-2003. " + DOC_DESC, "libreoffice"),
        _t("txt", "TXT", "Plain text (HTML, Markdown and DOCX work without LibreOffice)."),
        _t("html", "HTML", "Web page (Markdown works without LibreOffice)."),
    ), needs="libreoffice", default="pdf"),
    Category("spreadsheet", "Spreadsheets", (".xlsx", ".xlsm", ".xls", ".ods", ".fods", ".numbers"), (
        _t("pdf", "PDF", DOC_DESC, "libreoffice"),
        _t("xlsx", "XLSX", "Microsoft Excel. " + DOC_DESC, "libreoffice"),
        _t("ods", "ODS", "OpenDocument spreadsheet. " + DOC_DESC, "libreoffice"),
        _t("xls", "XLS", "Excel 97-2003. " + DOC_DESC, "libreoffice"),
        _t("csv", "CSV", "Each sheet as a table of text (XLSX works without LibreOffice)."),
        _t("json", "JSON", "Rows as JSON records (XLSX only)."),
        _t("html", "HTML", "Web page. " + DOC_DESC, "libreoffice"),
    ), needs="libreoffice", default="pdf"),
    Category("presentation", "Presentations", (".pptx", ".pptm", ".ppsx", ".pps", ".ppt", ".odp", ".fodp", ".key"), (
        _t("pdf", "PDF", DOC_DESC, "libreoffice"),
        _t("pptx", "PPTX", "Microsoft PowerPoint. " + DOC_DESC, "libreoffice"),
        _t("odp", "ODP", "OpenDocument presentation. " + DOC_DESC, "libreoffice"),
        _t("ppt", "PPT", "PowerPoint 97-2003. " + DOC_DESC, "libreoffice"),
    ), needs="libreoffice", default="pdf"),
    Category("data", "Data", (".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".xml", ".csv", ".tsv"), (
        _t("json", "JSON"), _t("yaml", "YAML"), _t("toml", "TOML"), _t("xml", "XML"),
        _t("csv", "CSV", "Tables only: a list of records."), _t("xlsx", "XLSX", "Tables only, as an Excel sheet."),
    ), default="json"),
    Category("archive", "Archives", (".zip", ".7z", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tbz",
                                     ".tar.xz", ".txz", ".gz", ".bz2", ".xz"), (
        _t("folder", "Extract", "Unpack into a new folder."),
        _t("zip", "ZIP", "Repack as ZIP."), _t("7z", "7Z", "Repack as 7-Zip (smaller)."),
        _t("tar.gz", "TAR.GZ", "Repack as gzip-compressed TAR."),
    ), default="folder"),
    Category("font", "Fonts", (".ttf", ".otf", ".woff", ".woff2"), (
        _t("ttf", "TTF/OTF", "Desktop font (.ttf, or .otf for CFF outlines)."),
        _t("woff", "WOFF", "Web font."), _t("woff2", "WOFF2", "Web font, smallest."),
    ), default="woff2"),
    Category("subtitle", "Subtitles", (".srt", ".ass", ".ssa", ".vtt", ".sub", ".smi", ".sami", ".ttml", ".dfxp"), (
        _t("srt", "SRT", "SubRip: plays everywhere."), _t("ass", "ASS", "Advanced SubStation Alpha."),
        _t("ssa", "SSA", "SubStation Alpha."), _t("vtt", "VTT", "WebVTT, for the web."),
        _t("sub", "SUB", "MicroDVD (23.976 fps)."), _t("ttml", "TTML", "Timed Text (TTML)."),
    ), default="srt"),
)}

ORDER = tuple(CATEGORIES)


def _ext_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for cat in CATEGORIES.values():
        for ext in cat.extensions:
            out.setdefault(ext, cat.key)       # first category wins (".csv" is data, not a spreadsheet)
    return out


_EXT = _ext_map()


def all_extensions() -> tuple[str, ...]:
    return tuple(_EXT)


_SHELL_SKIP = {".ts"}        # far more often TypeScript source than an MPEG transport stream


def shell_extensions() -> tuple[str, ...]:
    """Extensions for Explorer's menu. Registry keys take the last extension only (".tar.gz" -> ".gz")."""
    out = []
    for ext in _EXT:
        last = "." + ext.rsplit(".", 1)[-1]
        if last not in out and last not in _SHELL_SKIP:
            out.append(last)
    return tuple(out)


def category_of(path, sniff: bool = True) -> Category | None:
    """The category of a file by its name; an unknown extension that Pillow can open counts as an image."""
    from .archives import archive_suffix

    p = Path(path)
    suffix = archive_suffix(p)            # ".tar.gz" before ".gz"
    if suffix in _EXT:
        return CATEGORIES[_EXT[suffix]]
    key = _EXT.get(p.suffix.lower())
    if key:
        return CATEGORIES[key]
    if sniff and p.is_file():
        try:
            core.describe_image(p)
            return CATEGORIES["image"]
        except core.ConversionError:
            return None
    return None


def is_supported(path) -> bool:
    return category_of(path, sniff=False) is not None


def list_supported(folder) -> list[Path]:
    """Supported files directly inside a folder (not its sub-folders), sorted by name."""
    try:
        return sorted((p for p in Path(folder).iterdir() if p.is_file() and is_supported(p)),
                      key=lambda p: p.name.lower())
    except OSError:
        return []


def tools() -> dict[str, str | None]:
    from .media import find_ffmpeg
    from .office import find_soffice
    return {"ffmpeg": find_ffmpeg(), "libreoffice": find_soffice()}


# ───────────────────────── one file ─────────────────────────

def _resize(options: Options):
    if options.resize_mode == "max" and (options.max_width or options.max_height):
        return ("max", options.max_width, options.max_height)
    if options.resize_mode == "percent" and options.percent != 100:
        return ("percent", options.percent)
    return None


def _image(src: Path, fmt: str, options: Options, never_bigger=False, target_kb=0) -> Path:
    return core.convert_image(src, fmt, options.out_dir, quality=options.quality, overwrite=options.overwrite,
                              resize=_resize(options), grayscale=options.grayscale,
                              strip_metadata=options.strip_metadata, target_kb=target_kb,
                              png_palette=options.png_palette, suffix=options.suffix, never_bigger=never_bigger)


def convert_file(src, target: str, options: Options | None = None, progress: ProgressCallback | None = None,
                 category: str | None = None) -> Result:
    """Convert one file to `target` (a Target.key of its category). Raises ConversionError."""
    options = dataclasses.replace(options or Options()).clamp()
    src = Path(src)
    if not src.exists():
        raise ConversionError("File not found.")
    cat = CATEGORIES.get(category) if category else category_of(src)
    if cat is None:
        raise ConversionError("This kind of file is not supported.")
    if cat.target(target) is None or target not in {t.key for t in cat.targets}:
        raise ConversionError(f"{cat.label} cannot be converted to {target.upper()}.")
    key = cat.key
    if key == "image":
        return Result([_image(src, target, options)])
    if key == "pdf":
        from . import pdf
        if target in ("png", "jpg"):
            return Result(pdf.render(src, target, options, progress))
        if target == "txt":
            return Result(pdf.to_text(src, options, progress))
        if target == "split":
            return Result(pdf.split(src, options, progress))
        return Result(pdf.extract_pages(src, options, progress))
    if key in ("video", "audio"):
        from . import media
        return Result(media.convert(src, target, options, progress))
    if key in ("document", "spreadsheet", "presentation"):
        from . import office
        return Result(office.convert(src, target, options, progress))
    if key == "data":
        from . import data
        return Result(data.convert(src, target, options, progress))
    if key == "archive":
        from . import archives
        return Result(archives.convert(src, target, options, progress))
    if key == "font":
        from . import fonts
        return Result(fonts.convert(src, target, options, progress))
    if key == "subtitle":
        from . import subtitles
        return Result(subtitles.convert(src, target, options, progress))
    raise ConversionError("This kind of file is not supported.")  # pragma: no cover


_COMPRESS_IMAGE = {"jpg": "jpg", "png": "png", "webp": "webp", "avif": "avif", "heic": "heic", "gif": "gif",
                   "tiff": "tiff", "bmp": "png", "tga": "png", "ico": "png"}


def compress_file(src, options: Options | None = None, progress: ProgressCallback | None = None,
                  target: str = "keep", category: str | None = None) -> Result:
    """Make one file smaller. Images, PDF, video and audio can be compressed; anything else raises."""
    options = dataclasses.replace(options or Options()).clamp()
    if not options.suffix:
        options.suffix = "-compressed"
    src = Path(src)
    if not src.exists():
        raise ConversionError("File not found.")
    cat = CATEGORIES.get(category) if category else category_of(src)
    if cat is None or not cat.can_compress:
        raise ConversionError("This kind of file cannot be compressed. Use “Pack into an archive” instead.")
    before = src.stat().st_size
    note = ""
    if cat.key == "image":
        fmt = target if target in ("jpg", "webp", "avif") else None
        if fmt is None:
            try:
                fmt = _COMPRESS_IMAGE.get(core._SOURCE_FORMAT.get(core.describe_image(src).format, ""), "jpg")
            except ConversionError:
                fmt = "jpg"
        out = _image(src, fmt, options, never_bigger=True, target_kb=options.target_kb)
        outputs = [out]
    elif cat.key == "pdf":
        from . import pdf
        outputs, note = pdf.compress(src, options, progress)
    elif cat.key == "video":
        from . import media
        outputs = media.compress_video(src, options, progress)
    else:
        from . import media
        outputs = media.compress_audio(src, options, progress, target if target != "keep" else "")
    resized = bool(_resize(options) or options.grayscale) if cat.key == "image" else (
        cat.key == "video" and options.max_height_px > 0)
    if not note and len(outputs) == 1 and outputs[0].is_file():
        after = outputs[0].stat().st_size
        if after >= before:
            if outputs[0].suffix.lower() == src.suffix.lower() and not resized:
                shutil.copyfile(src, outputs[0])       # never bigger than the original in the same format
                note = "already as small as it gets"
            else:
                note = "bigger than the original"
    return Result(outputs, note)


# ───────────────────────── several files -> one ─────────────────────────

def _combined_path(first: Path, extension: str, options: Options, stem: str) -> Path:
    plain = Options(out_dir=options.out_dir, overwrite=options.overwrite)
    return target_path(first, extension, plain, stem=stem)


def images_to_pdf(paths, options: Options | None = None, progress: ProgressCallback | None = None) -> Path:
    from . import pdf
    options = (options or Options()).clamp()
    paths = [Path(p) for p in paths]
    if not paths:
        raise ConversionError("Add some pictures first.")
    return pdf.images_to_pdf(paths, _combined_path(paths[0], "pdf", options, paths[0].stem), options, progress)


def merge_pdfs(paths, options: Options | None = None, progress: ProgressCallback | None = None) -> Path:
    from . import pdf
    options = (options or Options()).clamp()
    paths = [Path(p) for p in paths]
    if len(paths) < 2:
        raise ConversionError("Add at least two PDF files to merge.")
    return pdf.merge(paths, _combined_path(paths[0], "pdf", options, f"{paths[0].stem} (merged)"), options, progress)


def pack_files(paths, fmt: str = "zip", options: Options | None = None,
               progress: ProgressCallback | None = None) -> Path:
    from . import archives
    options = (options or Options()).clamp()
    paths = [Path(p) for p in paths]
    if not paths:
        raise ConversionError("Add some files first.")
    fmt = fmt if fmt in archives.PACK_FORMATS else "zip"
    first = paths[0]
    stem = first.name if first.is_dir() else (archives.archive_stem(first) if archives.archive_suffix(first)
                                              else first.stem)
    return archives.pack(paths, _combined_path(first, fmt, options, stem), fmt, options, progress)

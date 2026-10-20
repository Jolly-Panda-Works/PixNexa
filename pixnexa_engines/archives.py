"""Archives: extract ZIP / TAR / TAR.GZ / TAR.BZ2 / TAR.XZ / 7Z (and single .gz / .bz2 / .xz files),
create ZIP / 7Z / TAR.GZ, repack one archive into another, and pack many files into one archive.

Extraction is careful: entries that point outside the target folder (`..`, absolute paths, drive letters) stop
the job before anything is written, links are never created, password-protected archives are refused, and
archives that would unpack to more than the free disk space are refused.
"""
from __future__ import annotations

import bz2
import gzip
import lzma
import os
import shutil
import tarfile
import tempfile
import zipfile
import zlib
from pathlib import Path, PurePosixPath

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

# longest first, so ".tar.gz" wins over ".gz"
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".tbz", ".txz", ".tar", ".zip", ".7z",
                    ".gz", ".bz2", ".xz")
PACK_FORMATS = {"zip": "zip", "7z": "7z", "tar.gz": "tar.gz"}
MAX_ENTRIES = 1_000_000
_PASSWORD = "This archive is password-protected, which PixNexa does not support."


def archive_suffix(path) -> str | None:
    name = Path(path).name.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return suffix
    return None


def archive_stem(path) -> str:
    path = Path(path)
    suffix = archive_suffix(path) or path.suffix
    return path.name[: len(path.name) - len(suffix)] if suffix else path.stem


def _safe_name(name: str) -> PurePosixPath:
    """The relative path of an entry, or ConversionError when it would land outside the target folder."""
    clean = name.replace("\\", "/")
    p = PurePosixPath(clean)
    if (clean.startswith("/") or (len(clean) > 1 and clean[1] == ":") or any(part == ".." for part in p.parts)):
        raise ConversionError(f"The archive is unsafe: “{name}” points outside the target folder. Nothing was "
                              "extracted.")
    return PurePosixPath(*[part for part in p.parts if part not in ("", ".")])


def _check_space(folder: Path, needed: int):
    try:
        free = shutil.disk_usage(folder).free
    except OSError:
        return
    if needed > free:
        raise ConversionError("The archive unpacks to more data than the drive has free space.")


def _copy_stream(src, dst_path: Path, limit: int | None = None):
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(dst_path, "wb") as out:
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            written += len(chunk)
            if limit is not None and written > limit:
                raise ConversionError("An entry in the archive is larger than it says (damaged or malicious).")
            out.write(chunk)


def _extract_zip(src: Path, dest: Path, options: Options, progress):
    try:
        z = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise ConversionError("Not a readable ZIP file.") from None
    with z:
        infos = z.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ConversionError("The archive has too many entries.")
        names = [_safe_name(i.filename) for i in infos]           # checked before anything is written
        if any(i.flag_bits & 0x1 for i in infos):
            raise ConversionError(_PASSWORD)
        _check_space(dest, sum(i.file_size for i in infos))
        for n, (info, rel) in enumerate(zip(infos, names, strict=True)):
            check_cancel(options)
            if not rel.parts:
                continue
            target = dest.joinpath(*rel.parts)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:                                   # a symbolic link: never created
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                with z.open(info) as f:
                    _copy_stream(f, target, info.file_size)
            report(progress, (n + 1) / len(infos))


def _extract_tar(src: Path, dest: Path, options: Options, progress):
    try:
        t = tarfile.open(src)
    except (tarfile.TarError, OSError, EOFError, lzma.LZMAError):
        raise ConversionError("Not a readable TAR archive.") from None
    with t:
        try:
            members = t.getmembers()
        except (tarfile.TarError, EOFError, OSError, lzma.LZMAError, zlib.error):
            raise ConversionError("The archive is damaged.") from None
        if len(members) > MAX_ENTRIES:
            raise ConversionError("The archive has too many entries.")
        names = [_safe_name(m.name) for m in members]
        _check_space(dest, sum(m.size for m in members if m.isfile()))
        for n, (m, rel) in enumerate(zip(members, names, strict=True)):
            check_cancel(options)
            if not rel.parts:
                continue
            target = dest.joinpath(*rel.parts)
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif m.isfile():
                f = t.extractfile(m)
                if f is not None:
                    with f:
                        _copy_stream(f, target, m.size)
            # links, devices and FIFOs are skipped
            report(progress, (n + 1) / len(members))


def _extract_7z(src: Path, dest: Path, options: Options, progress):
    import py7zr
    try:
        archive = py7zr.SevenZipFile(src, mode="r")
    except py7zr.exceptions.PasswordRequired:
        raise ConversionError(_PASSWORD) from None
    except (py7zr.exceptions.Bad7zFile, OSError, EOFError):
        raise ConversionError("Not a readable 7Z file.") from None
    with archive:
        if archive.needs_password():
            raise ConversionError(_PASSWORD)
        infos = archive.list()
        if len(infos) > MAX_ENTRIES:
            raise ConversionError("The archive has too many entries.")
        for info in infos:
            _safe_name(info.filename)
        _check_space(dest, sum(i.uncompressed or 0 for i in infos))
        report(progress, 0.1)
        try:
            archive.extractall(path=dest)
        except py7zr.exceptions.PasswordRequired:
            raise ConversionError(_PASSWORD) from None
        except Exception as exc:
            raise ConversionError(f"The 7Z archive could not be extracted: {exc}") from None
    for root, dirs, files in os.walk(dest):                       # never leave links behind
        for name in dirs + files:
            p = Path(root) / name
            if p.is_symlink():
                p.unlink()
    report(progress, 1)


def _extract_single(src: Path, dest: Path, suffix: str, options: Options, progress):
    opener = {".gz": gzip.open, ".bz2": bz2.open, ".xz": lzma.open}[suffix]
    name = archive_stem(src) or "file"
    try:
        with opener(src, "rb") as f:
            _copy_stream(f, dest / name)
    except (OSError, EOFError, lzma.LZMAError) as exc:
        raise ConversionError(f"The file could not be decompressed: {exc}") from None
    report(progress, 1)


def extract_to(src: Path, dest: Path, options: Options, progress=None):
    suffix = archive_suffix(src)
    if suffix == ".zip":
        _extract_zip(src, dest, options, progress)
    elif suffix == ".7z":
        _extract_7z(src, dest, options, progress)
    elif suffix in (".gz", ".bz2", ".xz") and not _is_tar(src):
        _extract_single(src, dest, suffix, options, progress)
    elif suffix is not None:
        _extract_tar(src, dest, options, progress)
    else:
        raise ConversionError("Not a supported archive.")


def _is_tar(path: Path) -> bool:
    try:
        return tarfile.is_tarfile(path)
    except (OSError, EOFError, lzma.LZMAError):
        return False


def extract(src, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """Unpack into a new folder named after the archive. When the archive holds exactly one top folder, its
    content becomes the result folder (photos.zip with photos/... gives photos/..., not photos/photos/...)."""
    src = Path(src)
    folder = target_folder(src, options, archive_stem(src) + options.suffix)
    with atomic_folder(folder) as temp:
        extract_to(src, temp, options, progress)
        entries = list(temp.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            inner = entries[0]
            holding = temp / ".pixnexa-flatten"
            inner.rename(holding)
            for child in holding.iterdir():
                child.rename(temp / child.name)
            holding.rmdir()
    return [folder]


# ───────────────────────── creating ─────────────────────────

def _walk(paths) -> list[tuple[Path, str]]:
    """(file on disk, name in the archive) for files and whole folders; equal names get " (1)"."""
    items: list[tuple[Path, str]] = []
    used: set[str] = set()

    def unique(name: str) -> str:
        if name.lower() not in used:
            used.add(name.lower())
            return name
        p = PurePosixPath(name)
        for i in range(1, 10_000):
            candidate = str(p.with_name(f"{p.stem} ({i}){p.suffix}"))
            if candidate.lower() not in used:
                used.add(candidate.lower())
                return candidate
        raise ConversionError("Too many files with the same name.")

    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for root, _dirs, files in os.walk(p):
                for f in sorted(files):
                    full = Path(root) / f
                    if full.is_symlink():
                        continue
                    rel = full.relative_to(p.parent).as_posix()
                    items.append((full, unique(rel)))
        elif p.is_file():
            items.append((p, unique(p.name)))
        else:
            raise ConversionError(f"File not found: {p.name}")
    return items


def pack(paths, dst: Path, fmt: str, options: Options, progress: ProgressCallback | None = None) -> Path:
    """Write the files (and folders) into one archive: "zip", "7z" or "tar.gz"."""
    items = _walk(paths)
    if not items:
        raise ConversionError("Nothing to pack.")
    total = sum(max(1, f.stat().st_size) for f, _ in items)
    done = 0
    with atomic_output(dst) as temp:
        if fmt == "zip":
            with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for f, name in items:
                    check_cancel(options)
                    z.write(f, name)
                    done += max(1, f.stat().st_size)
                    report(progress, done / total)
        elif fmt == "7z":
            import py7zr
            with py7zr.SevenZipFile(temp, "w") as z:
                for f, name in items:
                    check_cancel(options)
                    z.write(f, name)
                    done += max(1, f.stat().st_size)
                    report(progress, done / total)
        elif fmt == "tar.gz":
            with tarfile.open(temp, "w:gz", compresslevel=9, format=tarfile.PAX_FORMAT) as t:
                for f, name in items:
                    check_cancel(options)
                    t.add(f, arcname=name, recursive=False)
                    done += max(1, f.stat().st_size)
                    report(progress, done / total)
        else:
            raise ConversionError(f"Unsupported archive format: {fmt}")
    return dst


def convert(src, target: str, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    """target: "folder" (extract) or "zip" / "7z" / "tar.gz" (repack the archive's content)."""
    src = Path(src)
    target = target.lower()
    if target in ("folder", "extract"):
        return extract(src, options, progress)
    if target not in PACK_FORMATS:
        raise ConversionError(f"Unsupported target format: {target}")
    with tempfile.TemporaryDirectory(prefix="pixnexa-arc-") as tmp:
        work = Path(tmp)
        extract_to(src, work, options, lambda v: report(progress, v * 0.5))
        dst = target_path(src, target, options, stem=archive_stem(src))
        top = sorted(work.iterdir())
        return [pack(top, dst, target, options, lambda v: report(progress, 0.5 + v * 0.5))]

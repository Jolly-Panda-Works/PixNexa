"""Documents, spreadsheets and presentations.

Office formats go through LibreOffice (`soffice --headless --convert-to`) when it is installed; PixNexa never
downloads it. A few conversions need nothing at all: Markdown -> HTML, HTML / DOCX -> TXT, XLSX -> CSV / JSON.
"""
from __future__ import annotations

import csv
import glob
import html
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .base import ConversionError, Options, ProgressCallback, atomic_output, report, run_process, target_path

LIBREOFFICE_URL = "https://www.libreoffice.org/download/download-libreoffice/"
MISSING = ("This conversion needs LibreOffice (free), which was not found. Install it from "
           f"{LIBREOFFICE_URL} and try again.")

# --convert-to arguments. The explicit filter names make e.g. HTML -> DOCX work (a plain "docx" does not).
FILTERS = {
    "pdf": "pdf",
    "docx": "docx:MS Word 2007 XML",
    "doc": "doc:MS Word 97",
    "odt": "odt:writer8",
    "rtf": "rtf:Rich Text Format",
    "txt": "txt:Text (encoded):UTF8",
    "html": "html:HTML (StarWriter)",
    "xlsx": "xlsx:Calc MS Excel 2007 XML",
    "xls": "xls:MS Excel 97",
    "ods": "ods:calc8",
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76",
    "pptx": "pptx:Impress MS PowerPoint 2007 XML",
    "ppt": "ppt:MS PowerPoint 97",
    "odp": "odp:impress8",
}
CALC_FILTERS = {"html": "html:HTML (StarCalc)"}
MARKDOWN = (".md", ".markdown")
HTML_EXT = (".html", ".htm", ".xhtml")
SPREADSHEET_EXT = (".xlsx", ".xlsm", ".xls", ".ods", ".fods", ".numbers")


def find_soffice() -> str | None:
    env = os.environ.get("PIXNEXA_SOFFICE", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    candidates = []
    if sys.platform == "win32":
        for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if not base:
                continue
            roots = [Path(base)] + ([Path(base) / "Programs"] if var == "LOCALAPPDATA" else [])
            for root in roots:
                candidates.append(root / "LibreOffice" / "program" / "soffice.exe")
                candidates += [Path(p) for p in glob.glob(str(root / "LibreOffice*" / "program" / "soffice.exe"))]
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
    else:
        candidates += [Path("/usr/bin/soffice"), Path("/usr/lib/libreoffice/program/soffice"),
                       Path("/opt/libreoffice/program/soffice")]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _profile_dir() -> Path:
    """LibreOffice's own settings for PixNexa: separate from the user's, so an open LibreOffice window does not
    swallow the conversion."""
    folder = Path(tempfile.gettempdir()) / "PixNexa-LibreOffice-profile"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def libreoffice(src: Path, target: str, options: Options, progress: ProgressCallback | None = None,
                stem: str | None = None) -> Path:
    soffice = find_soffice()
    if soffice is None:
        raise ConversionError(MISSING)
    spec = (CALC_FILTERS.get(target) if src.suffix.lower() in SPREADSHEET_EXT + (".csv",) else None) \
        or FILTERS.get(target)
    if spec is None:
        raise ConversionError(f"Unsupported target format: {target}")
    dst = target_path(src, target, options, stem=stem)
    report(progress, 0.05)
    with tempfile.TemporaryDirectory(prefix="pixnexa-lo-") as tmp:
        # A plain ASCII copy of the name avoids trouble with unusual characters in some LibreOffice versions.
        work = Path(tmp) / f"input{src.suffix.lower()}"
        shutil.copyfile(src, work)
        outdir = Path(tmp) / "out"
        args = [soffice, "--headless", "--norestore", "--nolockcheck", "--nodefault", "--nologo",
                f"-env:UserInstallation={_profile_dir().as_uri()}", "--convert-to", spec,
                "--outdir", str(outdir), str(work)]
        code, stderr = run_process(args, options=options, timeout=600)
        produced = sorted(outdir.glob("*")) if outdir.is_dir() else []
        if not produced:
            if "no export filter" in stderr.lower():
                raise ConversionError(f"LibreOffice cannot save this kind of file as {target.upper()}.")
            detail = stderr.strip().splitlines()[-1][:200] if stderr.strip() else f"exit code {code}"
            raise ConversionError(f"LibreOffice could not convert this file ({detail}).")
        with atomic_output(dst) as temp:
            shutil.move(str(produced[0]), temp)
    report(progress, 1)
    return dst


# ───────────────────────── pure Python ─────────────────────────

class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header",
             "footer", "table", "ul", "ol", "pre", "blockquote", "hr", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append("\t")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(re.sub(r"[ \t\r\n]+", " ", data))

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [ln.strip() for ln in raw.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.text()


def read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("cp1252", "replace")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        raise ConversionError("Not a readable DOCX file.") from None
    root = ET.fromstring(xml)
    lines = []
    for para in root.iter(f"{_W}p"):
        bits = []
        for node in para.iter():
            if node.tag == f"{_W}t" and node.text:
                bits.append(node.text)
            elif node.tag == f"{_W}tab":
                bits.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                bits.append("\n")
        lines.append("".join(bits))
    return "\n".join(lines).strip() + "\n"


def markdown_to_html(text: str, title: str) -> str:
    import markdown
    body = markdown.markdown(text, extensions=["extra", "sane_lists", "toc"], output_format="html")
    return ("<!doctype html>\n<html><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{html.escape(title)}"
            "</title><style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:46em;margin:2em auto;"
            "padding:0 1em;line-height:1.55}pre,code{background:#f4f4f4;border-radius:4px}pre{padding:.8em;"
            "overflow:auto}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.3em .6em}"
            "img{max-width:100%}</style></head><body>\n" + body + "\n</body></html>\n")


def _write_text(dst: Path, text: str) -> Path:
    with atomic_output(dst) as temp:
        temp.write_text(text, encoding="utf-8")
    return dst


def xlsx_rows(path: Path):
    """{sheet name: list of rows} of an XLSX / XLSM file (values, not formulas)."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        raise ConversionError("Not a readable XLSX file.") from None
    try:
        sheets = {}
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            while rows and all(v is None for v in rows[-1]):
                rows.pop()
            if rows:
                width = max(len(r) for r in rows)
                while width and all((len(r) < width or r[width - 1] is None) for r in rows):
                    width -= 1
                sheets[ws.title] = [r[:width] for r in rows]
        return sheets
    finally:
        wb.close()


def _cell(v):
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def xlsx_export(src: Path, target: str, options: Options) -> list[Path]:
    sheets = xlsx_rows(src)
    if not sheets:
        raise ConversionError("The workbook is empty.")
    outputs = []
    if target == "csv":
        for title, rows in sheets.items():
            stem = src.stem if len(sheets) == 1 else f"{src.stem} - {_safe(title)}"
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\r\n").writerows([[_cell(v) for v in r] for r in rows])
            dst = target_path(src, "csv", options, stem=stem)
            with atomic_output(dst) as temp:
                temp.write_text(buf.getvalue(), encoding="utf-8-sig")       # Excel opens UTF-8 with a BOM
            outputs.append(dst)
        return outputs
    data = {}
    for title, rows in sheets.items():
        header = [str(h) if h is not None else f"column{i + 1}" for i, h in enumerate(rows[0])]
        data[title] = [{header[i]: _cell(v) for i, v in enumerate(r) if i < len(header)} for r in rows[1:]]
    payload = next(iter(data.values())) if len(data) == 1 else data
    dst = target_path(src, "json", options)
    return [_write_text(dst, json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")]


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "sheet"


def convert(src, target: str, options: Options, progress: ProgressCallback | None = None) -> list[Path]:
    src = Path(src)
    ext = src.suffix.lower()
    target = target.lower()
    if ext in MARKDOWN:
        text = read_text_file(src)
        if target == "html":
            return [_write_text(target_path(src, "html", options), markdown_to_html(text, src.stem))]
        if target == "txt":
            return [_write_text(target_path(src, "txt", options), text)]
        with tempfile.TemporaryDirectory(prefix="pixnexa-md-") as tmp:     # Markdown -> HTML -> LibreOffice
            page = Path(tmp) / f"{src.stem}.html"
            page.write_text(markdown_to_html(text, src.stem), encoding="utf-8")
            folder = Options(**{**options.__dict__, "out_dir": options.out_dir or src.parent})
            return [libreoffice(page, target, folder, progress, stem=src.stem)]
    if ext in HTML_EXT and target == "txt":
        return [_write_text(target_path(src, "txt", options), html_to_text(read_text_file(src)))]
    if ext in (".xlsx", ".xlsm") and target in ("csv", "json"):
        out = xlsx_export(src, target, options)
        report(progress, 1)
        return out
    if target == "json" and ext in SPREADSHEET_EXT:
        raise ConversionError("JSON is available for XLSX files. Convert to XLSX first.")
    if ext == ".docx" and target == "txt" and find_soffice() is None:
        return [_write_text(target_path(src, "txt", options), docx_to_text(src))]
    return [libreoffice(src, target, options, progress)]

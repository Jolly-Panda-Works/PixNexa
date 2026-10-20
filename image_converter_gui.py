#!/usr/bin/env python3
"""PixNexa Desktop - desktop app.

Add any files (button, drag and drop, a whole folder or Explorer's right-click menu), choose Convert or Compress,
pick a target for each kind of file in the list, press the big button. Everything runs on this computer.
Dark + orange interface, shared with SnapshotAll.
"""
import dataclasses
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import PIL._tkinter_finder  # noqa: F401  (CustomTkinter imports Pillow's Tk support lazily, so PyInstaller
import PIL.ImageTk  # noqa: F401              would miss it unless it is imported here)
from PIL import Image, ImageDraw, ImageFont, ImageOps

import converter_core as core
import shell_integration
from app_common import (
    APP_AUTHOR,
    APP_BRAND,
    APP_LICENSE,
    APP_NAME,
    APP_REPO,
    APP_SLUG,
    APP_URL,
    APP_VERSION,
    APP_WEBSITE,
    LEGACY_SLUG,
)
from pixnexa_engines import ConversionError, Options, registry
from pixnexa_engines.base import Cancelled
from pixnexa_engines.office import LIBREOFFICE_URL
from single_instance import SingleInstance

try:  # drag and drop is optional: without tkinterdnd2 everything else still works
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DnDBase = TkinterDnD.DnDWrapper
except Exception:  # pragma: no cover - depends on the installed packages
    DND_FILES = TkinterDnD = None
    _DnDBase = object

# ── Dark + orange theme (same palette as SnapshotAll) ───────────────
BG = "#110D0A"
TOOLBAR = "#16110D"
SIDEBAR = "#181310"
PANEL = "#1F1813"
PANEL_H = "#2B221B"
FIELD = "#2A211A"
BORDER = "#3A2E24"
FG = "#F5EEE8"
MUTED = "#A99B8E"
ORANGE = "#F97316"
ORANGE_H = "#FB923C"
ON_ORANGE = "#1A0E05"
DANGER = "#F87171"
OK = "#4ADE80"
FAINT_TEXT = "#6E6259"

# type badges in the file list (files without a picture preview)
BADGE = {"pdf": "#DC2626", "video": "#7C3AED", "audio": "#0EA5E9", "document": "#2563EB", "spreadsheet": "#16A34A",
         "presentation": "#EA580C", "data": "#0D9488", "archive": "#A16207", "font": "#DB2777",
         "subtitle": "#64748B", "image": "#F97316"}

FONT_FAMILY = "Segoe UI"
OUT_SAME, OUT_CUSTOM = "Next to the original", "Custom folder"
MODE_CONVERT, MODE_COMPRESS = "Convert", "Compress"

QUALITY_LABELS = {"high": "High", "balanced": "Balanced", "small": "Small"}
RESOLUTIONS = {"Original": 0, "1080p": 1080, "720p": 720, "480p": 480}
BITRATES = ("64", "96", "128", "160", "192", "256", "320")
DPIS = ("72", "96", "150", "200", "300", "600")
PDF_LEVELS = {"Smallest": (72, 50), "Balanced": (150, 65), "High quality": (300, 85)}
PAGE_SIZES = {"Picture size": "image", "A4": "a4", "Letter": "letter"}
RESIZE_LABELS = {"Original": "none", "Fit inside": "max", "Percent": "percent"}

ctk.set_appearance_mode("dark")


# ───────────────────────── helpers ─────────────────────────

def asset(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


def open_path(p):
    p = str(p)
    try:
        if sys.platform == "win32":
            os.startfile(p)  # noqa: S606 - opening a folder the user chose
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except Exception:
        pass


def reveal(path):
    """Show a file in Explorer (selected); other systems just open its folder."""
    path = Path(path)
    if sys.platform == "win32":
        try:
            subprocess.Popen(f'explorer /select,"{path}"')
            return
        except Exception:
            pass
    open_path(path.parent if path.is_file() else path)


def human_size(n):
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"


def shorten(text, limit):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def path_size(p):
    """Size of a file, or of everything inside a folder."""
    p = Path(p)
    try:
        if p.is_dir():
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return p.stat().st_size
    except OSError:
        return 0


def _int(value, default=0, low=0, high=1_000_000):
    try:
        return max(low, min(high, int(str(value).strip() or default)))
    except (TypeError, ValueError):
        return default


THUMB = 56
_THUMB_BG = (31, 24, 19, 255)


def _tile_from(img):
    tile = Image.new("RGBA", (THUMB, THUMB), _THUMB_BG)
    small = img.convert("RGBA")
    small.thumbnail((THUMB, THUMB), Image.LANCZOS)
    tile.alpha_composite(small, ((THUMB - small.width) // 2, (THUMB - small.height) // 2))
    return tile


def make_thumbnail(path):
    """A small square preview of an image (a dark placeholder tile if it cannot be drawn)."""
    tile = Image.new("RGBA", (THUMB, THUMB), _THUMB_BG)
    try:
        with Image.open(path) as im:
            if im.format == "JPEG":
                im.draft("RGB", (THUMB * 2, THUMB * 2))      # decode a reduced size: much faster for big photos
            im.thumbnail((THUMB * 2, THUMB * 2))
            im = ImageOps.exif_transpose(im) or im
            tile = _tile_from(im)
    except Exception:
        pass
    return ctk.CTkImage(light_image=tile, dark_image=tile, size=(THUMB, THUMB))


def _badge_font(size):
    try:
        return ImageFont.load_default(size=size)
    except Exception:  # Pillow without FreeType
        return ImageFont.load_default()


def make_badge(path, category):
    """A coloured tile with the file's extension, for files that have no picture preview."""
    if category == "pdf":
        try:
            from pixnexa_engines.pdf import thumbnail
            page = thumbnail(path, THUMB)
            if page is not None:
                tile = _tile_from(page)
                return ctk.CTkImage(light_image=tile, dark_image=tile, size=(THUMB, THUMB))
        except Exception:
            pass
    scale = 2
    size = THUMB * scale
    tile = Image.new("RGBA", (size, size), _THUMB_BG)
    draw = ImageDraw.Draw(tile)
    color = BADGE.get(category, "#57534E")
    draw.rounded_rectangle((8, 8, size - 8, size - 8), radius=18, fill=color)
    name = Path(path).name.lower()
    ext = next((s for s in (".tar.gz", ".tar.bz2", ".tar.xz") if name.endswith(s)), Path(path).suffix)
    text = (ext.lstrip(".") or "?").upper()[:6]
    font = _badge_font(30 if len(text) <= 4 else 22)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), text,
              fill="#FFFFFF", font=font)
    tile = tile.resize((THUMB, THUMB), Image.LANCZOS)
    return ctk.CTkImage(light_image=tile, dark_image=tile, size=(THUMB, THUMB))


def describe(path, category):
    """The grey line under a file name. Raises ConversionError for an image that cannot be read."""
    size = human_size(path_size(path))
    ext = path.suffix.lstrip(".").upper() or "?"
    if category == "image":
        info = core.describe_image(path)
        return f"{info.format} · {info.width} × {info.height} · {human_size(info.size_bytes)}"
    if category == "pdf":
        try:
            from pixnexa_engines.pdf import page_count
            n = page_count(path)
            return f"PDF · {n} page{'s' if n != 1 else ''} · {size}"
        except ConversionError as exc:
            return f"PDF · {shorten(str(exc), 40)} · {size}"
    label = registry.CATEGORIES[category].label.rstrip("s").lower()
    if category == "archive":
        name = path.name.lower()
        ext = next((s.lstrip(".").upper() for s in (".tar.gz", ".tar.bz2", ".tar.xz") if name.endswith(s)), ext)
    return f"{ext} {label} · {size}"


def set_windows_app_id():
    """Give the process its own taskbar identity so Windows shows our icon (not python.exe's)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"UsefFarahmand.{APP_SLUG}")
        except Exception:
            pass


def apply_window_icon(win):
    """Set the window / taskbar icon.

    CustomTkinter installs its own icon 200 ms after a window opens unless iconbitmap() was
    already called, so this must run immediately (and again later, to be safe).
    """
    try:
        if sys.platform == "win32":
            win.iconbitmap(str(asset("icon.ico")))
        else:
            win._icon_ref = tk.PhotoImage(file=str(asset("logo_64.png")))
            win.iconphoto(True, win._icon_ref)
    except Exception:
        pass


def style_titlebar(win, color=None, text=FG):
    """Paint the native Windows title bar in the app's color (Windows 11, build 22000+).

    Windows 10 cannot recolor the title bar, so there it just gets the dark variant.
    Does nothing on other systems.
    """
    if sys.platform != "win32":
        return
    color = color or TOOLBAR
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()

        def colorref(hex_color):  # COLORREF is 0x00BBGGRR
            r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
            return r | (g << 8) | (b << 16)

        def set_attr(attr, value):
            v = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        set_attr(20, 1)                   # DWMWA_USE_IMMERSIVE_DARK_MODE
        set_attr(34, colorref(color))     # DWMWA_BORDER_COLOR
        set_attr(35, colorref(color))     # DWMWA_CAPTION_COLOR
        set_attr(36, colorref(text))      # DWMWA_TEXT_COLOR
    except Exception:
        pass


def schedule_titlebar_style(win, color=None):
    """CustomTkinter re-applies its own title bar shortly after opening, so style it a few times."""
    for ms in (60, 300, 900):
        win.after(ms, lambda: style_titlebar(win, color))


def settings_dir():
    base = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
    folder, legacy = base / APP_SLUG, base / LEGACY_SLUG
    if not folder.exists() and legacy.is_dir():   # keep the options saved before the PixNexa rebrand
        try:
            legacy.rename(folder)
        except OSError:
            return legacy
    return folder


def settings_file():
    return settings_dir() / "settings.json"


DEFAULT_TARGETS = {key: cat.default for key, cat in registry.CATEGORIES.items()}
DEFAULT_COMPRESS = {key: cat.compress_targets[0].key for key, cat in registry.CATEGORIES.items() if cat.can_compress}

DEFAULT_SETTINGS = {
    "format": "png", "quality": core.DEFAULT_QUALITY, "output": OUT_SAME, "out_dir": "", "overwrite": False,
    "open_after": True,
    # added with the file converter
    "mode": MODE_CONVERT, "targets": dict(DEFAULT_TARGETS), "compress_targets": dict(DEFAULT_COMPRESS),
    "resize_mode": "none", "max_width": "", "max_height": "", "percent": "50", "grayscale": False,
    "strip_metadata": True, "target_kb": "", "png_palette": False, "max_side": "",
    "dpi": "150", "pdf_level": "Balanced", "page_size": "image",
    "video_quality": "balanced", "video_codec": "h264", "resolution": "Original", "audio_bitrate": "192",
    "archive_format": "zip",
}


def load_settings():
    data = json.loads(json.dumps(DEFAULT_SETTINGS))         # a deep copy
    try:
        loaded = json.loads(settings_file().read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS})
    except Exception:
        pass
    if data["format"] not in core.FORMATS:
        data["format"] = DEFAULT_SETTINGS["format"]
    if data["output"] not in (OUT_SAME, OUT_CUSTOM):
        data["output"] = OUT_SAME
    if data["mode"] not in (MODE_CONVERT, MODE_COMPRESS):
        data["mode"] = MODE_CONVERT
    try:
        data["quality"] = max(1, min(100, int(data["quality"])))
    except (TypeError, ValueError):
        data["quality"] = core.DEFAULT_QUALITY
    for key, defaults, kind in (("targets", DEFAULT_TARGETS, "targets"),
                                ("compress_targets", DEFAULT_COMPRESS, "compress_targets")):
        saved = data[key] if isinstance(data[key], dict) else {}
        clean = dict(defaults)
        for cat_key, target in saved.items():
            cat = registry.CATEGORIES.get(cat_key)
            if cat and target in {t.key for t in getattr(cat, kind)}:
                clean[cat_key] = target
        data[key] = clean
    data["targets"]["image"] = data["format"]               # "format" is the image target (older settings files)
    choices = {"resize_mode": RESIZE_LABELS.values(), "pdf_level": PDF_LEVELS, "page_size": PAGE_SIZES.values(),
               "video_quality": QUALITY_LABELS, "video_codec": ("h264", "h265"), "resolution": RESOLUTIONS,
               "audio_bitrate": BITRATES, "dpi": DPIS, "archive_format": ("zip", "7z", "tar.gz")}
    for key, allowed in choices.items():
        if data[key] not in allowed:
            data[key] = DEFAULT_SETTINGS[key]
    for key in ("grayscale", "strip_metadata", "png_palette", "overwrite", "open_after"):
        data[key] = bool(data[key])
    for key in ("max_width", "max_height", "percent", "target_kb", "max_side"):
        data[key] = str(data[key]) if str(data[key]).isdigit() else DEFAULT_SETTINGS[key]
    return data


def store_settings(data):
    try:
        f = settings_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def add_edit_support(widget):
    """Make Ctrl+C/V/X/A work with any keyboard layout (e.g. Persian), and add a right-click menu."""
    w = getattr(widget, "_entry", None) or getattr(widget, "_textbox", None) or widget

    def select_all():
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end-1c")
        else:
            w.select_range(0, "end")
            w.icursor("end")

    def editable():
        return str(w.cget("state")) != "disabled"

    def on_key(e):
        if e.state & 0x4:  # Ctrl held
            k = e.keycode  # physical key code, independent of keyboard language
            if k == 86:
                if editable():
                    w.event_generate("<<Paste>>")
                return "break"
            if k == 67:
                w.event_generate("<<Copy>>")
                return "break"
            if k == 88:
                if editable():
                    w.event_generate("<<Cut>>")
                return "break"
            if k == 65:
                select_all()
                return "break"

    menu = tk.Menu(w, tearoff=0, bg=FIELD, fg=FG, activebackground=ORANGE, activeforeground=ON_ORANGE,
                   bd=0, relief="flat")
    menu.add_command(label="Paste", command=lambda: editable() and w.event_generate("<<Paste>>"))
    menu.add_command(label="Copy", command=lambda: w.event_generate("<<Copy>>"))
    menu.add_command(label="Cut", command=lambda: editable() and w.event_generate("<<Cut>>"))
    menu.add_command(label="Select all", command=select_all)

    w.bind("<Key>", on_key, add="+")
    w.bind("<Button-3>", lambda e: (w.focus_set(), menu.tk_popup(e.x_root, e.y_root)), add="+")


# ───────────────────────── settings / about dialog ─────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app, fg_color=BG)
        apply_window_icon(self)
        self.after(300, lambda: apply_window_icon(self))
        schedule_titlebar_style(self, BG)
        self.app = app
        self.title("Settings")
        self.geometry("480x" + ("690" if shell_integration.is_supported() else "540"))
        self.resizable(False, False)
        self.transient(app)
        self.columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Settings", font=app.f_title, text_color=FG).grid(
            row=0, column=0, sticky="w", padx=28, pady=(24, 14))

        about = app._card(self)
        about.grid(row=1, column=0, sticky="ew", padx=28)
        about.columnconfigure(1, weight=1)
        ctk.CTkLabel(about, text="ABOUT", font=app.f_section, text_color=ORANGE).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 8))
        ctk.CTkLabel(about, image=app.img_logo_big, text="").grid(
            row=1, column=0, rowspan=4, padx=(18, 14), pady=(0, 14))
        ctk.CTkLabel(about, text=APP_NAME, font=app.f_bold_lg, text_color=FG, anchor="w").grid(
            row=1, column=1, sticky="w")
        ctk.CTkLabel(about, text=f"Version {APP_VERSION}", font=app.f_body, text_color=MUTED, anchor="w").grid(
            row=2, column=1, sticky="w")
        ctk.CTkLabel(about, text=f"Created by {APP_AUTHOR}", font=app.f_body, text_color=FG, anchor="w").grid(
            row=3, column=1, sticky="w")
        site = ctk.CTkLabel(about, text=APP_WEBSITE.split("://", 1)[-1].rstrip("/"), font=app.f_body,
                            text_color=ORANGE, anchor="w", cursor="hand2")
        site.grid(row=4, column=1, sticky="w", pady=(0, 14))
        site.bind("<Button-1>", lambda e: webbrowser.open(APP_WEBSITE))

        links = ctk.CTkFrame(about, fg_color="transparent")
        links.grid(row=5, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 6))
        app._ghost(links, "Website", lambda: webbrowser.open(APP_WEBSITE), width=100).pack(side="left")
        app._ghost(links, "GitHub", lambda: webbrowser.open(APP_URL), width=100).pack(side="left", padx=8)
        app._ghost(links, "Releases", lambda: webbrowser.open(APP_REPO + "/releases/latest"),
                   width=100).pack(side="left")
        ctk.CTkLabel(about, text=f"Released under the {APP_LICENSE}. Everything runs on your computer; "
                                 "nothing is uploaded.", font=app.f_small, text_color=MUTED, anchor="w",
                     justify="left", wraplength=400).grid(row=6, column=0, columnspan=2, sticky="w",
                                                          padx=18, pady=(0, 16))

        self._build_tools_card(app)
        if shell_integration.is_supported():
            self._build_menu_card(app)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=4, column=0, sticky="ew", padx=28, pady=(18, 0))
        foot.columnconfigure(0, weight=1)
        app._ghost(foot, "Reset options", self.reset, width=130).grid(row=0, column=0, sticky="w")
        app._primary(foot, "Done", self.destroy, width=110).grid(row=0, column=1, sticky="e")
        self.after(150, self._focus)

    def _build_tools_card(self, app):
        card = app._card(self)
        card.grid(row=2, column=0, sticky="ew", padx=28, pady=(14, 0))
        card.columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="HELPER PROGRAMS", font=app.f_section, text_color=ORANGE).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 6))
        found = app.tools
        ff = "FFmpeg: found" if found.get("ffmpeg") else "FFmpeg: not found (video and audio are unavailable)"
        lo = "LibreOffice: found" if found.get("libreoffice") else "LibreOffice: not installed (needed for Office files)"
        ctk.CTkLabel(card, text=ff, font=app.f_small, text_color=OK if found.get("ffmpeg") else DANGER,
                     anchor="w").grid(row=1, column=0, sticky="w", padx=18)
        ctk.CTkLabel(card, text=lo, font=app.f_small, text_color=OK if found.get("libreoffice") else MUTED,
                     anchor="w").grid(row=2, column=0, sticky="w", padx=18, pady=(2, 14))
        if not found.get("libreoffice"):
            app._ghost(card, "Get LibreOffice", lambda: webbrowser.open(LIBREOFFICE_URL), width=130,
                       height=32).grid(row=1, column=1, rowspan=2, padx=(0, 18))

    def _build_menu_card(self, app):
        card = app._card(self)
        card.grid(row=3, column=0, sticky="ew", padx=28, pady=(14, 0))
        card.columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="WINDOWS EXPLORER", font=app.f_section, text_color=ORANGE).grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 8))
        self.menu_var = tk.BooleanVar(value=shell_integration.is_registered())
        self.menu_switch = app._switch(card, f"Add “Convert with {APP_BRAND}” to the right-click menu", self.menu_var)
        self.menu_switch.configure(command=self._toggle_menu)
        self.menu_switch.grid(row=1, column=0, sticky="w", padx=18)
        self.menu_note = ctk.CTkLabel(
            card, text=f"Right-click a file → Convert with {APP_BRAND}. On Windows 11 it is under "
                       "“Show more options”.", font=app.f_small, text_color=MUTED, anchor="w", justify="left",
            wraplength=400)
        self.menu_note.grid(row=2, column=0, sticky="w", padx=18, pady=(8, 14))

    def _toggle_menu(self):
        want = bool(self.menu_var.get())
        ok = shell_integration.register() if want else shell_integration.unregister()
        if ok:
            self.menu_note.configure(text_color=OK, text="Added." if want else "Removed.")
        else:
            self.menu_var.set(not want)
            self.menu_note.configure(text_color=DANGER, text="Windows did not allow that change. Try again.")

    def _focus(self):
        try:
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

    def reset(self):
        self.app.apply_settings(json.loads(json.dumps(DEFAULT_SETTINGS)))


# ───────────────────────── option sections ─────────────────────────

class Section:
    """A block of options in the right panel. Rows can be shown or hidden depending on other choices."""

    def __init__(self, app, parent, title, count=None):
        self.app = app
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.rows = []
        head = ctk.CTkFrame(self.frame, fg_color="transparent")
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text=title.upper(), font=app.f_section, text_color=ORANGE).grid(row=0, column=0,
                                                                                         sticky="w")
        if count is not None:
            ctk.CTkLabel(head, text=f"{count} file{'s' if count != 1 else ''}", font=app.f_small,
                         text_color=MUTED).grid(row=0, column=1, sticky="w", padx=10)
        self.add(head, pady=(14, 6))

    def add(self, widget, show=None, pady=(8, 0)):
        widget.grid(row=len(self.rows), column=0, sticky="ew", pady=pady)
        self.rows.append((widget, show))
        return widget

    def note(self, text, color=MUTED, show=None):
        label = ctk.CTkLabel(self.frame, text=text, font=self.app.f_small, text_color=color, anchor="w",
                             justify="left", wraplength=318)
        return self.add(label, show, pady=(6, 0))

    def refresh(self):
        for widget, show in self.rows:
            if show is None or show():
                widget.grid()
            else:
                widget.grid_remove()


# ───────────────────────── main window ─────────────────────────

class App(ctk.CTk, _DnDBase):
    def __init__(self, initial_paths=None, instance=None):
        set_windows_app_id()
        super().__init__(fg_color=BG)
        self.instance = instance
        self._pending_paths = []
        self._results_shown = False
        apply_window_icon(self)
        self.title(f"{APP_NAME} - convert and compress files")
        self.geometry("1100x760")
        self.minsize(980, 660)

        self.dnd_ok = False
        if TkinterDnD is not None:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop)
                self.dnd_ok = True
            except Exception:
                self.dnd_ok = False

        fam = FONT_FAMILY
        self.f_title = ctk.CTkFont(family=fam, size=26, weight="bold")
        self.f_bold_lg = ctk.CTkFont(family=fam, size=18, weight="bold")
        self.f_bold = ctk.CTkFont(family=fam, size=14, weight="bold")
        self.f_body = ctk.CTkFont(family=fam, size=14)
        self.f_small = ctk.CTkFont(family=fam, size=12)
        self.f_section = ctk.CTkFont(family=fam, size=11, weight="bold")
        self.f_big = ctk.CTkFont(family=fam, size=20, weight="bold")

        def img(name, size):
            im = Image.open(asset(name))
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)

        self.img_logo = img("logo_64.png", (36, 36))
        self.img_logo_big = img("logo.png", (64, 64))
        self.img_logo_empty = img("logo.png", (96, 96))
        self.img_gear = img("icon_gear.png", (20, 20))

        self.settings = load_settings()
        self.tools = registry.tools()
        self.items = []                 # {"path", "category", "info", "row", "status", "detail", "bar", ...}
        self.busy = False
        self.stop_event = threading.Event()
        self.q = queue.Queue()
        self.last_outputs = []
        self._lockable = []
        self._sections = []
        self._section_key = None
        self._combined = None
        self._shown_vars = {}

        s = self.settings
        self.fmt = tk.StringVar(value=s["format"])        # the image target (kept for older settings and tests)
        self.mode = tk.StringVar(value=s["mode"])
        self.targets = {k: tk.StringVar(value=v) for k, v in s["targets"].items()}
        self.targets["image"] = self.fmt
        self.compress_targets = {k: tk.StringVar(value=v) for k, v in s["compress_targets"].items()}
        self.out_mode = tk.StringVar(value=s["output"])
        self.out_dir = tk.StringVar(value=s["out_dir"])
        self.overwrite = tk.BooleanVar(value=s["overwrite"])
        self.open_after = tk.BooleanVar(value=s["open_after"])
        self.quality = s["quality"]
        self.vars = {
            "resize_mode": tk.StringVar(value=s["resize_mode"]), "max_width": tk.StringVar(value=s["max_width"]),
            "max_height": tk.StringVar(value=s["max_height"]), "percent": tk.StringVar(value=s["percent"]),
            "grayscale": tk.BooleanVar(value=s["grayscale"]), "strip_metadata": tk.BooleanVar(value=s["strip_metadata"]),
            "target_kb": tk.StringVar(value=s["target_kb"]), "png_palette": tk.BooleanVar(value=s["png_palette"]),
            "max_side": tk.StringVar(value=s["max_side"]), "dpi": tk.StringVar(value=s["dpi"]),
            "pdf_level": tk.StringVar(value=s["pdf_level"]), "page_size": tk.StringVar(value=s["page_size"]),
            "video_quality": tk.StringVar(value=s["video_quality"]), "video_codec": tk.StringVar(value=s["video_codec"]),
            "resolution": tk.StringVar(value=s["resolution"]), "audio_bitrate": tk.StringVar(value=s["audio_bitrate"]),
            "archive_format": tk.StringVar(value=s["archive_format"]), "pages": tk.StringVar(value=""),
        }
        self.settings_win = None

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_body()
        self._build_footer()
        self._refresh_list()

        watched = [self.fmt, self.mode, self.out_mode, self.out_dir, self.overwrite, self.open_after,
                   *self.targets.values(), *self.compress_targets.values(),
                   *(v for k, v in self.vars.items() if k != "pages")]
        for var in watched:
            var.trace_add("write", lambda *_: self._save())
        self.bind("<Control-Key>", self._on_ctrl)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(60, self._poll)
        self.after(300, lambda: apply_window_icon(self))
        schedule_titlebar_style(self, TOOLBAR)
        if shell_integration.is_supported():
            self.after(1500, shell_integration.refresh_if_stale)   # the exe was moved or updated
        if initial_paths:
            self.after(150, lambda: self.add_external(initial_paths))
        if self.instance is not None:
            self.after(300, self._check_inbox)

    # ───────────── reusable widgets ─────────────

    def _card(self, parent, **kw):
        kw.setdefault("border_width", 1)
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, border_color=BORDER, **kw)

    def _primary(self, parent, text, command, width=150, **kw):
        kw.setdefault("height", 42)
        return ctk.CTkButton(parent, text=text, command=command, width=width, corner_radius=12,
                             fg_color=ORANGE, hover_color=ORANGE_H, text_color=ON_ORANGE,
                             text_color_disabled="#6B4A2E", font=self.f_bold, **kw)

    def _ghost(self, parent, text, command, width=110, height=42, **kw):
        kw.setdefault("border_width", 1)
        return ctk.CTkButton(parent, text=text, command=command, width=width, height=height, corner_radius=12,
                             fg_color="transparent", hover_color=PANEL_H, border_color=BORDER,
                             text_color=FG, text_color_disabled=FAINT_TEXT, font=self.f_body, **kw)

    def _entry(self, parent, var, placeholder="", **kw):
        kw.setdefault("height", 42)
        e = ctk.CTkEntry(parent, textvariable=var, corner_radius=10, fg_color=FIELD, border_color=BORDER,
                         border_width=1, text_color=FG, font=self.f_body, **kw)
        add_edit_support(e)
        if placeholder:  # CTkEntry ignores placeholder_text when a textvariable is used, so draw our own
            hint = tk.Label(e, text=placeholder, bg=FIELD, fg=MUTED, font=(FONT_FAMILY, 10), bd=0, cursor="xterm")
            hint.bind("<Button-1>", lambda _e: e.focus_set())

            def sync(*_):
                try:
                    if var.get():
                        hint.place_forget()
                    else:
                        hint.place(x=14, rely=0.5, anchor="w")
                except tk.TclError:
                    pass

            trace = var.trace_add("write", sync)

            def drop_trace(_e=None):
                try:
                    var.trace_remove("write", trace)
                except (tk.TclError, ValueError):
                    pass
            e.bind("<Destroy>", drop_trace, add="+")    # option rows are rebuilt; do not leak the trace
            sync()
        return e

    def _switch(self, parent, text, var):
        return ctk.CTkSwitch(parent, text=text, variable=var, onvalue=True, offvalue=False,
                             progress_color=ORANGE, button_color=FG, button_hover_color=FG,
                             fg_color=FIELD, text_color=FG, font=self.f_body)

    def _segmented(self, parent, values, var, command=None, height=34):
        """A segmented button whose labels may differ from the stored values (dict label -> value)."""
        labels = list(values) if isinstance(values, dict) else list(values)
        mapping = dict(values) if isinstance(values, dict) else {v: v for v in values}
        reverse = {v: k for k, v in mapping.items()}
        # One display variable per setting, kept for the app's lifetime: option rows are rebuilt often, and a
        # Tk variable must never be garbage-collected on the worker thread.
        shown = self._shown_vars.get(str(var))
        if shown is None:
            shown = self._shown_vars[str(var)] = tk.StringVar(self)
        shown.set(reverse.get(var.get(), labels[0]))

        def picked(label):
            var.set(mapping[label])
            if command:
                command()

        seg = ctk.CTkSegmentedButton(parent, values=labels, variable=shown, command=picked,
                                     selected_color=ORANGE, selected_hover_color=ORANGE_H, unselected_color=FIELD,
                                     unselected_hover_color=PANEL_H, fg_color=FIELD, text_color=FG,
                                     font=self.f_small, height=height, corner_radius=10)
        seg._shown_var = shown
        self._lockable.append(seg)
        return seg

    def _menu(self, parent, values, var, command=None, width=120):
        menu = ctk.CTkOptionMenu(parent, values=list(values), variable=var, width=width, height=32,
                                 corner_radius=10, fg_color=FIELD, button_color=FIELD, button_hover_color=PANEL_H,
                                 dropdown_fg_color=FIELD, dropdown_hover_color=PANEL_H, dropdown_text_color=FG,
                                 text_color=FG, font=self.f_small, dropdown_font=self.f_small,
                                 command=(lambda _v: command()) if command else None)
        self._lockable.append(menu)
        return menu

    def _labeled(self, parent, label, widget_factory):
        """LABEL ............ [widget]  in one row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row, text=label, font=self.f_small, text_color=MUTED, anchor="w").grid(row=0, column=0,
                                                                                           sticky="w")
        widget_factory(row).grid(row=0, column=1, sticky="e")
        return row

    def _format_grid(self, parent, targets, var, on_change=None, columns=4):
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.grid_columnconfigure(tuple(range(columns)), weight=1, uniform="fmt")
        buttons = {}

        def paint():
            for k, b in buttons.items():
                if k == var.get():
                    b.configure(fg_color=ORANGE, hover_color=ORANGE_H, text_color=ON_ORANGE)
                else:
                    b.configure(fg_color=FIELD, hover_color=PANEL_H, text_color=FG)

        def pick(k):
            if self.busy:
                return
            var.set(k)
            paint()
            self._reset_statuses()
            if on_change:
                on_change()

        for i, t in enumerate(targets):
            b = ctk.CTkButton(grid, text=t.label, height=36, corner_radius=10, font=self.f_bold,
                              text_color_disabled=FAINT_TEXT, command=lambda k=t.key: pick(k))
            b.grid(row=i // columns, column=i % columns, sticky="ew", padx=3, pady=3)
            buttons[t.key] = b
        if var.get() not in buttons:
            var.set(targets[0].key)
        paint()
        grid._paint = paint
        self._lockable.extend(buttons.values())
        return grid, buttons

    def _quality_row(self, parent):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text="QUALITY", font=self.f_section, text_color=ORANGE).grid(row=0, column=0, sticky="w")
        lbl = ctk.CTkLabel(box, text=str(self.quality), font=self.f_bold, text_color=FG)
        lbl.grid(row=0, column=1, sticky="e")
        slider = ctk.CTkSlider(box, from_=1, to=100, number_of_steps=99, progress_color=ORANGE,
                               button_color=ORANGE_H, button_hover_color=ORANGE, fg_color=FIELD,
                               command=lambda v: self._on_quality(v, lbl))
        slider.set(self.quality)
        slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self._lockable.append(slider)
        self.quality_slider, self.quality_lbl = slider, lbl
        return box

    def _tool_note(self, section, need):
        if need == "ffmpeg" and not self.tools.get("ffmpeg"):
            section.note("FFmpeg was not found, so these files cannot be converted. Reinstall PixNexa (it includes "
                         "FFmpeg) or put ffmpeg.exe in the “ffmpeg” folder next to PixNexa.exe.", DANGER)
        if need == "libreoffice" and not self.tools.get("libreoffice"):
            row = ctk.CTkFrame(section.frame, fg_color="transparent")
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text="Most conversions here need LibreOffice (free). It is not installed.",
                         font=self.f_small, text_color=DANGER, anchor="w", justify="left",
                         wraplength=200).grid(row=0, column=0, sticky="w")
            self._ghost(row, "Get LibreOffice", lambda: webbrowser.open(LIBREOFFICE_URL), width=120,
                        height=30).grid(row=0, column=1, sticky="e")
            section.add(row, pady=(6, 0))

    # ───────────── layout ─────────────

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color=TOOLBAR, corner_radius=0, height=64)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(bar, image=self.img_logo, text="").grid(row=0, column=0, padx=(22, 10), pady=12)
        ctk.CTkLabel(bar, text=APP_NAME, font=self.f_bold_lg, text_color=FG).grid(row=0, column=1)
        ctk.CTkLabel(bar, text=f"v{APP_VERSION}", font=self.f_small, text_color=MUTED, fg_color=PANEL,
                     corner_radius=8, width=56, height=22).grid(row=0, column=2, padx=10)
        ctk.CTkButton(bar, text="Settings", image=self.img_gear, compound="left", command=self.open_settings,
                      width=120, height=36, corner_radius=12, fg_color="transparent", hover_color=PANEL_H,
                      text_color=FG, font=self.f_body).grid(row=0, column=4, padx=(4, 18))
        ctk.CTkFrame(self, height=1, fg_color=BORDER, corner_radius=0).grid(row=1, column=0, sticky="ew")

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=28, pady=(22, 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=392)
        self._build_files_card(body)
        self._build_options_card(body)

    def _build_files_card(self, body):
        card = self._card(body)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="FILES", font=self.f_section, text_color=ORANGE).grid(row=0, column=0, sticky="w")
        self.count_lbl = ctk.CTkLabel(head, text="", font=self.f_small, text_color=MUTED)
        self.count_lbl.grid(row=0, column=1, sticky="w", padx=12)
        self.btn_add = self._primary(head, "Add files…", self.pick_files, width=120, height=34)
        self.btn_add.grid(row=0, column=2)
        self.btn_folder = self._ghost(head, "Add folder…", self.pick_folder, width=118, height=34)
        self.btn_folder.grid(row=0, column=3, padx=8)
        self.btn_clear = self._ghost(head, "Clear", self.clear_items, width=70, height=34)
        self.btn_clear.grid(row=0, column=4)

        self.list_frame = ctk.CTkScrollableFrame(card, fg_color="transparent", scrollbar_button_color=BORDER,
                                                 scrollbar_button_hover_color=ORANGE)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=(0, 12))

        self.empty = ctk.CTkFrame(card, fg_color="transparent")
        self.empty.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.empty.grid_columnconfigure(0, weight=1)
        self.empty.grid_rowconfigure((0, 5), weight=1)
        ctk.CTkLabel(self.empty, image=self.img_logo_empty, text="").grid(row=1, column=0)
        ctk.CTkLabel(self.empty, text="Drop files here" if self.dnd_ok else "No files yet",
                     font=self.f_big, text_color=FG).grid(row=2, column=0, pady=(14, 2))
        ctk.CTkLabel(self.empty, text="or use “Add files…” - you can convert many files at once.",
                     font=self.f_body, text_color=MUTED).grid(row=3, column=0)
        ctk.CTkLabel(self.empty, text="Images · PDF · video · audio · documents · spreadsheets · presentations\n"
                                      "data · archives · fonts · subtitles", font=self.f_small,
                     text_color=FAINT_TEXT, justify="center").grid(row=4, column=0, pady=(12, 0))

    def _build_options_card(self, body):
        card = self._card(body, width=392)
        card.grid(row=0, column=1, sticky="nsew")
        card.grid_propagate(False)          # fixed width: the file list gets all the remaining space
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        self.mode_switch = self._segmented(card, [MODE_CONVERT, MODE_COMPRESS], self.mode, self._on_mode,
                                           height=40)
        self.mode_switch.configure(font=self.f_bold)
        self.mode_switch.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))

        self.opt_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent", scrollbar_button_color=BORDER,
                                                 scrollbar_button_hover_color=ORANGE)
        self.opt_scroll.grid_columnconfigure(0, weight=1)
        self.opt_scroll.grid(row=1, column=0, sticky="nsew", padx=(12, 4), pady=(0, 4))

        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(bottom, height=1, fg_color=BORDER).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(bottom, text="SAVE TO", font=self.f_section, text_color=ORANGE).grid(
            row=1, column=0, sticky="w", pady=(0, 6))
        seg = ctk.CTkSegmentedButton(bottom, values=[OUT_SAME, OUT_CUSTOM], variable=self.out_mode,
                                     command=lambda _v: self._refresh_output(), selected_color=ORANGE,
                                     selected_hover_color=ORANGE_H, unselected_color=FIELD,
                                     unselected_hover_color=PANEL_H, fg_color=FIELD, text_color=FG,
                                     font=self.f_body, height=36, corner_radius=10)
        seg.grid(row=2, column=0, sticky="ew")
        self.custom_row = ctk.CTkFrame(bottom, fg_color="transparent")
        self.custom_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.custom_row.grid_columnconfigure(0, weight=1)
        self._entry(self.custom_row, self.out_dir, "Choose a folder", height=36).grid(row=0, column=0, sticky="ew")
        self._ghost(self.custom_row, "Browse…", self.pick_out_dir, width=90, height=36).grid(
            row=0, column=1, padx=(8, 0))
        self._switch(bottom, "Replace files with the same name", self.overwrite).grid(
            row=4, column=0, sticky="w", pady=(12, 0))
        self._switch(bottom, "Open the folder when finished", self.open_after).grid(
            row=5, column=0, sticky="w", pady=(10, 0))
        self._refresh_output()
        self._rebuild_options(force=True)

    def _build_footer(self):
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", padx=28, pady=(14, 22))
        foot.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(foot, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        left.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(left, text="Add some files to get started.", font=self.f_body,
                                   text_color=MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        self.bar = ctk.CTkProgressBar(left, height=8, corner_radius=4, fg_color=FIELD, progress_color=ORANGE)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.btn_convert = self._primary(foot, "Convert", self.on_convert, width=190)
        self.btn_convert.grid(row=0, column=1)

    # ───────────── options panel (built from the kinds of files in the list) ─────────────

    def _present(self):
        """{category key: number of files}, in the registry's order."""
        counts = {}
        for it in self.items:
            counts[it["category"]] = counts.get(it["category"], 0) + 1
        return {k: counts[k] for k in registry.ORDER if k in counts}

    def _rebuild_options(self, force=False):
        present = self._present()
        key = (self.mode.get(), tuple(present.items()))
        if key == self._section_key and not force:
            return
        self._section_key = key
        for child in self.opt_scroll.winfo_children():
            child.destroy()
        self._lockable = [self.mode_switch]
        self._sections = []
        compress = self.mode.get() == MODE_COMPRESS
        shown = present or {"image": None}            # with an empty list, show what images can become
        row = 0
        skipped = []
        for cat_key, count in shown.items():
            cat = registry.CATEGORIES[cat_key]
            if compress and not cat.can_compress:
                skipped.append(f"{cat.label} ({count})")
                continue
            builder = getattr(self, f"_section_{'compress' if compress else 'convert'}_{cat_key}", None)
            section = Section(self, self.opt_scroll, cat.label, count)
            (builder or self._section_convert_generic)(section, cat)
            section.frame.grid(row=row, column=0, sticky="ew", padx=(8, 8))
            section.refresh()
            self._sections.append(section)
            row += 1
        if skipped:
            section = Section(self, self.opt_scroll, "Skipped")
            section.note(f"{', '.join(skipped)}: these cannot be compressed and will be left as they are. "
                         "To make them smaller to send, pack them into a ZIP below.")
            section.frame.grid(row=row, column=0, sticky="ew", padx=(8, 8))
            row += 1
        if not present:
            ctk.CTkLabel(self.opt_scroll, text="Add files to see what each kind can become: PDF, video, audio, "
                                               "documents, archives and more get their own options here.",
                         font=self.f_small, text_color=FAINT_TEXT, anchor="w", justify="left",
                         wraplength=318).grid(row=row, column=0, sticky="ew", padx=8, pady=(14, 0))
            row += 1
        self._build_combine(row, present)
        if self.busy:
            self._lock(True)

    def _desc(self, section, cat, var, compress=False):
        targets = cat.compress_targets if compress else cat.targets
        label = section.note("")

        def update():
            t = next((t for t in targets if t.key == var.get()), None)
            label.configure(text=t.description if t else "")
        update()
        return update

    # images -------------------------------------------------------------

    def _resize_rows(self, section):
        v = self.vars
        section.add(self._labeled(section.frame, "Resize", lambda p: self._segmented(
            p, RESIZE_LABELS, v["resize_mode"], section.refresh)))
        box = ctk.CTkFrame(section.frame, fg_color="transparent")
        self._entry(box, v["max_width"], "width", width=90, height=32).pack(side="left")
        ctk.CTkLabel(box, text="×", text_color=MUTED, font=self.f_body).pack(side="left", padx=6)
        self._entry(box, v["max_height"], "height", width=90, height=32).pack(side="left")
        ctk.CTkLabel(box, text="px (the picture fits inside, never enlarged)", text_color=MUTED,
                     font=self.f_small, wraplength=120, justify="left").pack(side="left", padx=8)
        section.add(box, show=lambda: v["resize_mode"].get() == "max", pady=(6, 0))
        pbox = ctk.CTkFrame(section.frame, fg_color="transparent")
        self._entry(pbox, v["percent"], "50", width=90, height=32).pack(side="left")
        ctk.CTkLabel(pbox, text="% of the original size", text_color=MUTED, font=self.f_small).pack(side="left",
                                                                                                    padx=8)
        section.add(pbox, show=lambda: v["resize_mode"].get() == "percent", pady=(6, 0))

    def _section_convert_image(self, section, cat):
        var = self.targets["image"]
        update = None

        def changed():
            update()
            section.refresh()
        grid, _ = self._format_grid(section.frame, cat.targets, var, changed)
        section.add(grid, pady=(2, 0))
        update = self._desc(section, cat, var)
        if not self.tools.get("ffmpeg"):
            section.note("HEIC output needs FFmpeg, which was not found.", DANGER,
                         show=lambda: var.get() == "heic")
        section.add(self._quality_row(section.frame), show=lambda: core.FORMATS[var.get()].has_quality
                    or var.get() == "pdf", pady=(12, 0))
        self._resize_rows(section)
        flags = ctk.CTkFrame(section.frame, fg_color="transparent")
        self._switch(flags, "Grayscale", self.vars["grayscale"]).pack(anchor="w")
        self._switch(flags, "Remove metadata (EXIF, GPS, camera)", self.vars["strip_metadata"]).pack(
            anchor="w", pady=(8, 0))
        section.add(flags, pady=(12, 0))

    def _section_compress_image(self, section, cat):
        var = self.compress_targets["image"]
        section.add(self._labeled(section.frame, "Save as", lambda p: self._segmented(
            p, {t.label: t.key for t in cat.compress_targets}, var)), pady=(2, 0))
        section.add(self._quality_row(section.frame), pady=(10, 0))
        size = ctk.CTkFrame(section.frame, fg_color="transparent")
        size.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(size, text="Longest side at most", font=self.f_small, text_color=MUTED).grid(
            row=0, column=0, sticky="w")
        self._entry(size, self.vars["max_side"], "px", width=80, height=32).grid(row=0, column=1)
        ctk.CTkLabel(size, text="Target size at most", font=self.f_small, text_color=MUTED).grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        self._entry(size, self.vars["target_kb"], "KB", width=80, height=32).grid(row=1, column=1, pady=(6, 0))
        section.add(size, pady=(10, 0))
        section.note("Leave empty for no limit. With a target size, the best quality that fits is found "
                     "automatically.", FAINT_TEXT)
        flags = ctk.CTkFrame(section.frame, fg_color="transparent")
        self._switch(flags, "PNG: reduce to 256 colours", self.vars["png_palette"]).pack(anchor="w")
        self._switch(flags, "Remove metadata (EXIF, GPS, camera)", self.vars["strip_metadata"]).pack(
            anchor="w", pady=(8, 0))
        section.add(flags, pady=(10, 0))

    # PDF ----------------------------------------------------------------

    def _section_convert_pdf(self, section, cat):
        var = self.targets["pdf"]
        update = None

        def changed():
            update()
            section.refresh()
        grid, _ = self._format_grid(section.frame, cat.targets, var, changed, columns=5)
        section.add(grid, pady=(2, 0))
        update = self._desc(section, cat, var)
        section.add(self._labeled(section.frame, "Resolution (DPI)",
                                  lambda p: self._menu(p, DPIS, self.vars["dpi"], width=90)),
                    show=lambda: var.get() in ("png", "jpg"))
        section.add(self._quality_row(section.frame), show=lambda: var.get() == "jpg", pady=(10, 0))
        section.add(self._labeled(section.frame, "Pages (empty = all)", lambda p: self._entry(
            p, self.vars["pages"], "e.g. 1-3, 5", width=130, height=32)))

    def _section_compress_pdf(self, section, cat):
        section.add(self._labeled(section.frame, "Level", lambda p: self._segmented(
            p, list(PDF_LEVELS), self.vars["pdf_level"])), pady=(2, 0))
        section.note("Smallest: 72 dpi pictures · Balanced: 150 dpi · High quality: 300 dpi. Text and drawings "
                     "stay sharp; the result is never bigger than the original.", FAINT_TEXT)
        section.add(self._switch(section.frame, "Remove metadata (author, title, XMP)",
                                 self.vars["strip_metadata"]), pady=(10, 0))

    # video / audio -------------------------------------------------------

    def _video_quality_rows(self, section, show_codec):
        v = self.vars
        section.add(self._labeled(section.frame, "Quality", lambda p: self._segmented(
            p, {lbl: k for k, lbl in QUALITY_LABELS.items()}, v["video_quality"])))
        section.add(self._labeled(section.frame, "Resolution", lambda p: self._menu(
            p, RESOLUTIONS, v["resolution"], width=110)))
        section.add(self._labeled(section.frame, "Codec", lambda p: self._segmented(
            p, {"H.264": "h264", "H.265": "h265"}, v["video_codec"])), show=show_codec)

    def _section_convert_video(self, section, cat):
        var = self.targets["video"]
        update = None

        def changed():
            update()
            section.refresh()
        self._tool_note(section, "ffmpeg")
        grid, _ = self._format_grid(section.frame, cat.targets, var, changed)
        section.add(grid, pady=(2, 0))
        update = self._desc(section, cat, var)
        is_video = lambda: var.get() in ("mp4", "webm", "mkv", "mov", "avi", "gif")  # noqa: E731
        section.add(self._labeled(section.frame, "Quality", lambda p: self._segmented(
            p, {lbl: k for k, lbl in QUALITY_LABELS.items()}, self.vars["video_quality"])), show=is_video)
        section.add(self._labeled(section.frame, "Resolution", lambda p: self._menu(
            p, RESOLUTIONS, self.vars["resolution"], width=110)), show=is_video)
        section.add(self._labeled(section.frame, "Codec", lambda p: self._segmented(
            p, {"H.264": "h264", "H.265": "h265"}, self.vars["video_codec"])),
            show=lambda: var.get() in ("mp4", "mkv", "mov"))
        section.add(self._labeled(section.frame, "Sound bitrate (kbit/s)", lambda p: self._menu(
            p, BITRATES, self.vars["audio_bitrate"], width=90)),
            show=lambda: var.get() in ("mp3", "m4a", "ogg", "opus"))

    def _section_compress_video(self, section, cat):
        self._tool_note(section, "ffmpeg")
        section.note("Saved as MP4. Small quality and a lower resolution give the smallest files.", FAINT_TEXT)
        self._video_quality_rows(section, show_codec=None)

    def _section_convert_audio(self, section, cat):
        var = self.targets["audio"]
        update = None

        def changed():
            update()
            section.refresh()
        self._tool_note(section, "ffmpeg")
        grid, _ = self._format_grid(section.frame, cat.targets, var, changed, columns=3)
        section.add(grid, pady=(2, 0))
        update = self._desc(section, cat, var)
        section.add(self._labeled(section.frame, "Bitrate (kbit/s)", lambda p: self._menu(
            p, BITRATES, self.vars["audio_bitrate"], width=90)),
            show=lambda: var.get() in ("mp3", "m4a", "ogg", "opus"))

    def _section_compress_audio(self, section, cat):
        self._tool_note(section, "ffmpeg")
        var = self.compress_targets["audio"]
        section.add(self._labeled(section.frame, "Save as", lambda p: self._segmented(
            p, {t.label: t.key for t in cat.compress_targets}, var)), pady=(2, 0))
        section.add(self._labeled(section.frame, "Bitrate (kbit/s)", lambda p: self._menu(
            p, BITRATES, self.vars["audio_bitrate"], width=90)))
        section.note("128 kbit/s is fine for most music, 64-96 for speech.", FAINT_TEXT)

    # everything else ------------------------------------------------------

    def _section_convert_generic(self, section, cat):
        var = self.targets[cat.key]
        update = None

        def changed():
            update()
            section.refresh()
        if cat.needs:
            self._tool_note(section, cat.needs)
        grid, _ = self._format_grid(section.frame, cat.targets, var, changed)
        section.add(grid, pady=(2, 0))
        update = self._desc(section, cat, var)

    # combine ------------------------------------------------------------

    def _build_combine(self, row, present):
        n_images, n_pdfs, n_all = present.get("image", 0), present.get("pdf", 0), sum(present.values())
        if not n_all:
            return
        section = Section(self, self.opt_scroll, "Combine files")
        if n_images:
            box = ctk.CTkFrame(section.frame, fg_color="transparent")
            box.grid_columnconfigure(0, weight=1)
            b = self._ghost(box, f"{n_images} picture{'s' if n_images != 1 else ''} → one PDF",
                            self.on_images_to_pdf, height=36)
            b.grid(row=0, column=0, sticky="ew")
            self._lockable.append(b)
            seg = self._segmented(box, PAGE_SIZES, self.vars["page_size"], height=30)
            seg.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            section.add(box, pady=(2, 0))
        if n_pdfs >= 2:
            b = self._ghost(section.frame, f"Merge {n_pdfs} PDFs into one", self.on_merge_pdfs, height=36)
            self._lockable.append(b)
            section.add(b)
        box = ctk.CTkFrame(section.frame, fg_color="transparent")
        box.grid_columnconfigure(0, weight=1)
        b = self._ghost(box, f"Pack {n_all} file{'s' if n_all != 1 else ''} into one", self.on_pack, height=36)
        b.grid(row=0, column=0, sticky="ew")
        self._lockable.append(b)
        self._segmented(box, {"ZIP": "zip", "7Z": "7z", "TAR.GZ": "tar.gz"}, self.vars["archive_format"],
                        height=36).grid(row=0, column=1, padx=(8, 0))
        section.add(box)
        section.frame.grid(row=row, column=0, sticky="ew", padx=(8, 8), pady=(6, 10))
        section.refresh()

    # ───────────── options ─────────────

    def select_format(self, key, category="image"):
        if self.busy:
            return
        self.targets[category].set(key)
        self._section_key = None
        self._rebuild_options()
        self._reset_statuses()

    def _on_mode(self):
        self._rebuild_options()
        self._reset_statuses()
        self._refresh_list()

    def _on_quality(self, value, label=None):
        self.quality = int(round(value))
        if label is not None:
            label.configure(text=str(self.quality))
        self._save()

    def _refresh_output(self):
        if self.out_mode.get() == OUT_CUSTOM:
            self.custom_row.grid()
        else:
            self.custom_row.grid_remove()

    def _save(self):
        v = self.vars
        self.settings.update(
            format=self.fmt.get(), quality=self.quality, output=self.out_mode.get(),
            out_dir=self.out_dir.get().strip(), overwrite=bool(self.overwrite.get()),
            open_after=bool(self.open_after.get()), mode=self.mode.get(),
            targets={k: var.get() for k, var in self.targets.items()},
            compress_targets={k: var.get() for k, var in self.compress_targets.items()},
            **{k: (bool(var.get()) if isinstance(var, tk.BooleanVar) else var.get().strip())
               for k, var in v.items() if k != "pages"})
        store_settings(self.settings)

    def apply_settings(self, data):
        """Used by 'Reset options'."""
        self.fmt.set(data["format"])
        self.mode.set(data["mode"])
        for k, var in self.targets.items():
            var.set(data["targets"].get(k, DEFAULT_TARGETS[k]) if k != "image" else data["format"])
        for k, var in self.compress_targets.items():
            var.set(data["compress_targets"].get(k, DEFAULT_COMPRESS[k]))
        for k, var in self.vars.items():
            if k in data:
                var.set(data[k])
        self.out_mode.set(data["output"])
        self.out_dir.set(data["out_dir"])
        self.overwrite.set(data["overwrite"])
        self.open_after.set(data["open_after"])
        self.quality = data["quality"]
        self.mode_switch._shown_var.set(self.mode.get())
        self._refresh_output()
        self._rebuild_options(force=True)
        self._save()

    def pick_out_dir(self):
        folder = filedialog.askdirectory(parent=self, title="Choose the output folder")
        if folder:
            self.out_dir.set(folder)

    def open_settings(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.focus_set()
            return
        self.tools = registry.tools()               # LibreOffice may have been installed in the meantime
        self.settings_win = SettingsDialog(self)

    def _job_options(self):
        """The Options for a job, from the panel's current choices."""
        v = self.vars
        mode = self.mode.get()
        compress = mode == MODE_COMPRESS
        side = _int(v["max_side"].get())
        resize_mode = v["resize_mode"].get()
        max_w, max_h = _int(v["max_width"].get()), _int(v["max_height"].get())
        if compress:
            resize_mode, max_w, max_h = ("max", side, side) if side else ("none", 0, 0)
        dpi, quality = _int(v["dpi"].get(), 150, 36, 1200), self.quality
        if compress and "pdf" in self._present():
            dpi, pdf_quality = PDF_LEVELS.get(v["pdf_level"].get(), PDF_LEVELS["Balanced"])
        else:
            pdf_quality = quality
        return {
            "base": Options(
                out_dir=self._out_dir(), overwrite=bool(self.overwrite.get()), quality=quality,
                resize_mode=resize_mode, max_width=max_w, max_height=max_h,
                percent=_int(v["percent"].get(), 100, 1, 1000), grayscale=bool(v["grayscale"].get()) and not compress,
                strip_metadata=bool(v["strip_metadata"].get()),
                target_kb=_int(v["target_kb"].get()) if compress else 0, png_palette=bool(v["png_palette"].get()),
                dpi=dpi, pages=v["pages"].get().strip(), page_size=v["page_size"].get(),
                video_quality=v["video_quality"].get(), video_codec=v["video_codec"].get(),
                max_height_px=RESOLUTIONS.get(v["resolution"].get(), 0),
                audio_bitrate=_int(v["audio_bitrate"].get(), 192, 32, 512),
                archive_format=v["archive_format"].get(), cancel=self.stop_event),
            "pdf_quality": pdf_quality,
        }

    def _out_dir(self):
        if self.out_mode.get() == OUT_CUSTOM:
            return self.out_dir.get().strip().strip('"') or None
        return None

    # ───────────── adding / removing files ─────────────

    def pick_files(self):
        everything = " ".join(f"*{ext}" for ext in registry.all_extensions())
        types = [("All supported files", everything)]
        for cat in registry.CATEGORIES.values():
            types.append((cat.label, " ".join(f"*{ext}" for ext in cat.extensions)))
        types.append(("All files", "*.*"))
        files = filedialog.askopenfilenames(parent=self, title="Choose files", filetypes=types)
        if files:
            self.add_paths(files)

    def pick_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Choose a folder")
        if folder:
            self.add_paths([folder])

    def _on_drop(self, event):
        if not self.busy:
            self.add_paths(self.tk.splitlist(event.data))
        return event.action

    def _on_ctrl(self, e):
        if e.keysym.lower() == "o" or (sys.platform == "win32" and e.keycode == 79):   # Ctrl+O, any layout
            if not self.busy:
                self.pick_files()
            return "break"

    def add_paths(self, paths):
        """Add files (and the supported files inside dropped folders). Unsupported files are skipped."""
        known = {str(it["path"]).lower() for it in self.items}
        candidates = []
        for raw in paths:
            p = Path(raw)
            candidates.extend(registry.list_supported(p) if p.is_dir() else [p])
        added = skipped = duplicates = 0
        for p in candidates:
            key = str(p).lower()
            if key in known:
                duplicates += 1
                continue
            cat = registry.category_of(p) if p.is_file() else None
            if cat is None:
                skipped += 1
                continue
            try:
                info = describe(p, cat.key)
            except ConversionError:
                skipped += 1
                continue
            known.add(key)
            self._add_row(p, cat.key, info)
            added += 1
        parts = [f"Added {added} file{'s' if added != 1 else ''}"]
        if skipped:
            parts.append(f"{skipped} skipped (not supported)")
        if duplicates:
            parts.append(f"{duplicates} already in the list")
        self._set_status(", ".join(parts) + ".", OK if added else (DANGER if skipped else MUTED))
        self.bar.set(0)
        self._results_shown = False
        self._refresh_list()

    def _add_row(self, path, category, info):
        row = ctk.CTkFrame(self.list_frame, fg_color=FIELD, corner_radius=10)
        row.grid(row=len(self.items), column=0, sticky="ew", padx=4, pady=3)
        row.grid_columnconfigure(1, weight=1)
        thumb = make_thumbnail(path) if category == "image" else make_badge(path, category)
        ctk.CTkLabel(row, image=thumb, text="").grid(row=0, column=0, rowspan=2, padx=(10, 4), pady=10)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.grid(row=0, column=1, sticky="w", padx=(8, 8), pady=(10, 0))
        ctk.CTkLabel(text, text=shorten(path.name, 44), font=self.f_bold, text_color=FG, anchor="w").pack(anchor="w")
        detail = ctk.CTkLabel(text, text=info, font=self.f_small, text_color=MUTED, anchor="w")
        detail.pack(anchor="w")
        status = ctk.CTkLabel(row, text="Ready", font=self.f_small, text_color=MUTED, anchor="e")
        status.grid(row=0, column=2, padx=(8, 4), pady=(10, 0))
        item = {"path": path, "category": category, "info": info, "row": row, "status": status, "detail": detail,
                "thumb": thumb}
        remove = ctk.CTkButton(row, text="✕", width=30, height=30, corner_radius=8, fg_color="transparent",
                               hover_color=PANEL_H, text_color=MUTED, font=self.f_body,
                               command=lambda it=item: self.remove_item(it))
        remove.grid(row=0, column=3, padx=(0, 8), pady=(8, 0))
        item["remove"] = remove
        bar = ctk.CTkProgressBar(row, height=6, corner_radius=3, fg_color=PANEL, progress_color=PANEL)
        bar.set(0)
        bar.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 12), pady=(6, 12))
        item["bar"] = bar
        self.items.append(item)

    def remove_item(self, item):
        if self.busy or item not in self.items:
            return
        item["row"].destroy()
        self.items.remove(item)
        for i, it in enumerate(self.items):
            it["row"].grid(row=i, column=0, sticky="ew", padx=4, pady=3)
        self._refresh_list()

    def clear_items(self):
        if self.busy:
            return
        for it in self.items:
            it["row"].destroy()
        self.items.clear()
        self.bar.set(0)
        self._set_status("Add some files to get started.", MUTED)
        self._refresh_list()

    def _reset_statuses(self):
        for it in self.items:
            it["status"].configure(text="Ready", text_color=MUTED)
            it["detail"].configure(text=it["info"], text_color=MUTED)
            self._row_bar(it, "idle")
        self.bar.set(0)

    def _row_bar(self, item, state, value=None):
        """Per-file progress bar: idle (empty) / running (animated, or the fraction FFmpeg reports) /
        ok (full) / error (full, red)."""
        bar = item["bar"]
        if state == "progress":
            if item.get("bar_mode") != "determinate":
                bar.stop()
                bar.configure(mode="determinate", progress_color=ORANGE)
                item["bar_mode"] = "determinate"
            bar.set(value)
            return
        bar.stop()
        color = DANGER if state == "error" else (PANEL if state == "idle" else ORANGE)   # idle: no stray dot
        bar.configure(mode="determinate", progress_color=color)
        item["bar_mode"] = "determinate"
        if state == "running":
            bar.configure(mode="indeterminate")
            item["bar_mode"] = "indeterminate"
            bar.start()
        else:
            bar.set(1 if state in ("ok", "error") else 0)

    def _scroll_to(self, index):
        """Keep the file that is being converted in view."""
        try:
            self.list_frame._parent_canvas.yview_moveto(max(0, index - 1) / max(1, len(self.items)))
        except Exception:
            pass

    def _refresh_list(self):
        n = len(self.items)
        if n:
            self.empty.grid_remove()
            self.list_frame.grid()
        else:
            self.list_frame.grid_remove()
            self.empty.grid()
        self.count_lbl.configure(text=f"{n} file{'s' if n != 1 else ''}" if n else "")
        self.btn_clear.configure(state="normal" if n and not self.busy else "disabled")
        if not self.busy:
            verb = self.mode.get()
            if verb == MODE_COMPRESS:
                n = sum(1 for it in self.items if registry.CATEGORIES[it["category"]].can_compress)
            self.btn_convert.configure(text=f"{verb} {n} files" if n > 1 else verb)
            self._rebuild_options()

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    # ───────────── files from Explorer's right-click menu / a second launch ─────────────

    def _check_inbox(self):
        try:
            for paths in self.instance.collect():
                self.bring_to_front()
                if paths:
                    self.add_external(paths)
        except Exception:
            pass
        self.after(400, self._check_inbox)

    def add_external(self, paths):
        """Paths that arrive from outside the window. They wait if a conversion is running."""
        if self.busy:
            self._pending_paths.extend(paths)
            return
        if self._results_shown:                  # the last batch is finished: start a fresh list
            self.clear_items()
        self.add_paths(paths)

    def bring_to_front(self):
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(300, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass

    # ───────────── converting ─────────────

    def _start(self, job):
        if self.out_mode.get() == OUT_CUSTOM and not self._out_dir():
            self._set_status("Choose an output folder, or switch to “Next to the original”.", DANGER)
            return False
        self._reset_statuses()
        self.last_outputs = []
        self.stop_event.clear()
        self._set_busy(True)
        threading.Thread(target=self._worker, args=(job,), daemon=True).start()
        return True

    def on_convert(self):
        if self.busy:                       # the button turns into "Stop" while converting
            self.stop_event.set()
            self.btn_convert.configure(state="disabled", text="Stopping…")
            return
        if not self.items:
            self._set_status("Add some files first.", DANGER)
            return
        compress = self.mode.get() == MODE_COMPRESS
        opts = self._job_options()
        tasks = []
        for i, it in enumerate(self.items):
            cat = registry.CATEGORIES[it["category"]]
            if compress:
                target = self.compress_targets[cat.key].get() if cat.can_compress else None
            else:
                target = self.targets[cat.key].get()
            tasks.append((i, it["path"], cat.key, target))
        self._start({"kind": "files", "compress": compress, "tasks": tasks, **opts})

    def _combine(self, kind, category=None):
        if self.busy:
            return
        indices = [i for i, it in enumerate(self.items) if category is None or it["category"] == category]
        if not indices:
            return
        opts = self._job_options()
        self._start({"kind": kind, "indices": indices, "paths": [self.items[i]["path"] for i in indices], **opts})

    def on_images_to_pdf(self):
        self._combine("images_pdf", "image")

    def on_merge_pdfs(self):
        self._combine("merge_pdf", "pdf")

    def on_pack(self):
        self._combine("pack")

    def _lock(self, busy):
        state = "disabled" if busy else "normal"
        for w in self._lockable:
            try:
                w.configure(state=state)
            except Exception:
                pass

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_add, self.btn_folder):
            b.configure(state=state)
        for it in self.items:
            it["remove"].configure(state=state)
        self._lock(busy)
        if busy:
            self.btn_clear.configure(state="disabled")
            self.btn_convert.configure(state="normal", text="Stop")
        else:
            self.btn_convert.configure(state="normal")
            self._refresh_list()

    def _progress_cb(self, index):
        last = [0.0, 0.0]

        def cb(value):
            now = time.monotonic()
            if value >= 1 or value - last[0] >= 0.01 and now - last[1] > 0.1:
                last[0], last[1] = value, now
                self.q.put(("prog", index, value))
        return cb

    def _worker(self, job):                 # runs in a background thread: talks to the GUI only via the queue
        try:
            if job["kind"] == "files":
                self._work_files(job)
            else:
                self._work_combine(job)
        except Exception as exc:            # never let the thread die silently
            self.q.put(("done", 0, 1, False, f"Unexpected error: {exc}"))

    def _work_files(self, job):
        tasks = job["tasks"]
        total = len(tasks)
        done = failed = skipped = 0
        for n, (i, src, cat_key, target) in enumerate(tasks):
            if self.stop_event.is_set():
                break
            if target is None:
                skipped += 1
                self.q.put(("skip", i, n + 1, total))
                continue
            self.q.put(("start", i, n, total))
            options = dataclasses.replace(job["base"])
            if cat_key == "pdf" and job["compress"]:
                options.quality = job["pdf_quality"]
            before = path_size(src)
            try:
                if job["compress"]:
                    result = registry.compress_file(src, options, self._progress_cb(i), target, category=cat_key)
                else:
                    result = registry.convert_file(src, target, options, self._progress_cb(i), category=cat_key)
                done += 1
                after = sum(path_size(p) for p in result.outputs)
                self.q.put(("ok", i, n + 1, total, result.outputs, before, after, result.note))
            except Cancelled:
                self.q.put(("err", i, n + 1, total, "Stopped."))
                break
            except ConversionError as exc:
                failed += 1
                self.q.put(("err", i, n + 1, total, str(exc)))
            except Exception as exc:        # never let the thread die silently
                failed += 1
                self.q.put(("err", i, n + 1, total, f"Unexpected error: {exc}"))
        self.q.put(("done", done, failed, self.stop_event.is_set(), None, skipped))

    def _work_combine(self, job):
        indices, paths, options = job["indices"], job["paths"], job["base"]
        for i in indices:
            self.q.put(("start", i, 0, 1))

        def cb(value):
            self.q.put(("combine_prog", indices, value))
        before = sum(path_size(p) for p in paths)
        try:
            if job["kind"] == "images_pdf":
                out = registry.images_to_pdf(paths, options, cb)
            elif job["kind"] == "merge_pdf":
                out = registry.merge_pdfs(paths, options, cb)
            else:
                out = registry.pack_files(paths, options.archive_format, options, cb)
            self.q.put(("combine_ok", indices, out, before, path_size(out)))
            self.q.put(("done", 1, 0, False, None, 0))
        except Cancelled:
            self.q.put(("combine_err", indices, "Stopped."))
            self.q.put(("done", 0, 0, True, None, 0))
        except ConversionError as exc:
            self.q.put(("combine_err", indices, str(exc)))
            self.q.put(("done", 0, 1, False, str(exc), 0))

    def _result_text(self, outputs, before, after, note, compress):
        first = Path(outputs[0])
        if len(outputs) > 1:
            name, size = f"{len(outputs)} files ({first.name}, …)", human_size(after)
        elif first.is_dir():
            count = sum(1 for f in first.rglob("*") if f.is_file())
            name, size = f"{first.name}/", f"{count} file{'s' if count != 1 else ''}, {human_size(after)}"
        else:
            name, size = first.name, human_size(after)
        if compress and before and not first.is_dir():
            pct = round((after - before) / before * 100)
            size = f"{human_size(before)} → {human_size(after)} ({'+' if pct > 0 else '−' if pct < 0 else '±'}{abs(pct)}%)"
        text = f"→ {name} · {size}" + (f" · {note}" if note else "")
        if compress and before and after and after < before:
            status = f"✓ −{round((before - after) / before * 100)}%"
        else:
            status = "✓ Done"
        return shorten(text, 78), status

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "start":
                    _, i, n, total = msg
                    verb = "Compressing" if self.mode.get() == MODE_COMPRESS else "Converting"
                    self.items[i]["status"].configure(text=f"{verb}…", text_color=ORANGE_H)
                    self._row_bar(self.items[i], "running")
                    self._scroll_to(i)
                    self._set_status(f"{verb} {n + 1} of {total}…", MUTED)
                elif kind == "prog":
                    _, i, value = msg
                    if 0 <= i < len(self.items):
                        self._row_bar(self.items[i], "progress", value)
                elif kind == "ok":
                    _, i, n, total, outputs, before, after, note = msg
                    item = self.items[i]
                    self._row_bar(item, "ok")
                    self.last_outputs.extend(Path(p) for p in outputs)
                    detail, status = self._result_text(outputs, before, after, note,
                                                       self.mode.get() == MODE_COMPRESS)
                    item["status"].configure(text=status, text_color=OK)
                    item["detail"].configure(text=detail, text_color=OK)
                    self._progress(n, total)
                elif kind == "skip":
                    _, i, n, total = msg
                    self.items[i]["status"].configure(text="Skipped", text_color=FAINT_TEXT)
                    self.items[i]["detail"].configure(text="This kind of file cannot be compressed.",
                                                      text_color=FAINT_TEXT)
                    self._progress(n, total)
                elif kind == "err":
                    _, i, n, total, text = msg
                    item = self.items[i]
                    self._row_bar(item, "error")
                    item["status"].configure(text="✗ Failed", text_color=DANGER)
                    item["detail"].configure(text=shorten(text, 80), text_color=DANGER)
                    self._progress(n, total)
                elif kind == "combine_prog":
                    _, indices, value = msg
                    for i in indices:
                        self._row_bar(self.items[i], "progress", value)
                    self.bar.set(value)
                elif kind == "combine_ok":
                    _, indices, out, before, after = msg
                    self.last_outputs.append(Path(out))
                    for i in indices:
                        self._row_bar(self.items[i], "ok")
                        self.items[i]["status"].configure(text="✓ Combined", text_color=OK)
                        self.items[i]["detail"].configure(text=shorten(f"→ {Path(out).name}", 74), text_color=OK)
                    self.bar.set(1)
                    self._combined = (Path(out), before, after)
                elif kind == "combine_err":
                    _, indices, text = msg
                    for i in indices:
                        self._row_bar(self.items[i], "error")
                        self.items[i]["status"].configure(text="✗ Failed", text_color=DANGER)
                        self.items[i]["detail"].configure(text=shorten(text, 80), text_color=DANGER)
                elif kind == "done":
                    self._finished(*msg[1:])
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _progress(self, n, total):
        self.bar.set(n / max(1, total))

    def _finished(self, done, failed, stopped, message=None, skipped=0):
        self._set_busy(False)
        verb = "compressed" if self.mode.get() == MODE_COMPRESS else "converted"
        combined = getattr(self, "_combined", None)
        self._combined = None
        if stopped:
            text, color = f"Stopped. {done} {verb}.", MUTED
        elif combined is not None:
            out, before, after = combined
            text, color = f"Done! Created {out.name} ({human_size(after)}).", OK
        elif message:
            text, color = shorten(message, 110), DANGER
        elif failed and done:
            text, color = f"{done} {verb}, {failed} failed - see the list.", DANGER
        elif failed:
            text, color = f"Nothing {verb}: {failed} failed - see the list.", DANGER
        elif done:
            text, color = f"Done! {done} file{'s' if done != 1 else ''} {verb}.", OK
        else:
            text, color = "Nothing to do: none of these files can be compressed.", MUTED
        if skipped and not stopped and done:
            text += f" {skipped} skipped."
        self._set_status(text, color)
        self._results_shown = True
        if self._pending_paths:
            waiting, self._pending_paths = self._pending_paths, []
            self.add_external(waiting)
        if self.open_after.get() and self.last_outputs:
            if len(self.last_outputs) == 1:
                reveal(self.last_outputs[0])
            else:
                open_path(self.last_outputs[0].parent)

    def on_close(self):
        self.stop_event.set()
        self._save()
        if self.instance is not None:
            self.instance.release()
        self.destroy()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    # Used by the installer: add / remove the Explorer menu item without opening a window.
    if "--register-menu" in argv:
        sys.exit(0 if shell_integration.register() else 1)
    if "--unregister-menu" in argv:
        sys.exit(0 if shell_integration.unregister() else 1)
    if "--self-test" in argv:                  # used by the build: one tiny conversion per engine, no window
        import self_test
        sys.exit(min(1, self_test.run()))

    paths = [a for a in argv if not a.startswith("--")]
    instance = SingleInstance(settings_dir())
    if not instance.acquire():          # the app is already open: hand it the files and quit
        instance.send(paths)
        return
    App(paths, instance).mainloop()


if __name__ == "__main__":
    main()

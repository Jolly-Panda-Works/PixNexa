#!/usr/bin/env python3
"""Image Format Converter - desktop app.

Add images (button, drag and drop, or a whole folder), pick a target format, press Convert.
Dark + orange interface, shared with SnapshotAll.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import PIL._tkinter_finder  # noqa: F401  (CustomTkinter imports Pillow's Tk support lazily, so PyInstaller
import PIL.ImageTk  # noqa: F401              would miss it unless it is imported here)
from PIL import Image, ImageOps

import converter_core as core
from app_common import APP_AUTHOR, APP_LICENSE, APP_NAME, APP_REPO, APP_SLUG, APP_URL, APP_VERSION, APP_WEBSITE

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

FONT_FAMILY = "Segoe UI"
OUT_SAME, OUT_CUSTOM = "Next to the original", "Custom folder"

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
    open_path(path.parent)


def human_size(n):
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"


def shorten(text, limit):
    return text if len(text) <= limit else text[: limit - 1] + "…"


THUMB = 56
_THUMB_BG = (31, 24, 19, 255)


def make_thumbnail(path):
    """A small square preview of an image (a dark placeholder tile if it cannot be drawn)."""
    tile = Image.new("RGBA", (THUMB, THUMB), _THUMB_BG)
    try:
        with Image.open(path) as im:
            if im.format == "JPEG":
                im.draft("RGB", (THUMB * 2, THUMB * 2))      # decode a reduced size: much faster for big photos
            im.thumbnail((THUMB * 2, THUMB * 2))
            im = ImageOps.exif_transpose(im) or im
            small = im.convert("RGBA")
        small.thumbnail((THUMB, THUMB), Image.LANCZOS)
        tile.alpha_composite(small, ((THUMB - small.width) // 2, (THUMB - small.height) // 2))
    except Exception:
        pass
    return ctk.CTkImage(light_image=tile, dark_image=tile, size=(THUMB, THUMB))


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


def settings_file():
    base = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
    return base / APP_SLUG / "settings.json"


DEFAULT_SETTINGS = {"format": "png", "quality": core.DEFAULT_QUALITY, "output": OUT_SAME,
                    "out_dir": "", "overwrite": False, "open_after": True}


def load_settings():
    data = dict(DEFAULT_SETTINGS)
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
    try:
        data["quality"] = max(1, min(100, int(data["quality"])))
    except (TypeError, ValueError):
        data["quality"] = core.DEFAULT_QUALITY
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
        self.geometry("480x440")
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

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=28, pady=(18, 0))
        foot.columnconfigure(0, weight=1)
        app._ghost(foot, "Reset options", self.reset, width=130).grid(row=0, column=0, sticky="w")
        app._primary(foot, "Done", self.destroy, width=110).grid(row=0, column=1, sticky="e")
        self.after(150, self._focus)

    def _focus(self):
        try:
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

    def reset(self):
        self.app.apply_settings(dict(DEFAULT_SETTINGS))


# ───────────────────────── main window ─────────────────────────

class App(ctk.CTk, _DnDBase):
    def __init__(self):
        set_windows_app_id()
        super().__init__(fg_color=BG)
        apply_window_icon(self)
        self.title(f"{APP_NAME} - JPG, PNG, WEBP, BMP, GIF, TIFF, ICO")
        self.geometry("1040x700")
        self.minsize(940, 640)

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
        self.items = []                 # {"path", "info", "row", "status"}
        self.busy = False
        self.stop_event = threading.Event()
        self.q = queue.Queue()
        self.last_outputs = []

        self.fmt = tk.StringVar(value=self.settings["format"])
        self.out_mode = tk.StringVar(value=self.settings["output"])
        self.out_dir = tk.StringVar(value=self.settings["out_dir"])
        self.overwrite = tk.BooleanVar(value=self.settings["overwrite"])
        self.open_after = tk.BooleanVar(value=self.settings["open_after"])
        self.quality = self.settings["quality"]
        self.settings_win = None

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_body()
        self._build_footer()
        self._refresh_options()
        self._refresh_list()

        for var in (self.fmt, self.out_mode, self.out_dir, self.overwrite, self.open_after):
            var.trace_add("write", lambda *_: self._save())
        self.bind("<Control-Key>", self._on_ctrl)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(60, self._poll)
        self.after(300, lambda: apply_window_icon(self))
        schedule_titlebar_style(self, TOOLBAR)

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
                if var.get():
                    hint.place_forget()
                else:
                    hint.place(x=14, rely=0.5, anchor="w")

            var.trace_add("write", sync)
            sync()
        return e

    def _switch(self, parent, text, var):
        return ctk.CTkSwitch(parent, text=text, variable=var, onvalue=True, offvalue=False,
                             progress_color=ORANGE, button_color=FG, button_hover_color=FG,
                             fg_color=FIELD, text_color=FG, font=self.f_body)

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
        body.grid_columnconfigure(1, weight=0, minsize=372)
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
        ctk.CTkLabel(head, text="IMAGES", font=self.f_section, text_color=ORANGE).grid(row=0, column=0, sticky="w")
        self.count_lbl = ctk.CTkLabel(head, text="", font=self.f_small, text_color=MUTED)
        self.count_lbl.grid(row=0, column=1, sticky="w", padx=12)
        self.btn_add = self._primary(head, "Add images…", self.pick_files, width=130, height=34)
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
        self.empty.grid_rowconfigure((0, 4), weight=1)
        ctk.CTkLabel(self.empty, image=self.img_logo_empty, text="").grid(row=1, column=0)
        ctk.CTkLabel(self.empty, text="Drop images here" if self.dnd_ok else "No images yet",
                     font=self.f_big, text_color=FG).grid(row=2, column=0, pady=(14, 2))
        ctk.CTkLabel(self.empty, text="or use “Add images…” - you can convert many files at once.",
                     font=self.f_body, text_color=MUTED).grid(row=3, column=0)

    def _build_options_card(self, body):
        card = self._card(body, width=372)
        card.grid(row=0, column=1, sticky="nsew")
        card.grid_propagate(False)          # fixed width: the file list gets all the remaining space
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="CONVERT TO", font=self.f_section, text_color=ORANGE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(16, 8))
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.grid(row=1, column=0, sticky="ew", padx=20)
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="fmt")
        self.fmt_buttons = {}
        for i, key in enumerate(core.FORMAT_KEYS):
            b = ctk.CTkButton(grid, text=core.FORMATS[key].label, height=40, corner_radius=10, font=self.f_bold,
                              command=lambda k=key: self.select_format(k))
            b.grid(row=i // 4, column=i % 4, sticky="ew", padx=3, pady=3)
            self.fmt_buttons[key] = b
        self.fmt_desc = ctk.CTkLabel(card, text="", font=self.f_small, text_color=MUTED, anchor="w",
                                     justify="left", wraplength=320)
        self.fmt_desc.grid(row=2, column=0, sticky="w", padx=20, pady=(8, 0))

        # quality (jpg / webp only)
        self.quality_box = ctk.CTkFrame(card, fg_color="transparent")
        self.quality_box.grid(row=3, column=0, sticky="ew", padx=20, pady=(16, 0))
        self.quality_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.quality_box, text="QUALITY", font=self.f_section, text_color=ORANGE).grid(
            row=0, column=0, sticky="w")
        self.quality_lbl = ctk.CTkLabel(self.quality_box, text=str(self.quality), font=self.f_bold, text_color=FG)
        self.quality_lbl.grid(row=0, column=1, sticky="e")
        self.quality_slider = ctk.CTkSlider(self.quality_box, from_=1, to=100, number_of_steps=99,
                                            command=self._on_quality, progress_color=ORANGE,
                                            button_color=ORANGE_H, button_hover_color=ORANGE, fg_color=FIELD)
        self.quality_slider.set(self.quality)
        self.quality_slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # output folder
        ctk.CTkLabel(card, text="SAVE TO", font=self.f_section, text_color=ORANGE).grid(
            row=4, column=0, sticky="w", padx=20, pady=(18, 8))
        ctk.CTkSegmentedButton(card, values=[OUT_SAME, OUT_CUSTOM], variable=self.out_mode,
                               command=lambda _v: self._refresh_options(), selected_color=ORANGE,
                               selected_hover_color=ORANGE_H, unselected_color=FIELD,
                               unselected_hover_color=PANEL_H, fg_color=FIELD, text_color=FG,
                               font=self.f_body, height=38, corner_radius=10).grid(
            row=5, column=0, sticky="ew", padx=20)
        self.custom_row = ctk.CTkFrame(card, fg_color="transparent")
        self.custom_row.grid(row=6, column=0, sticky="ew", padx=20, pady=(8, 0))
        self.custom_row.grid_columnconfigure(0, weight=1)
        self._entry(self.custom_row, self.out_dir, "Choose a folder", height=38).grid(row=0, column=0, sticky="ew")
        self._ghost(self.custom_row, "Browse…", self.pick_out_dir, width=90, height=38).grid(
            row=0, column=1, padx=(8, 0))

        self._switch(card, "Replace files with the same name", self.overwrite).grid(
            row=7, column=0, sticky="w", padx=20, pady=(18, 0))
        self._switch(card, "Open the folder when finished", self.open_after).grid(
            row=8, column=0, sticky="w", padx=20, pady=(12, 0))
        ctk.CTkLabel(card, text="SVG is not supported: it is a vector format, not a raster image.",
                     font=self.f_small, text_color=FAINT_TEXT, anchor="w", justify="left",
                     wraplength=320).grid(row=9, column=0, sticky="w", padx=20, pady=(16, 16))

    def _build_footer(self):
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", padx=28, pady=(14, 22))
        foot.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(foot, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        left.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(left, text="Add some images to get started.", font=self.f_body,
                                   text_color=MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        self.bar = ctk.CTkProgressBar(left, height=8, corner_radius=4, fg_color=FIELD, progress_color=ORANGE)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.btn_convert = self._primary(foot, "Convert", self.on_convert, width=190)
        self.btn_convert.grid(row=0, column=1)

    # ───────────── options ─────────────

    def select_format(self, key):
        if self.busy:
            return
        self.fmt.set(key)
        self._refresh_options()
        self._reset_statuses()

    def _on_quality(self, value):
        self.quality = int(round(value))
        self.quality_lbl.configure(text=str(self.quality))
        self._save()

    def _refresh_options(self):
        key = self.fmt.get()
        for k, b in self.fmt_buttons.items():
            if k == key:
                b.configure(fg_color=ORANGE, hover_color=ORANGE_H, text_color=ON_ORANGE)
            else:
                b.configure(fg_color=FIELD, hover_color=PANEL_H, text_color=FG)
        self.fmt_desc.configure(text=core.FORMATS[key].description)
        if core.FORMATS[key].has_quality:
            self.quality_box.grid()
        else:
            self.quality_box.grid_remove()
        if self.out_mode.get() == OUT_CUSTOM:
            self.custom_row.grid()
        else:
            self.custom_row.grid_remove()

    def _save(self):
        self.settings.update(format=self.fmt.get(), quality=self.quality, output=self.out_mode.get(),
                             out_dir=self.out_dir.get().strip(), overwrite=bool(self.overwrite.get()),
                             open_after=bool(self.open_after.get()))
        store_settings(self.settings)

    def apply_settings(self, data):
        """Used by 'Reset options'."""
        self.fmt.set(data["format"])
        self.out_mode.set(data["output"])
        self.out_dir.set(data["out_dir"])
        self.overwrite.set(data["overwrite"])
        self.open_after.set(data["open_after"])
        self.quality = data["quality"]
        self.quality_slider.set(self.quality)
        self.quality_lbl.configure(text=str(self.quality))
        self._refresh_options()
        self._save()

    def pick_out_dir(self):
        folder = filedialog.askdirectory(parent=self, title="Choose the output folder")
        if folder:
            self.out_dir.set(folder)

    def open_settings(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.focus_set()
            return
        self.settings_win = SettingsDialog(self)

    # ───────────── adding / removing images ─────────────

    def pick_files(self):
        patterns = " ".join(f"*{ext}" for ext in core.INPUT_EXTENSIONS)
        files = filedialog.askopenfilenames(parent=self, title="Choose images",
                                            filetypes=[("Images", patterns), ("All files", "*.*")])
        if files:
            self.add_paths(files)

    def pick_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Choose a folder with images")
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
        """Add files (and the images inside dropped folders). Anything that is not an image is skipped."""
        known = {str(it["path"]).lower() for it in self.items}
        candidates = []
        for raw in paths:
            p = Path(raw)
            candidates.extend(core.list_images(p) if p.is_dir() else [p])
        added = skipped = duplicates = 0
        for p in candidates:
            key = str(p).lower()
            if key in known:
                duplicates += 1
                continue
            try:
                info = core.describe_image(p)
            except core.ConversionError:
                skipped += 1
                continue
            known.add(key)
            self._add_row(p, info)
            added += 1
        parts = [f"Added {added} image{'s' if added != 1 else ''}"]
        if skipped:
            parts.append(f"{skipped} skipped (not an image)")
        if duplicates:
            parts.append(f"{duplicates} already in the list")
        self._set_status(", ".join(parts) + ".", OK if added else (DANGER if skipped else MUTED))
        self.bar.set(0)
        self._refresh_list()

    def _add_row(self, path, info):
        row = ctk.CTkFrame(self.list_frame, fg_color=FIELD, corner_radius=10)
        row.grid(row=len(self.items), column=0, sticky="ew", padx=4, pady=3)
        row.grid_columnconfigure(1, weight=1)
        thumb = make_thumbnail(path)
        ctk.CTkLabel(row, image=thumb, text="").grid(row=0, column=0, rowspan=2, padx=(10, 4), pady=10)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.grid(row=0, column=1, sticky="w", padx=(8, 8), pady=(10, 0))
        ctk.CTkLabel(text, text=shorten(path.name, 40), font=self.f_bold, text_color=FG, anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text=f"{info.format} · {info.width} × {info.height} · {human_size(info.size_bytes)}",
                     font=self.f_small, text_color=MUTED, anchor="w").pack(anchor="w")
        status = ctk.CTkLabel(row, text="Ready", font=self.f_small, text_color=MUTED, anchor="e")
        status.grid(row=0, column=2, padx=(8, 4), pady=(10, 0))
        item = {"path": path, "info": info, "row": row, "status": status, "thumb": thumb}
        remove = ctk.CTkButton(row, text="✕", width=30, height=30, corner_radius=8, fg_color="transparent",
                               hover_color=PANEL_H, text_color=MUTED, font=self.f_body,
                               command=lambda it=item: self.remove_item(it))
        remove.grid(row=0, column=3, padx=(0, 8), pady=(8, 0))
        item["remove"] = remove
        bar = ctk.CTkProgressBar(row, height=6, corner_radius=3, fg_color=PANEL, progress_color=ORANGE)
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
        self._set_status("Add some images to get started.", MUTED)
        self._refresh_list()

    def _reset_statuses(self):
        for it in self.items:
            it["status"].configure(text="Ready", text_color=MUTED)
            self._row_bar(it, "idle")
        self.bar.set(0)

    def _row_bar(self, item, state):
        """Per-image progress bar: idle (empty) / running (animated) / ok (full) / error (full, red)."""
        bar = item["bar"]
        bar.stop()
        color = DANGER if state == "error" else (PANEL if state == "idle" else ORANGE)   # idle: no stray dot
        bar.configure(mode="determinate", progress_color=color)
        if state == "running":
            bar.configure(mode="indeterminate")
            bar.start()
        else:
            bar.set(1 if state in ("ok", "error") else 0)

    def _scroll_to(self, index):
        """Keep the image that is being converted in view."""
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
        self.count_lbl.configure(text=f"{n} image{'s' if n != 1 else ''}" if n else "")
        self.btn_clear.configure(state="normal" if n and not self.busy else "disabled")
        if not self.busy:
            self.btn_convert.configure(text=f"Convert {n} images" if n > 1 else "Convert")

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    # ───────────── converting ─────────────

    def on_convert(self):
        if self.busy:                       # the button turns into "Stop" while converting
            self.stop_event.set()
            self.btn_convert.configure(state="disabled", text="Stopping…")
            return
        if not self.items:
            self._set_status("Add some images first.", DANGER)
            return
        out_dir = None
        if self.out_mode.get() == OUT_CUSTOM:
            out_dir = self.out_dir.get().strip().strip('"')
            if not out_dir:
                self._set_status("Choose an output folder, or switch to “Next to the original”.", DANGER)
                return
        self._reset_statuses()
        self.last_outputs = []
        self.stop_event.clear()
        self._set_busy(True)
        job = {"files": [it["path"] for it in self.items], "fmt": self.fmt.get(), "out_dir": out_dir,
               "quality": self.quality, "overwrite": bool(self.overwrite.get())}
        threading.Thread(target=self._worker, args=(job,), daemon=True).start()

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_add, self.btn_folder):
            b.configure(state=state)
        for it in self.items:
            it["remove"].configure(state=state)
        for b in self.fmt_buttons.values():
            b.configure(state=state)
        if busy:
            self.btn_clear.configure(state="disabled")
            self.btn_convert.configure(state="normal", text="Stop")
        else:
            self.btn_convert.configure(state="normal")
            self._refresh_list()

    def _worker(self, job):                 # runs in a background thread: talks to the GUI only via the queue
        total = len(job["files"])
        done = failed = 0
        for i, src in enumerate(job["files"]):
            if self.stop_event.is_set():
                break
            self.q.put(("start", i, total))
            try:
                dst = core.convert_image(src, job["fmt"], job["out_dir"], quality=job["quality"],
                                         overwrite=job["overwrite"])
                done += 1
                self.q.put(("ok", i, total, dst))
            except core.ConversionError as exc:
                failed += 1
                self.q.put(("err", i, total, str(exc)))
            except Exception as exc:        # never let the thread die silently
                failed += 1
                self.q.put(("err", i, total, f"Unexpected error: {exc}"))
        self.q.put(("done", done, failed, self.stop_event.is_set()))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "start":
                    _, i, total = msg
                    self.items[i]["status"].configure(text="Converting…", text_color=ORANGE_H)
                    self._row_bar(self.items[i], "running")
                    self._scroll_to(i)
                    self._set_status(f"Converting {i + 1} of {total}…", MUTED)
                elif kind == "ok":
                    _, i, total, dst = msg
                    self._row_bar(self.items[i], "ok")
                    self.last_outputs.append(Path(dst))
                    self.items[i]["status"].configure(text=f"✓ {shorten(Path(dst).name, 28)}", text_color=OK)
                    self._progress(i + 1, total)
                elif kind == "err":
                    _, i, total, text = msg
                    self._row_bar(self.items[i], "error")
                    self.items[i]["status"].configure(text=f"✗ {shorten(text, 34)}", text_color=DANGER)
                    self._progress(i + 1, total)
                elif kind == "done":
                    self._finished(*msg[1:])
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _progress(self, n, total):
        self.bar.set(n / total)

    def _finished(self, done, failed, stopped):
        self._set_busy(False)
        if stopped:
            text, color = f"Stopped. {done} converted.", MUTED
        elif failed and done:
            text, color = f"{done} converted, {failed} failed - see the list.", DANGER
        elif failed:
            text, color = f"Nothing converted: {failed} failed - see the list.", DANGER
        else:
            text, color = f"Done! {done} image{'s' if done != 1 else ''} converted.", OK
        self._set_status(text, color)
        if self.open_after.get() and self.last_outputs:
            if len(self.last_outputs) == 1:
                reveal(self.last_outputs[0])
            else:
                open_path(self.last_outputs[0].parent)

    def on_close(self):
        self.stop_event.set()
        self._save()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

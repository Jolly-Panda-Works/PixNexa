"""Windows Explorer integration: "Convert with PixNexa" in the right-click menu of images.

Entries are written for the current user only (HKEY_CURRENT_USER), so no administrator rights are needed.
They live under SystemFileAssociations, which adds a menu item without changing which program opens the file.
The menu item simply starts the app with the clicked file; everything else happens inside the app.

On Windows 11 the item appears under "Show more options" (the classic menu).
"""
import sys
from pathlib import Path

import converter_core as core
from app_common import APP_BRAND, APP_SLUG, LEGACY_SLUG

try:
    import winreg
except ImportError:  # not Windows
    winreg = None

VERB = f"{APP_SLUG}.Convert"
LEGACY_VERB = f"{LEGACY_SLUG}.Convert"   # written by versions before the PixNexa rebrand
LABEL = f"Convert with {APP_BRAND}"
BASE = r"Software\Classes\SystemFileAssociations"
_PROBE_EXT = ".png"


def is_supported():
    return sys.platform == "win32" and winreg is not None


def launch_command():
    """(command line for the menu item, icon) for the way the app is running right now."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return f'"{exe}" "%1"', f'"{exe}",0'
    python = Path(sys.executable)
    runner = python.with_name("pythonw.exe")          # no console window when started from the menu
    runner = runner if runner.exists() else python
    here = Path(__file__).resolve().parent
    return f'"{runner}" "{here / "image_converter_gui.py"}" "%1"', str(here / "assets" / "icon.ico")


def _verb_key(ext, verb=VERB):
    return rf"{BASE}\{ext}\shell\{verb}"


def register():
    """Add the menu item for every supported image type. Returns True on success."""
    if not is_supported():
        return False
    command, icon = launch_command()
    try:
        for ext in core.INPUT_EXTENSIONS:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _verb_key(ext)) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, LABEL)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _verb_key(ext) + r"\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        return True
    except OSError:
        return False


def unregister(verb=VERB):
    """Remove the menu item again. Returns True when nothing is left behind."""
    if not is_supported():
        return False
    ok = True
    for ext in core.INPUT_EXTENSIONS:
        for key in (_verb_key(ext, verb) + r"\command", _verb_key(ext, verb)):      # children first
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except FileNotFoundError:
                pass
            except OSError:
                ok = False
    return ok


def _registered_command(verb=VERB):
    if not is_supported():
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _verb_key(_PROBE_EXT, verb) + r"\command") as key:
            return winreg.QueryValueEx(key, "")[0]
    except OSError:
        return None


def is_registered():
    return _registered_command() is not None


def refresh_if_stale():
    """If the menu item points to an old location of the app (it was moved or updated), fix it silently.

    An item left by a version from before the PixNexa rebrand is replaced by the new one.
    """
    if _registered_command(LEGACY_VERB) is not None:
        unregister(LEGACY_VERB)
        register()
        return
    current = _registered_command()
    if current is not None and current != launch_command()[0]:
        register()

"""The registry code is exercised with an in-memory stand-in for winreg, so it runs on any system."""
import sys

import pytest

import converter_core as core
import shell_integration as si


class FakeKey:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self):
        self.keys = {}                                  # path -> {value name: data}

    def CreateKey(self, root, path):                    # noqa: N802 - mirrors winreg's API
        self.keys.setdefault(path, {})
        return FakeKey(self.keys, path)

    def SetValueEx(self, key, name, _reserved, _kind, data):   # noqa: N802
        key.store[key.path][name] = data

    def OpenKey(self, root, path):                      # noqa: N802
        if path not in self.keys:
            raise FileNotFoundError(path)
        return FakeKey(self.keys, path)

    def QueryValueEx(self, key, name):                  # noqa: N802
        return key.store[key.path][name], self.REG_SZ

    def DeleteKey(self, root, path):                    # noqa: N802
        if path not in self.keys:
            raise FileNotFoundError(path)
        if any(k.startswith(path + "\\") for k in self.keys):
            raise PermissionError("key has subkeys")    # like the real winreg: children must go first
        del self.keys[path]


@pytest.fixture()
def reg(monkeypatch):
    fake = FakeWinreg()
    monkeypatch.setattr(si, "winreg", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    return fake


def test_register_creates_entries_for_every_supported_type(reg):
    assert si.register() is True
    assert set(core.INPUT_EXTENSIONS) <= set(si.extensions())
    assert {".pdf", ".mp4", ".mp3", ".docx", ".zip", ".gz", ".json", ".srt", ".woff2"} <= set(si.extensions())
    for ext in si.extensions():
        verb = reg.keys[rf"Software\Classes\SystemFileAssociations\{ext}\shell\{si.VERB}"]
        assert verb[""] == "Convert with PixNexa" and "Icon" in verb
        command = reg.keys[rf"Software\Classes\SystemFileAssociations\{ext}\shell\{si.VERB}\command"][""]
        assert command.endswith('"%1"') and "image_converter_gui.py" in command
    assert si.is_registered()


def test_frozen_exe_command(reg, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\PixNexa\PixNexa.exe")
    command, icon = si.launch_command()
    assert command == r'"C:\Apps\PixNexa\PixNexa.exe" "%1"'
    assert icon.endswith(".exe\",0")


def test_unregister_removes_everything_and_is_repeatable(reg):
    si.register()
    assert si.unregister() is True
    assert reg.keys == {} and not si.is_registered()
    assert si.unregister() is True                      # nothing left: still fine


def test_refresh_if_stale_updates_a_moved_app(reg, monkeypatch):
    si.register()
    key = rf"Software\Classes\SystemFileAssociations\.png\shell\{si.VERB}\command"
    reg.keys[key][""] = r'"D:\old\place.exe" "%1"'
    si.refresh_if_stale()
    assert reg.keys[key][""] == si.launch_command()[0]


def test_refresh_adds_types_an_older_version_did_not_know(reg):
    command, icon = si.launch_command()
    for ext in core.INPUT_EXTENSIONS:                   # what an images-only version registered
        reg.CreateKey(reg.HKEY_CURRENT_USER, rf"{si.BASE}\{ext}\shell\{si.VERB}")
        reg.CreateKey(reg.HKEY_CURRENT_USER, rf"{si.BASE}\{ext}\shell\{si.VERB}\command")
        reg.keys[rf"{si.BASE}\{ext}\shell\{si.VERB}\command"][""] = command
    si.refresh_if_stale()
    assert reg.keys[rf"{si.BASE}\.pdf\shell\{si.VERB}\command"][""] == command


def test_refresh_does_nothing_when_not_registered(reg):
    si.refresh_if_stale()
    assert reg.keys == {}


def test_unsupported_system(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert si.is_supported() is False
    assert si.register() is False and si.unregister() is False and si.is_registered() is False


def test_menu_item_from_before_the_rebrand_is_replaced(reg):
    for ext in si.extensions():
        reg.CreateKey(reg.HKEY_CURRENT_USER, rf"{si.BASE}\{ext}\shell\{si.LEGACY_VERB}")
        reg.CreateKey(reg.HKEY_CURRENT_USER, rf"{si.BASE}\{ext}\shell\{si.LEGACY_VERB}\command")
        reg.keys[rf"{si.BASE}\{ext}\shell\{si.LEGACY_VERB}\command"][""] = '"C:\\old\\ImageFormatConverter.exe" "%1"'
    si.refresh_if_stale()
    assert not any(si.LEGACY_VERB in k for k in reg.keys)
    assert si.is_registered()

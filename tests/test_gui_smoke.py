"""Opens the real window, adds images, converts them. Skipped where there is no display or no Tk."""
import time

import pytest
from PIL import Image

pytest.importorskip("customtkinter")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    import image_converter_gui as gui
    try:
        window = gui.App()
    except Exception as exc:  # no display (headless CI) or Tk missing
        pytest.skip(f"cannot open a window here: {exc}")
    yield window
    window.destroy()


def pump(app, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def test_add_convert_and_report(app, tmp_path):
    good = tmp_path / "a.png"
    Image.new("RGB", (20, 10), (1, 2, 3)).save(good)
    bad = tmp_path / "b.txt"
    bad.write_text("not an image")

    app.add_paths([str(good), str(bad), str(good)])
    assert len(app.items) == 1                       # text file skipped, duplicate ignored

    app.open_after.set(False)
    app.select_format("webp")
    app.on_convert()
    deadline = time.time() + 20
    while app.busy and time.time() < deadline:
        app.update()
        time.sleep(0.01)
    pump(app)
    assert (tmp_path / "a.webp").exists()
    assert "Done" in app.status.cget("text")


def test_missing_custom_folder_is_reported(app, tmp_path):
    img = tmp_path / "a.png"
    Image.new("RGB", (4, 4)).save(img)
    app.add_paths([str(img)])
    app.out_mode.set("Custom folder")
    app.out_dir.set("")
    app.on_convert()
    assert not app.busy and "folder" in app.status.cget("text").lower()


def test_settings_roundtrip(app):
    app.select_format("ico")
    app.overwrite.set(True)
    import image_converter_gui as gui
    saved = gui.load_settings()
    assert saved["format"] == "ico" and saved["overwrite"] is True

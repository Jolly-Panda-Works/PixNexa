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


def test_paths_from_the_command_line_and_the_inbox(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    import image_converter_gui as gui
    from single_instance import SingleInstance

    one, two = tmp_path / "one.png", tmp_path / "two.png"
    for p in (one, two):
        Image.new("RGB", (8, 8)).save(p)
    inst = SingleInstance(gui.settings_dir())
    assert inst.acquire()
    try:
        window = gui.App([str(one)], inst)
    except Exception as exc:
        pytest.skip(f"cannot open a window here: {exc}")
    try:
        pump(window, 0.6)
        assert [it["path"].name for it in window.items] == ["one.png"]

        SingleInstance(gui.settings_dir()).send([str(two)])    # a second launch, e.g. another right-click
        pump(window, 1.0)
        assert [it["path"].name for it in window.items] == ["one.png", "two.png"]
    finally:
        window.on_close()


def test_new_files_start_a_fresh_list_after_a_finished_batch(app, tmp_path):
    old, new = tmp_path / "old.png", tmp_path / "new.png"
    for p in (old, new):
        Image.new("RGB", (8, 8)).save(p)
    app.add_paths([str(old)])
    app.open_after.set(False)
    app.on_convert()
    deadline = time.time() + 20
    while app.busy and time.time() < deadline:
        app.update()
        time.sleep(0.01)
    pump(app)
    app.add_external([str(new)])
    assert [it["path"].name for it in app.items] == ["new.png"]

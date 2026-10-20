"""The format matrix and the entry points the GUI uses."""
import pytest

import converter_core as core
from pixnexa_engines import ConversionError, Options, registry


def test_every_category_has_targets_and_a_valid_default():
    for cat in registry.CATEGORIES.values():
        assert cat.targets, cat.key
        assert cat.target(cat.default) is not None, cat.key
        assert len({t.key for t in cat.targets}) == len(cat.targets)


def test_compressible_categories():
    assert {c.key for c in registry.CATEGORIES.values() if c.can_compress} == {"image", "pdf", "video", "audio"}


@pytest.mark.parametrize("name, key", [
    ("a.JPG", "image"), ("b.heic", "image"), ("c.avif", "image"), ("d.pdf", "pdf"), ("e.mkv", "video"),
    ("f.flac", "audio"), ("g.docx", "document"), ("h.md", "document"), ("i.xlsx", "spreadsheet"),
    ("j.pptx", "presentation"), ("k.yaml", "data"), ("l.csv", "data"), ("m.tar.gz", "archive"), ("n.7z", "archive"),
    ("o.woff2", "font"), ("p.vtt", "subtitle"),
])
def test_category_of(name, key):
    assert registry.category_of(name).key == key


def test_image_extensions_are_all_known():
    for ext in core.INPUT_EXTENSIONS:
        assert registry.category_of(f"x{ext}").key == "image"


def test_shell_extensions_are_single_suffixes():
    exts = registry.shell_extensions()
    assert ".png" in exts and ".pdf" in exts and ".gz" in exts and ".mp4" in exts
    assert all(e.count(".") == 1 for e in exts) and len(exts) == len(set(exts))


def test_list_supported(tmp_path):
    for name in ("b.PNG", "a.pdf", "c.unknown", "d.mp3"):
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in registry.list_supported(tmp_path)] == ["a.pdf", "b.PNG", "d.mp3"]


def test_wrong_target_for_category(tmp_path):
    src = tmp_path / "x.png"
    src.write_bytes(b"x")
    with pytest.raises(ConversionError):
        registry.convert_file(src, "mp3", Options())


def test_cannot_compress_other_kinds(tmp_path):
    src = tmp_path / "x.json"
    src.write_text("{}")
    with pytest.raises(ConversionError, match="cannot be compressed"):
        registry.compress_file(src, Options())


def test_missing_file():
    with pytest.raises(ConversionError, match="not found"):
        registry.convert_file("/no/such/file.png", "jpg", Options())

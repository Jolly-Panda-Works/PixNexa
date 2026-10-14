import struct

import pytest
from PIL import Image

import converter_core as core
from converter_core import ConversionError, convert_image


def make_image(path, size=(64, 48), mode="RGB", color=(200, 40, 40)):
    img = Image.new(mode, size, color)
    img.save(path)
    return path


def make_transparent_png(path, size=(40, 40)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))                    # fully transparent ...
    for x in range(10, 30):
        for y in range(10, 30):
            img.putpixel((x, y), (0, 0, 255, 255))                 # ... with an opaque blue square
    img.save(path)
    return path


# ───────────── every target format ─────────────

@pytest.mark.parametrize("fmt", core.FORMAT_KEYS)
def test_png_to_every_format(tmp_path, fmt):
    src = make_image(tmp_path / "in.png")
    dst = convert_image(src, fmt)
    assert dst.exists() and dst.parent == tmp_path
    assert dst.suffix == f".{core.FORMATS[fmt].extension}"
    with Image.open(dst) as out:
        out.load()
        if fmt != "ico":
            assert out.size == (64, 48)


@pytest.mark.parametrize("src_fmt", ["jpg", "bmp", "gif", "tiff", "webp"])
def test_other_sources_to_png(tmp_path, src_fmt):
    src = tmp_path / f"in.{src_fmt}"
    Image.new("RGB", (30, 20), (10, 120, 200)).save(src)
    dst = convert_image(src, "png")
    with Image.open(dst) as out:
        assert out.format == "PNG" and out.size == (30, 20)


def test_format_aliases(tmp_path):
    src = make_image(tmp_path / "in.png")
    assert convert_image(src, "jpeg").suffix == ".jpg"
    assert convert_image(src, "tif").suffix == ".tiff"
    assert convert_image(src, ".PNG").name == "in (1).png"      # PNG -> PNG never overwrites the source


def test_unknown_target_format(tmp_path):
    src = make_image(tmp_path / "in.png")
    with pytest.raises(ConversionError):
        convert_image(src, "svg")


# ───────────── ICO ─────────────

def test_ico_has_all_standard_sizes(tmp_path):
    src = make_image(tmp_path / "logo.png", size=(300, 100))        # non-square on purpose
    dst = convert_image(src, "ico")
    data = dst.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 4)
    sizes = []
    for i in range(count):
        width, height = struct.unpack("<BB", data[6 + 16 * i:8 + 16 * i])
        sizes.append((width or 256, height or 256))
    assert sizes == [(16, 16), (32, 32), (48, 48), (256, 256)]
    with Image.open(dst) as ico:
        assert set(ico.info["sizes"]) == {(16, 16), (32, 32), (48, 48), (256, 256)}


def test_ico_from_tiny_source_still_has_256(tmp_path):
    src = make_image(tmp_path / "tiny.png", size=(8, 8))
    with Image.open(convert_image(src, "ico")) as ico:
        assert (256, 256) in ico.info["sizes"]


def test_ico_keeps_aspect_ratio_and_transparency(tmp_path):
    src = make_image(tmp_path / "wide.png", size=(200, 100), color=(255, 0, 0))
    dst = convert_image(src, "ico")
    with Image.open(dst) as ico:
        ico.size = (256, 256)
        frame = ico.convert("RGBA")
    assert frame.getpixel((128, 128))[3] == 255                     # picture in the middle
    assert frame.getpixel((128, 5))[3] == 0                         # transparent bars above and below


# ───────────── transparency, quality, colour modes ─────────────

def test_jpg_flattens_transparency_to_white(tmp_path):
    src = make_transparent_png(tmp_path / "t.png")
    with Image.open(convert_image(src, "jpg")) as out:
        assert out.mode == "RGB"
        r, g, b = out.getpixel((2, 2))
        assert min(r, g, b) > 240                                   # white, not black
        assert out.getpixel((20, 20))[2] > 200                      # the blue square survives


def test_png_and_webp_keep_transparency(tmp_path):
    src = make_transparent_png(tmp_path / "t.png")
    for fmt in ("png", "webp", "tiff", "gif"):
        with Image.open(convert_image(src, fmt)) as out:
            assert out.convert("RGBA").getpixel((2, 2))[3] == 0, fmt


def test_lower_quality_makes_smaller_jpg(tmp_path):
    src = tmp_path / "noise.png"
    Image.effect_noise((256, 256), 80).convert("RGB").save(src)
    high = convert_image(src, "jpg", quality=95, out_dir=tmp_path / "hi")
    low = convert_image(src, "jpg", quality=20, out_dir=tmp_path / "lo")
    assert low.stat().st_size < high.stat().st_size


@pytest.mark.parametrize("mode", ["L", "LA", "P", "1", "CMYK", "I;16"])
def test_unusual_modes(tmp_path, mode):
    src = tmp_path / "in.tiff"
    Image.new(mode, (16, 16)).save(src)
    for fmt in ("png", "jpg", "bmp", "webp", "gif"):
        with Image.open(convert_image(src, fmt, out_dir=tmp_path / fmt)) as out:
            out.load()


def test_exif_orientation_is_applied(tmp_path):
    src = tmp_path / "rotated.jpg"
    img = Image.new("RGB", (60, 20), (255, 0, 0))
    exif = Image.Exif()
    exif[0x0112] = 6                                                # "rotate 90 degrees clockwise to view"
    img.save(src, exif=exif)
    with Image.open(convert_image(src, "png")) as out:
        assert out.size == (20, 60)


# ───────────── animation ─────────────

def _animated_gif(path):
    frames = [Image.new("RGB", (20, 20), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[50, 80, 120], loop=0)


def test_animated_gif_to_webp_and_back(tmp_path):
    src = tmp_path / "anim.gif"
    _animated_gif(src)
    webp = convert_image(src, "webp")
    with Image.open(webp) as w:
        assert w.n_frames == 3
    back = convert_image(webp, "gif")
    with Image.open(back) as g:
        assert g.n_frames == 3


def test_animated_gif_to_png_uses_first_frame(tmp_path):
    src = tmp_path / "anim.gif"
    _animated_gif(src)
    with Image.open(convert_image(src, "png")) as out:
        assert getattr(out, "n_frames", 1) == 1
        assert out.convert("RGB").getpixel((5, 5))[0] > 200         # first frame is red


# ───────────── output location and file names ─────────────

def test_default_output_is_next_to_original(tmp_path):
    src = make_image(tmp_path / "photo.jpg")
    assert convert_image(src, "png") == tmp_path / "photo.png"


def test_custom_output_folder_is_created(tmp_path):
    src = make_image(tmp_path / "photo.png")
    dst = convert_image(src, "jpg", out_dir=tmp_path / "new" / "folder")
    assert dst == tmp_path / "new" / "folder" / "photo.jpg"


def test_existing_file_is_not_overwritten_by_default(tmp_path):
    src = make_image(tmp_path / "photo.png")
    (tmp_path / "photo.jpg").write_bytes(b"keep me")
    dst = convert_image(src, "jpg")
    assert dst.name == "photo (1).jpg"
    assert (tmp_path / "photo.jpg").read_bytes() == b"keep me"
    assert convert_image(src, "jpg").name == "photo (2).jpg"


def test_overwrite_replaces_existing_file(tmp_path):
    src = make_image(tmp_path / "photo.png")
    (tmp_path / "photo.jpg").write_bytes(b"old")
    dst = convert_image(src, "jpg", overwrite=True)
    assert dst.name == "photo.jpg" and dst.read_bytes() != b"old"


def test_overwrite_never_destroys_the_source(tmp_path):
    src = make_image(tmp_path / "photo.png")
    dst = convert_image(src, "png", overwrite=True)
    assert dst.name == "photo (1).png" and src.exists()


def test_non_ascii_file_names(tmp_path):
    src = make_image(tmp_path / "عکس تعطیلات 🌅.png")
    dst = convert_image(src, "jpg")
    assert dst.name == "عکس تعطیلات 🌅.jpg" and dst.exists()


# ───────────── errors ─────────────

def test_missing_file(tmp_path):
    with pytest.raises(ConversionError, match="not found"):
        convert_image(tmp_path / "nope.png", "jpg")


def test_not_an_image_leaves_no_partial_files(tmp_path):
    bad = tmp_path / "fake.png"
    bad.write_text("this is not an image")
    with pytest.raises(ConversionError):
        convert_image(bad, "jpg")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fake.png"]


def test_truncated_image_leaves_no_partial_files(tmp_path):
    src = tmp_path / "cut.png"
    Image.effect_noise((200, 200), 90).convert("RGB").save(src)
    src.write_bytes(src.read_bytes()[:300])
    with pytest.raises(ConversionError):
        convert_image(src, "jpg")
    assert not list(tmp_path.glob("*.jpg")) and not list(tmp_path.glob("*.part"))


# ───────────── helpers ─────────────

def test_describe_image(tmp_path):
    src = make_image(tmp_path / "a.png", size=(33, 22))
    info = core.describe_image(src)
    assert (info.format, info.width, info.height) == ("PNG", 33, 22) and info.size_bytes > 0
    (tmp_path / "b.png").write_text("nope")
    with pytest.raises(ConversionError):
        core.describe_image(tmp_path / "b.png")


def test_list_images_filters_and_sorts(tmp_path):
    for name in ("b.PNG", "a.jpg", "c.txt", "d.svg"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "e.png").write_bytes(b"x")
    assert [p.name for p in core.list_images(tmp_path)] == ["a.jpg", "b.PNG"]
    assert core.list_images(tmp_path / "missing") == []


def test_is_supported_input():
    assert core.is_supported_input("x.JPG") and core.is_supported_input("x.webp")
    assert not core.is_supported_input("x.svg") and not core.is_supported_input("x.txt")

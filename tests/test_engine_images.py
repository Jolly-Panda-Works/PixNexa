"""New image features: AVIF, HEIC, TGA, PDF output, resize, grayscale, metadata, target size, compression."""
import io

import pytest
from conftest import needs_ffmpeg, needs_x265
from PIL import Image

import converter_core as core
from pixnexa_engines import Options, registry


def photo(path, size=(400, 300)):
    Image.effect_noise(size, 60).convert("RGB").save(path, quality=95)
    return path


def test_avif_is_supported_by_pillow():
    from PIL import features
    assert features.check("avif"), "Pillow >= 11.3 with AVIF is required"


def test_avif_roundtrip_keeps_transparency(tmp_path):
    src = tmp_path / "t.png"
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    img.paste((0, 0, 255, 255), (10, 10, 30, 30))
    img.save(src)
    out = core.convert_image(src, "avif")
    with Image.open(out) as a:
        assert a.format == "AVIF" and a.convert("RGBA").getpixel((2, 2))[3] == 0
    back = core.convert_image(out, "png")
    assert back.exists()


@needs_ffmpeg
@needs_x265
@pytest.mark.parametrize("size", [(64, 48), (63, 47), (1, 1)])
def test_heic_output_reads_back(tmp_path, size):
    src = tmp_path / "in.png"
    Image.new("RGB", size, (30, 160, 60)).save(src)
    out = core.convert_image(src, "heic", quality=80)
    assert out.suffix == ".heic" and out.read_bytes()[4:12] == b"ftypheic"
    with Image.open(out) as h:                       # read by pi-heif (libheif)
        assert h.size == size
        r, g, b = h.convert("RGB").getpixel((size[0] - 1, size[1] - 1))
        assert abs(r - 30) < 12 and abs(g - 160) < 12 and abs(b - 60) < 12


@needs_ffmpeg
@needs_x265
def test_heic_input_converts_to_jpg(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGB", (32, 20), (200, 10, 10)).save(src)
    heic = core.convert_image(src, "heic")
    info = core.describe_image(heic)
    assert info.format == "HEIF" and (info.width, info.height) == (32, 20)
    jpg = core.convert_image(heic, "jpg")
    with Image.open(jpg) as j:
        assert j.size == (32, 20)


def test_tga_and_pdf_outputs(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGBA", (30, 20), (10, 20, 30, 128)).save(src)
    with Image.open(core.convert_image(src, "tga")) as t:
        assert t.format == "TGA" and t.size == (30, 20)
    pdf = core.convert_image(src, "pdf")
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    assert len(doc) == 1
    doc.close()


def test_resize_max_box_never_enlarges(tmp_path):
    src = photo(tmp_path / "p.jpg", (400, 300))
    out = core.convert_image(src, "png", resize=("max", 200, 200))
    with Image.open(out) as o:
        assert o.size == (200, 150)
    out = core.convert_image(src, "png", resize=("max", 1000, 0))
    with Image.open(out) as o:
        assert o.size == (400, 300)


def test_resize_percent_and_grayscale(tmp_path):
    src = photo(tmp_path / "p.jpg", (400, 300))
    out = core.convert_image(src, "png", resize=("percent", 25), grayscale=True)
    with Image.open(out) as o:
        assert o.size == (100, 75) and o.mode in ("L", "LA")


def test_metadata_is_stripped_or_kept(tmp_path):
    src = tmp_path / "m.jpg"
    exif = Image.Exif()
    exif[0x010F] = "CameraMaker"
    Image.new("RGB", (20, 20)).save(src, exif=exif)
    stripped = core.convert_image(src, "jpg", out_dir=tmp_path / "a")
    kept = core.convert_image(src, "jpg", out_dir=tmp_path / "b", strip_metadata=False)
    with Image.open(stripped) as s, Image.open(kept) as k:
        assert 0x010F not in s.getexif()
        assert k.getexif().get(0x010F) == "CameraMaker"


@pytest.mark.parametrize("fmt", ["jpg", "webp", "avif"])
def test_target_size_is_reached(tmp_path, fmt):
    src = photo(tmp_path / "big.png", (900, 700))
    out = core.convert_image(src, fmt, target_kb=40)
    assert out.stat().st_size <= 40 * 1024


def test_target_size_shrinks_the_picture_when_quality_is_not_enough(tmp_path):
    src = photo(tmp_path / "big.png", (900, 700))
    out = core.convert_image(src, "jpg", target_kb=8)
    assert out.stat().st_size <= 8 * 1024
    with Image.open(out) as o:
        assert o.width < 900


def test_png_palette_is_smaller(tmp_path):
    src = tmp_path / "g.png"
    from PIL import ImageFilter
    channels = [Image.effect_noise((300, 300), 50 + 10 * i) for i in range(3)]
    Image.merge("RGB", channels).filter(ImageFilter.GaussianBlur(2)).save(src)   # many colours, like a photo
    full = core.convert_image(src, "png", out_dir=tmp_path / "a")
    pal = core.convert_image(src, "png", out_dir=tmp_path / "b", png_palette=True)
    assert pal.stat().st_size < full.stat().st_size


def test_compress_image_keeps_format_and_is_smaller(tmp_path):
    src = photo(tmp_path / "photo.jpg", (800, 600))
    res = registry.compress_file(src, Options(quality=50))
    out = res.outputs[0]
    assert out.name == "photo-compressed.jpg"
    assert out.stat().st_size < src.stat().st_size


def test_compress_image_never_bigger(tmp_path):
    src = tmp_path / "tiny.jpg"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(src, quality=10)
    res = registry.compress_file(src, Options(quality=100))
    assert res.outputs[0].stat().st_size <= src.stat().st_size


def test_compress_bmp_becomes_png(tmp_path):
    src = tmp_path / "s.bmp"
    Image.new("RGB", (100, 100), (5, 5, 5)).save(src)
    out = registry.compress_file(src, Options()).outputs[0]
    assert out.suffix == ".png" and out.stat().st_size < src.stat().st_size


def test_animated_resize_keeps_frames(tmp_path):
    src = tmp_path / "a.gif"
    frames = [Image.new("RGB", (40, 40), c) for c in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=[50, 90], loop=0)
    out = core.convert_image(src, "webp", resize=("percent", 50))
    with Image.open(out) as w:
        assert w.n_frames == 2 and w.size == (20, 20)


def test_image_registry_convert(tmp_path):
    src = tmp_path / "x.png"
    Image.new("RGB", (10, 10)).save(src)
    res = registry.convert_file(src, "webp", Options(resize_mode="percent", percent=50))
    with Image.open(res.outputs[0]) as o:
        assert o.size == (5, 5)


def test_images_to_one_pdf_embeds_jpeg_unchanged(tmp_path):
    a = photo(tmp_path / "a.jpg", (200, 100))
    b = tmp_path / "b.png"
    Image.new("RGBA", (50, 80), (0, 255, 0, 128)).save(b)
    out = registry.images_to_pdf([a, b], Options(page_size="a4"))
    assert out.name == "a.pdf"
    import pikepdf
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 2
        first = next(iter(pdf.pages[0].get_images().values()))
        assert first.read_raw_bytes() == a.read_bytes()            # the JPEG was not re-encoded
        assert float(pdf.pages[0].mediabox[2]) > float(pdf.pages[0].mediabox[3])   # landscape page
        second = next(iter(pdf.pages[1].get_images().values()))
        assert "/SMask" in second                                 # transparency kept


def test_unknown_extension_image_is_sniffed(tmp_path):
    src = tmp_path / "picture.data"
    Image.new("RGB", (4, 4)).save(src, format="PNG")
    assert registry.category_of(src).key == "image"
    assert registry.category_of(tmp_path / "nothing.data") is None


def test_heic_without_ffmpeg_gives_a_clear_message(tmp_path, monkeypatch):
    import pixnexa_engines.heif as heif
    monkeypatch.setattr(heif, "find_ffmpeg", lambda: None)
    src = tmp_path / "x.png"
    Image.new("RGB", (4, 4)).save(src)
    with pytest.raises(core.ConversionError, match="FFmpeg"):
        core.convert_image(src, "heic")
    assert not list(tmp_path.glob("*.heic*"))


def test_heif_box_writer_structure():
    from pixnexa_engines import heif
    # a fake stream: VPS, SPS (with a 12-byte profile_tier_level), PPS, one slice
    vps, sps, pps = b"\x40\x01\x0c", b"\x42\x01\x01" + bytes(range(1, 13)) + b"\xa0", b"\x44\x01\xc1"
    sl = b"\x26\x01\xaf\x00\x00\x03\x01"
    stream = b"".join(b"\x00\x00\x00\x01" + u for u in (vps, sps, pps, sl))
    data = heif.build_heif(stream, 64, 48, 63, 47)
    assert data[4:8] == b"ftyp" and b"hvcC" in data and b"clap" in data and b"ispe" in data
    assert data.endswith(len(sl).to_bytes(4, "big") + sl)
    assert heif._rbsp(b"\x00\x00\x03\x01") == b"\x00\x00\x01"
    buf = io.BytesIO(data)
    assert buf.read(4) == (24).to_bytes(4, "big")

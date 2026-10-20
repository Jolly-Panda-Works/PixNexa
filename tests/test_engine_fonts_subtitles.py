"""Fonts (fontTools) and subtitles (pysubs2)."""
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from pixnexa_engines import ConversionError, Options, registry


def make_ttf(path):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({65: "A"})
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((500, 700))
    pen.lineTo((900, 0))
    pen.closePath()
    glyph = pen.glyph()
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": glyph})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "A": (1000, 100)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "PixTest", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))
    return path


@pytest.mark.parametrize("target", ["woff", "woff2"])
def test_ttf_to_web_fonts_and_back(tmp_path, target):
    src = make_ttf(tmp_path / "pix.ttf")
    web = registry.convert_file(src, target, Options()).outputs[0]
    assert web.suffix == f".{target}"
    assert TTFont(str(web)).flavor == target
    back = registry.convert_file(web, "ttf", Options(out_dir=tmp_path / "back")).outputs[0]
    assert back.name == "pix.ttf"
    font = TTFont(str(back))
    assert font.flavor is None and font.getBestCmap()[65] == "A"


def test_bad_font(tmp_path):
    bad = tmp_path / "bad.ttf"
    bad.write_bytes(b"nope")
    with pytest.raises(ConversionError):
        registry.convert_file(bad, "woff2", Options())


SRT = "1\n00:00:01,000 --> 00:00:02,500\nHello <i>world</i>\n\n2\n00:00:03,000 --> 00:00:04,000\nÜmlaut line\n"


@pytest.mark.parametrize("target", ["ass", "ssa", "vtt", "sub", "ttml", "srt"])
def test_srt_to_every_subtitle_format_and_back(tmp_path, target):
    src = tmp_path / "movie.srt"
    src.write_text(SRT, encoding="utf-8")
    out = registry.convert_file(src, target, Options()).outputs[0]
    assert out.suffix == f".{target}"
    back = registry.convert_file(out, "srt", Options(out_dir=tmp_path / "back")).outputs[0]
    text = back.read_text(encoding="utf-8")
    assert "Hello" in text and "Ümlaut line" in text
    import pysubs2
    subs = pysubs2.load(str(back))
    assert len(subs) == 2 and abs(subs[0].start - 1000) <= 50


def test_cp1252_subtitles_are_read(tmp_path):
    src = tmp_path / "old.srt"
    src.write_bytes("1\n00:00:01,000 --> 00:00:02,000\nCafé\n".encode("cp1252"))
    out = registry.convert_file(src, "vtt", Options()).outputs[0]
    assert "Café" in out.read_text(encoding="utf-8")


def test_empty_subtitles(tmp_path):
    src = tmp_path / "empty.srt"
    src.write_text("", encoding="utf-8")
    with pytest.raises(ConversionError):
        registry.convert_file(src, "vtt", Options())

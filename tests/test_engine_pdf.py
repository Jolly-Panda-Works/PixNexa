"""PDF: render pages, text, merge, split, page ranges, compression."""
import pikepdf
import pytest
from conftest import make_text_pdf
from PIL import Image

from pixnexa_engines import ConversionError, Options, registry
from pixnexa_engines.pdf import parse_pages


def test_parse_pages():
    assert parse_pages("", 4) == [0, 1, 2, 3]
    assert parse_pages("1-2, 4", 4) == [0, 1, 3]
    assert parse_pages("3-", 5) == [2, 3, 4]
    assert parse_pages("2,2,1", 3) == [1, 0]
    assert parse_pages("2-10", 3) == [1, 2]
    for bad in ("x", "0", "3-1"):
        with pytest.raises(ConversionError):
            parse_pages(bad, 3)
    with pytest.raises(ConversionError):
        parse_pages("5", 3)


def test_pdf_to_png_pages_in_a_folder(tmp_path):
    src = make_text_pdf(tmp_path / "doc.pdf", ["One", "Two", "Three"])
    res = registry.convert_file(src, "png", Options(dpi=72))
    folder = res.outputs[0]
    assert folder.is_dir() and folder.name == "doc"
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["doc-001.png", "doc-002.png", "doc-003.png"]
    with Image.open(folder / "doc-001.png") as im:
        assert im.size == (612, 792)


def test_pdf_single_page_to_jpg_at_dpi(tmp_path):
    src = make_text_pdf(tmp_path / "one.pdf")
    out = registry.convert_file(src, "jpg", Options(dpi=144)).outputs[0]
    assert out.name == "one.jpg"
    with Image.open(out) as im:
        assert im.size == (1224, 1584)


def test_pdf_page_range_to_png(tmp_path):
    src = make_text_pdf(tmp_path / "doc.pdf", ["A", "B", "C"])
    out = registry.convert_file(src, "png", Options(dpi=36, pages="2")).outputs[0]
    assert out.name == "doc-2.png" and out.is_file()


def test_pdf_to_text(tmp_path):
    src = make_text_pdf(tmp_path / "t.pdf", ["Hello PixNexa", "Second page"])
    out = registry.convert_file(src, "txt", Options()).outputs[0]
    text = out.read_text(encoding="utf-8")
    assert "Hello PixNexa" in text and "Second page" in text


def test_pdf_without_text_reports_it(tmp_path):
    img = tmp_path / "scan.png"
    Image.new("RGB", (50, 50), "white").save(img)
    pdf = registry.images_to_pdf([img])
    with pytest.raises(ConversionError, match="no text"):
        registry.convert_file(pdf, "txt", Options())


def test_merge_and_split(tmp_path):
    a = make_text_pdf(tmp_path / "a.pdf", ["A1", "A2"])
    b = make_text_pdf(tmp_path / "b.pdf", ["B1"])
    merged = registry.merge_pdfs([a, b])
    assert merged.name == "a (merged).pdf"
    with pikepdf.open(merged) as pdf:
        assert len(pdf.pages) == 3
    folder = registry.convert_file(merged, "split", Options()).outputs[0]
    files = sorted(folder.iterdir())
    assert len(files) == 3 and all(f.suffix == ".pdf" for f in files)
    with pikepdf.open(files[2]) as last:
        assert len(last.pages) == 1


def test_extract_page_range(tmp_path):
    src = make_text_pdf(tmp_path / "d.pdf", ["1", "2", "3", "4"])
    out = registry.convert_file(src, "extract", Options(pages="4, 1-2")).outputs[0]
    assert out.name == "d (pages 4,1-2).pdf"
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 3
    with pytest.raises(ConversionError):
        registry.convert_file(src, "extract", Options(pages=""))


def test_merge_needs_two(tmp_path):
    with pytest.raises(ConversionError):
        registry.merge_pdfs([make_text_pdf(tmp_path / "x.pdf")])


def _photo_pdf(tmp_path, size=(2400, 1800)):
    img = tmp_path / "photo.png"
    Image.effect_noise(size, 40).convert("RGB").resize(size).save(img)
    return registry.images_to_pdf([img], Options(page_size="a4", quality=95))


def test_compress_pdf_downscales_and_recompresses(tmp_path):
    src = _photo_pdf(tmp_path)
    res = registry.compress_file(src, Options(quality=50, dpi=72))
    out = res.outputs[0]
    assert out.name == "photo-compressed.pdf"
    assert out.stat().st_size < src.stat().st_size * 0.5
    with pikepdf.open(out) as pdf:
        image = next(iter(pdf.pages[0].get_images().values()))
        assert int(image.Width) < 1000                     # A4 width (~8 inches) at 72 dpi is ~560 px
        assert image.Filter == "/DCTDecode"
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(out))
    assert len(doc) == 1
    doc.close()


def test_compress_pdf_never_bigger(tmp_path):
    src = make_text_pdf(tmp_path / "text.pdf", ["Only text"])
    res = registry.compress_file(src, Options())
    assert res.outputs[0].stat().st_size <= src.stat().st_size


def test_compress_pdf_strips_metadata(tmp_path):
    src = make_text_pdf(tmp_path / "meta.pdf")
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Author"] = "Someone"
        pdf.save(src)
    out = registry.compress_file(src, Options(strip_metadata=True)).outputs[0]
    with pikepdf.open(out) as pdf:
        assert "/Author" not in pdf.docinfo


def test_password_protected_pdf(tmp_path):
    src = make_text_pdf(tmp_path / "plain.pdf")
    locked = tmp_path / "locked.pdf"
    with pikepdf.open(src) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(user="secret", owner="secret"))
    for target in ("png", "txt", "split"):
        with pytest.raises(ConversionError, match="password"):
            registry.convert_file(locked, target, Options())
    with pytest.raises(ConversionError, match="password"):
        registry.compress_file(locked, Options())


def test_broken_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 nonsense")
    with pytest.raises(ConversionError):
        registry.convert_file(bad, "png", Options())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.pdf"]

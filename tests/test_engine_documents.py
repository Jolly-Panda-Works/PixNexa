"""Documents: pure-Python paths always, LibreOffice paths when it is installed."""
import zipfile

import pytest
from conftest import needs_libreoffice

from pixnexa_engines import ConversionError, Options, office, registry


def make_docx(path, paragraphs=("Hello from DOCX", "Second\tline")):
    body = "".join(
        "<w:p><w:r>" + "".join(
            (f"<w:t>{part}</w:t>" if i == 0 else f"<w:tab/><w:t>{part}</w:t>") for i, part in enumerate(p.split("\t"))
        ) + "</w:r></w:p>" for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/'
                   '2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
                   'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override '
                   'PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
                   'wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", doc)
    return path


def make_xlsx(path, sheets=None):
    import openpyxl
    wb = openpyxl.Workbook()
    sheets = sheets or {"People": [["name", "age"], ["Ana", 31], ["Bo", 25]]}
    first = True
    for title, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = title
        first = False
        for r in rows:
            ws.append(r)
    wb.save(path)
    return path


def test_markdown_to_html(tmp_path):
    src = tmp_path / "notes.md"
    src.write_text("# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n*Ünïcode*\n", encoding="utf-8")
    out = registry.convert_file(src, "html", Options()).outputs[0]
    html = out.read_text(encoding="utf-8")
    assert '<h1 id="title">Title</h1>' in html and "<table>" in html and "Ünïcode" in html
    assert 'charset="utf-8"' in html


def test_html_to_text(tmp_path):
    src = tmp_path / "page.html"
    src.write_text("<html><head><style>p{}</style><script>x()</script></head><body><h1>Head</h1>"
                   "<p>One &amp; two</p><ul><li>Item</li></ul></body></html>", encoding="utf-8")
    text = registry.convert_file(src, "txt", Options()).outputs[0].read_text(encoding="utf-8")
    assert "Head" in text and "One & two" in text and "Item" in text
    assert "x()" not in text and "p{}" not in text


def test_docx_to_text_without_libreoffice(tmp_path, monkeypatch):
    monkeypatch.setattr(office, "find_soffice", lambda: None)
    src = make_docx(tmp_path / "letter.docx")
    text = registry.convert_file(src, "txt", Options()).outputs[0].read_text(encoding="utf-8")
    assert text == "Hello from DOCX\nSecond\tline\n"


def test_xlsx_to_csv_and_json_without_libreoffice(tmp_path, monkeypatch):
    monkeypatch.setattr(office, "find_soffice", lambda: None)
    src = make_xlsx(tmp_path / "book.xlsx")
    csv_out = registry.convert_file(src, "csv", Options()).outputs[0]
    assert csv_out.name == "book.csv"
    assert csv_out.read_text(encoding="utf-8-sig").splitlines() == ["name,age", "Ana,31", "Bo,25"]
    import json
    data = json.loads(registry.convert_file(src, "json", Options()).outputs[0].read_text(encoding="utf-8"))
    assert data == [{"name": "Ana", "age": 31}, {"name": "Bo", "age": 25}]


def test_xlsx_with_several_sheets_gives_one_csv_each(tmp_path):
    src = make_xlsx(tmp_path / "two.xlsx", {"A": [["x"], [1]], "B C": [["y"], [2]]})
    outs = registry.convert_file(src, "csv", Options()).outputs
    assert sorted(p.name for p in outs) == ["two - A.csv", "two - B C.csv"]


def test_missing_libreoffice_message(tmp_path, monkeypatch):
    monkeypatch.setattr(office, "find_soffice", lambda: None)
    src = make_docx(tmp_path / "x.docx")
    with pytest.raises(ConversionError, match="LibreOffice"):
        registry.convert_file(src, "pdf", Options())
    assert "libreoffice.org" in office.MISSING


def test_find_soffice_env(tmp_path, monkeypatch):
    exe = tmp_path / "soffice.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("PIXNEXA_SOFFICE", str(exe))
    assert office.find_soffice() == str(exe)


@needs_libreoffice
def test_docx_to_pdf_and_odt(tmp_path):
    src = make_docx(tmp_path / "doc.docx")
    pdf = registry.convert_file(src, "pdf", Options()).outputs[0]
    assert pdf.name == "doc.pdf" and pdf.read_bytes().startswith(b"%PDF")
    odt = registry.convert_file(src, "odt", Options()).outputs[0]
    assert zipfile.is_zipfile(odt)
    txt = registry.convert_file(src, "txt", Options()).outputs[0]
    assert "Hello from DOCX" in txt.read_text(encoding="utf-8-sig")


@needs_libreoffice
def test_markdown_and_html_to_docx(tmp_path):
    md = tmp_path / "m.md"
    md.write_text("# Hi\n\nText\n", encoding="utf-8")
    out = registry.convert_file(md, "docx", Options()).outputs[0]
    assert out.name == "m.docx" and zipfile.is_zipfile(out)
    html = tmp_path / "p.html"
    html.write_text("<p>Hello</p>", encoding="utf-8")
    assert registry.convert_file(html, "pdf", Options()).outputs[0].read_bytes().startswith(b"%PDF")


@needs_libreoffice
def test_spreadsheet_and_presentation(tmp_path):
    src = make_xlsx(tmp_path / "s.xlsx")
    ods = registry.convert_file(src, "ods", Options()).outputs[0]
    assert ods.suffix == ".ods"
    back = registry.convert_file(ods, "csv", Options()).outputs[0]
    assert back.read_text(encoding="utf-8-sig").splitlines()[0] == "name,age"
    pdf = registry.convert_file(ods, "pdf", Options()).outputs[0]
    assert pdf.read_bytes().startswith(b"%PDF")

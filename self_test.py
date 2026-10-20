"""`PixNexa.exe --self-test`: run one tiny conversion per engine, without opening a window.

Used by the build to prove that PyInstaller bundled every library and that the bundled FFmpeg is found.
The report goes to %TEMP%\\PixNexa-self-test.txt (a windowed exe has no console); the exit code is the number
of failed checks.
"""
from __future__ import annotations

import json
import tempfile
import traceback
from pathlib import Path


def _font(path: Path):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({65: "A"})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((500, 700))
    pen.lineTo((1000, 0))
    pen.closePath()
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": pen.glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "A": (1000, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "SelfTest", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))


def run(report_path: Path | None = None) -> int:
    from PIL import Image

    from pixnexa_engines import Options, registry
    from pixnexa_engines.media import find_ffmpeg, run_process

    lines, failed = [], 0
    with tempfile.TemporaryDirectory(prefix="pixnexa-selftest-") as tmp:
        d = Path(tmp)
        png = d / "pic.png"
        Image.new("RGBA", (40, 30), (249, 115, 22, 200)).save(png)
        (d / "data.json").write_text(json.dumps([{"a": 1, "b": "x"}]), encoding="utf-8")
        (d / "subs.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
        (d / "notes.md").write_text("# Hi\n", encoding="utf-8")
        _font(d / "font.ttf")
        ffmpeg = find_ffmpeg()
        lines.append(f"ffmpeg: {ffmpeg}")
        lines.append(f"libreoffice: {registry.tools().get('libreoffice')}")

        def check(name, fn):
            nonlocal failed
            try:
                result = fn()
                lines.append(f"ok    {name}: {result}")
            except Exception:
                failed += 1
                lines.append(f"FAIL  {name}:\n{traceback.format_exc()}")

        o = Options(out_dir=d / "out")
        check("png -> avif", lambda: registry.convert_file(png, "avif", o).outputs)
        check("png -> webp / ico / tga", lambda: [registry.convert_file(png, t, o).outputs for t in ("webp", "ico",
                                                                                                    "tga")])
        check("images -> pdf", lambda: registry.images_to_pdf([png, png], o))
        check("pdf -> png (pdfium)", lambda: registry.convert_file(registry.images_to_pdf([png], o), "png", o).outputs)
        check("pdf compress (pikepdf)", lambda: registry.compress_file(registry.images_to_pdf([png], o), o).outputs)
        check("json -> yaml/toml/xml/xlsx/csv", lambda: [registry.convert_file(d / "data.json", t, o).outputs
                                                         for t in ("yaml", "toml", "xml", "xlsx", "csv")])
        check("pack zip/7z/tar.gz + extract", lambda: [
            registry.convert_file(registry.pack_files([png], f, o), "folder", o).outputs for f in ("zip", "7z",
                                                                                                    "tar.gz")])
        check("ttf -> woff2", lambda: registry.convert_file(d / "font.ttf", "woff2", o).outputs)
        check("srt -> vtt/ass", lambda: [registry.convert_file(d / "subs.srt", t, o).outputs for t in ("vtt", "ass")])
        check("markdown -> html", lambda: registry.convert_file(d / "notes.md", "html", o).outputs)
        if ffmpeg:
            wav = d / "tone.wav"
            check("ffmpeg runs", lambda: run_process([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                                                      "-i", "sine=duration=1", str(wav)])[0] == 0 or 1 / 0)
            check("wav -> mp3", lambda: registry.convert_file(wav, "mp3", o).outputs)
            check("png -> heic -> jpg", lambda: registry.convert_file(registry.convert_file(png, "heic", o).outputs[0],
                                                                      "jpg", o).outputs)
        else:
            failed += 1
            lines.append("FAIL  ffmpeg not found")
    text = "\n".join(lines) + f"\n\n{failed} failed\n"
    target = report_path or Path(tempfile.gettempdir()) / "PixNexa-self-test.txt"
    try:
        target.write_text(text, encoding="utf-8")
    except OSError:
        pass
    print(text)
    return failed


if __name__ == "__main__":
    raise SystemExit(run())

"""Sample files made on the fly, and markers for tests that need FFmpeg or LibreOffice."""
import shutil
import subprocess

import pytest

from pixnexa_engines.media import find_ffmpeg
from pixnexa_engines.office import find_soffice

FFMPEG = find_ffmpeg()
SOFFICE = find_soffice()

needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="FFmpeg is not installed")
needs_libreoffice = pytest.mark.skipif(SOFFICE is None, reason="LibreOffice is not installed")


def _ffmpeg_has(encoder: str) -> bool:
    if FFMPEG is None:
        return False
    out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return f" {encoder} " in out


needs_x265 = pytest.mark.skipif(not _ffmpeg_has("libx265"), reason="FFmpeg without libx265")


def make_text_pdf(path, pages=("Hello PixNexa",)):
    """A real PDF with a text layer (Helvetica), one page per string."""
    import pikepdf
    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                BaseFont=pikepdf.Name.Helvetica))
    for text in pages:
        content = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
        page = pikepdf.Dictionary(Type=pikepdf.Name.Page, MediaBox=[0, 0, 612, 792],
                                  Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)),
                                  Contents=pikepdf.Stream(pdf, content))
        pdf.pages.append(pikepdf.Page(page))
    pdf.save(path)
    return path


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory):
    """Two seconds of test picture with a tone (320x240), made by FFmpeg."""
    if FFMPEG is None:
        pytest.skip("FFmpeg is not installed")
    path = tmp_path_factory.mktemp("media") / "clip.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=size=320x240:rate=25:duration=2", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", str(path)], check=True)
    return path


@pytest.fixture(scope="session")
def sample_audio(tmp_path_factory):
    if FFMPEG is None:
        pytest.skip("FFmpeg is not installed")
    path = tmp_path_factory.mktemp("media") / "tone.wav"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", str(path)], check=True)
    return path


@pytest.fixture()
def copy_of(tmp_path):
    def _copy(src, name=None):
        dst = tmp_path / (name or src.name)
        shutil.copyfile(src, dst)
        return dst
    return _copy

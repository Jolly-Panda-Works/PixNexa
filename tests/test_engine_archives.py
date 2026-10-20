"""Archives: extract, repack, pack many files, and refuse unsafe archives."""
import io
import tarfile
import zipfile

import py7zr
import pytest

from pixnexa_engines import ConversionError, Options, registry
from pixnexa_engines.archives import archive_stem, archive_suffix


def files(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("alpha")
    sub = tmp_path / "folder"
    sub.mkdir()
    (sub / "b.txt").write_text("beta")
    return a, sub


def test_suffixes():
    assert archive_suffix("x.tar.gz") == ".tar.gz" and archive_stem("x.tar.gz") == "x"
    assert archive_suffix("x.TGZ") == ".tgz" and archive_stem("photos.zip") == "photos"
    assert archive_suffix("readme.txt") is None


@pytest.mark.parametrize("fmt", ["zip", "7z", "tar.gz"])
def test_pack_and_extract_roundtrip(tmp_path, fmt):
    a, sub = files(tmp_path)
    archive = registry.pack_files([a, sub], fmt, Options(out_dir=tmp_path / "out"))
    assert archive.name == f"a.{fmt}"
    folder = registry.convert_file(archive, "folder", Options()).outputs[0]
    assert folder.name == "a" and folder.is_dir()
    assert (folder / "a.txt").read_text() == "alpha"
    assert (folder / "folder" / "b.txt").read_text() == "beta"


def test_pack_same_names_do_not_collide(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    one, two = tmp_path / "x" / "same.txt", tmp_path / "y" / "same.txt"
    one.write_text("1")
    two.write_text("2")
    archive = registry.pack_files([one, two], "zip")
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == ["same (1).txt", "same.txt"]


def test_pack_name_never_overwrites(tmp_path):
    a, _ = files(tmp_path)
    first = registry.pack_files([a], "tar.gz")
    second = registry.pack_files([a], "tar.gz")
    assert first.name == "a.tar.gz" and second.name == "a (1).tar.gz"


def test_single_top_folder_is_flattened(tmp_path):
    src = tmp_path / "photos.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("photos/one.txt", "1")
        z.writestr("photos/deep/two.txt", "2")
    folder = registry.convert_file(src, "folder", Options()).outputs[0]
    assert (folder / "one.txt").exists() and (folder / "deep" / "two.txt").exists()


@pytest.mark.parametrize("target", ["zip", "7z", "tar.gz"])
def test_repack(tmp_path, target):
    src = tmp_path / "in.tar.bz2"
    with tarfile.open(src, "w:bz2") as t:
        data = b"hello"
        info = tarfile.TarInfo("hello.txt")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    out = registry.convert_file(src, target, Options()).outputs[0]
    assert out.name == f"in.{target}"
    folder = registry.convert_file(out, "folder", Options(out_dir=tmp_path / "x")).outputs[0]
    assert (folder / "hello.txt").read_bytes() == b"hello"


def test_tar_xz_and_single_gz(tmp_path):
    src = tmp_path / "data.tar.xz"
    with tarfile.open(src, "w:xz") as t:
        info = tarfile.TarInfo("d.txt")
        info.size = 1
        t.addfile(info, io.BytesIO(b"x"))
    assert (registry.convert_file(src, "folder", Options()).outputs[0] / "d.txt").exists()
    import gzip
    gz = tmp_path / "log.txt.gz"
    gz.write_bytes(gzip.compress(b"log line"))
    folder = registry.convert_file(gz, "folder", Options()).outputs[0]
    assert (folder / "log.txt").read_bytes() == b"log line"


def test_zip_slip_is_refused(tmp_path):
    src = tmp_path / "evil.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("ok.txt", "fine")
        z.writestr("../escape.txt", "bad")
    with pytest.raises(ConversionError, match="outside"):
        registry.convert_file(src, "folder", Options())
    assert not (tmp_path.parent / "escape.txt").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["evil.zip"]


def test_tar_absolute_path_and_links_are_refused(tmp_path):
    src = tmp_path / "evil.tar"
    with tarfile.open(src, "w") as t:
        info = tarfile.TarInfo("/etc/evil")
        info.size = 0
        t.addfile(info, io.BytesIO(b""))
    with pytest.raises(ConversionError, match="outside"):
        registry.convert_file(src, "folder", Options())

    links = tmp_path / "links.tar"
    with tarfile.open(links, "w") as t:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        t.addfile(link)
        info = tarfile.TarInfo("real.txt")
        info.size = 2
        t.addfile(info, io.BytesIO(b"ok"))
    folder = registry.convert_file(links, "folder", Options()).outputs[0]
    assert (folder / "real.txt").exists() and not (folder / "link").exists()


def test_encrypted_7z_is_refused(tmp_path):
    secret = tmp_path / "s.txt"
    secret.write_text("x")
    src = tmp_path / "locked.7z"
    with py7zr.SevenZipFile(src, "w", password="pw") as z:
        z.write(secret, "s.txt")
    with pytest.raises(ConversionError, match="password"):
        registry.convert_file(src, "folder", Options())


def test_broken_zip(tmp_path):
    src = tmp_path / "broken.zip"
    src.write_bytes(b"PK\x03\x04 not really")
    with pytest.raises(ConversionError):
        registry.convert_file(src, "folder", Options())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.zip"]

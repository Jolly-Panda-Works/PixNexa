import set_version as sv


def test_default_version_is_read_from_version_file():
    assert sv.default_version().count(".") == 2


def test_compute_version_for_tags_main_and_other_branches():
    assert sv.compute_version("refs/tags/v2.3.4", "v2.3.4", "99", "2.0.0") == "2.3.4"
    assert sv.compute_version("refs/heads/main", "main", "37", "2.0.0") == "2.0.37"
    assert sv.compute_version("refs/heads/develop", "develop", "12", "2.0.0") == "2.0.0-dev.12"
    assert sv.compute_version("refs/pull/5/merge", "5/merge", "8", "2.1.0") == "2.1.0-dev.8"


def test_numeric_version_has_four_parts():
    assert sv.numeric_version("2.0.37") == (2, 0, 37, 0)
    assert sv.numeric_version("2.0.0-dev.12") == (2, 0, 0, 12)
    assert sv.numeric_version("2.1") == (2, 1, 0, 0)


def test_write_files(tmp_path):
    sv.write_files("2.0.5", root=tmp_path)
    assert (tmp_path / "_build_version.py").read_text() == 'APP_VERSION = "2.0.5"\n'
    info = (tmp_path / "version_info.txt").read_text()
    assert "filevers=(2, 0, 5, 0)" in info and "PixNexa.exe" in info
    compile(info.replace("VSVersionInfo", "dict") .replace("FixedFileInfo", "dict").replace("StringFileInfo", "list")
            .replace("StringTable", "tuple").replace("StringStruct", "tuple").replace("VarFileInfo", "list")
            .replace("VarStruct", "tuple"), "version_info", "eval")

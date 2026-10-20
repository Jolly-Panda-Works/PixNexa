"""Video and audio through FFmpeg. Skipped when FFmpeg is not installed (the release build bundles it)."""
import threading

import pytest
from conftest import needs_ffmpeg, needs_x265

from pixnexa_engines import Cancelled, ConversionError, Options, media, registry


def test_missing_ffmpeg_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "find_ffmpeg", lambda: None)
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"\x00" * 100)
    with pytest.raises(ConversionError, match="FFmpeg was not found"):
        registry.convert_file(src, "webm", Options())
    with pytest.raises(ConversionError, match="FFmpeg was not found"):
        registry.compress_file(src, Options())


def test_find_ffmpeg_prefers_the_bundled_copy(tmp_path, monkeypatch):
    bundled = tmp_path / "ffmpeg" / media.EXE
    bundled.parent.mkdir()
    bundled.write_bytes(b"")
    monkeypatch.delenv("PIXNEXA_FFMPEG", raising=False)
    monkeypatch.setattr(media, "app_dir", lambda: tmp_path)
    assert media.find_ffmpeg() == str(bundled)
    monkeypatch.setenv("PIXNEXA_FFMPEG", str(bundled))
    assert media.find_ffmpeg() == str(bundled)


@needs_ffmpeg
def test_probe(sample_video, sample_audio):
    info = media.probe(sample_video)
    assert info.has_video and info.has_audio and 1.5 < info.duration < 2.5 and (info.width, info.height) == (320, 240)
    audio = media.probe(sample_audio)
    assert audio.has_audio and not audio.has_video


@needs_ffmpeg
def test_probe_rejects_non_media(tmp_path):
    bad = tmp_path / "x.mp4"
    bad.write_text("not a video")
    with pytest.raises(ConversionError):
        media.probe(bad)


@needs_ffmpeg
@pytest.mark.parametrize("target", ["webm", "mkv", "mov", "avi", "gif", "mp3", "m4a", "wav", "flac", "ogg", "opus"])
def test_video_targets(sample_video, copy_of, target):
    src = copy_of(sample_video)
    seen = []
    out = registry.convert_file(src, target, Options(video_quality="small"), seen.append).outputs[0]
    assert out.suffix == f".{target}" and out.stat().st_size > 100
    assert seen and seen[-1] == 1.0                   # per-file progress from -progress pipe:1
    info = media.probe(out)
    assert info.has_video == (target in ("webm", "mkv", "mov", "avi", "gif"))


@needs_ffmpeg
def test_video_to_mp4_with_scale(sample_video, copy_of):
    src = copy_of(sample_video, "in.mov")
    out = registry.convert_file(src, "mp4", Options(max_height_px=120)).outputs[0]
    info = media.probe(out)
    assert info.height == 120 and info.width == 160


@needs_ffmpeg
@pytest.mark.parametrize("target", ["mp3", "m4a", "flac", "ogg", "opus", "wav"])
def test_audio_targets(sample_audio, copy_of, target):
    src = copy_of(sample_audio)
    if target == "wav":
        src = registry.convert_file(src, "flac", Options()).outputs[0]
    out = registry.convert_file(src, target, Options(audio_bitrate=128)).outputs[0]
    assert out.suffix == f".{target}" and media.probe(out).has_audio


@needs_ffmpeg
def test_audio_has_no_video_target(sample_audio, copy_of):
    with pytest.raises(ConversionError):
        registry.convert_file(copy_of(sample_audio), "mp4", Options())


@needs_ffmpeg
def test_compress_video_h264(sample_video, copy_of):
    src = copy_of(sample_video)
    res = registry.compress_file(src, Options(video_quality="small", max_height_px=120))
    out = res.outputs[0]
    assert out.name == "clip-compressed.mp4"
    assert media.probe(out).height == 120               # the smaller size asked for, even if the file is not smaller


@needs_ffmpeg
def test_compress_video_never_bigger_without_scaling(sample_video, copy_of):
    src = copy_of(sample_video)
    res = registry.compress_file(src, Options(video_quality="high"))
    assert res.outputs[0].stat().st_size <= src.stat().st_size


@needs_ffmpeg
@needs_x265
def test_compress_video_h265(sample_video, copy_of):
    out = registry.compress_file(copy_of(sample_video), Options(video_codec="h265")).outputs[0]
    assert out.suffix == ".mp4" and media.probe(out).has_video


@needs_ffmpeg
def test_compress_audio_wav_becomes_mp3(sample_audio, copy_of):
    src = copy_of(sample_audio)
    out = registry.compress_file(src, Options(audio_bitrate=64)).outputs[0]
    assert out.name == "tone-compressed.mp3" and out.stat().st_size < src.stat().st_size


@needs_ffmpeg
def test_stop_kills_ffmpeg_and_leaves_nothing(sample_video, copy_of, tmp_path):
    src = copy_of(sample_video)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        registry.convert_file(src, "webm", Options(cancel=cancel))
    assert not list(tmp_path.glob("*.webm")) and not list(tmp_path.glob("*.part*"))

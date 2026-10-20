"""HEIC writer: the picture is encoded to HEVC by FFmpeg (a separate program) and wrapped in a HEIF file here.

Why not pillow-heif? Its Windows wheels link the x265 encoder (GPL) into the Python process. PixNexa reads
HEIC with pi-heif (decode only, LGPL libraries) and writes it with the FFmpeg program it ships anyway.

The file is the simple form every HEIF reader understands (Windows Photos with the HEIF extensions, macOS,
iOS, libheif): one 'hvc1' coded image, its size ('ispe'), its colours ('colr' nclx: sRGB, BT.601, full range)
and, for odd sizes, a crop ('clap') because 4:2:0 HEVC needs even sizes.
"""
from __future__ import annotations

import struct

from PIL import Image

from .base import ConversionError
from .media import find_ffmpeg, run_ffmpeg_bytes

_VPS, _SPS, _PPS = 32, 33, 34


def encode_heic(img: Image.Image, quality: int = 90) -> bytes:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise ConversionError("HEIC output needs FFmpeg, which was not found. Reinstall PixNexa, "
                              "or put ffmpeg.exe in the 'ffmpeg' folder next to PixNexa.exe.")
    rgb = img.convert("RGB")
    width, height = rgb.size
    # 4:2:0 HEVC needs even sizes, and x265 refuses very small pictures: pad, and crop back with 'clap'
    padded_w, padded_h = max(16, width + (width & 1)), max(16, height + (height & 1))
    if (padded_w, padded_h) != (width, height):
        canvas = Image.new("RGB", (padded_w, padded_h))
        canvas.paste(rgb, (0, 0))
        if padded_w != width:      # repeat the last column / row so the crop edge has no dark seam
            canvas.paste(rgb.crop((width - 1, 0, width, height)).resize((padded_w - width, height)), (width, 0))
        if padded_h != height:
            canvas.paste(canvas.crop((0, height - 1, padded_w, height)).resize((padded_w, padded_h - height)),
                         (0, height))
        rgb = canvas

    crf = max(0, min(51, round(50 - 0.4 * max(1, min(100, int(quality))))))     # 90 -> 14, 50 -> 30
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{padded_w}x{padded_h}", "-i", "pipe:0", "-frames:v", "1",
            "-vf", "scale=out_color_matrix=bt601:out_range=full:flags=accurate_rnd+full_chroma_int",
            "-pix_fmt", "yuv420p", "-color_range", "pc", "-colorspace", "smpte170m",
            "-c:v", "libx265", "-preset", "medium", "-crf", str(crf),
            "-x265-params", "log-level=error:keyint=1:info=0", "-f", "hevc", "pipe:1"]
    stream = run_ffmpeg_bytes(args, rgb.tobytes())
    return build_heif(stream, padded_w, padded_h, width, height)


# ───────────────────────── HEVC bitstream ─────────────────────────

def split_annexb(data: bytes) -> list[bytes]:
    """NAL units of an Annex-B stream (start codes 00 00 01 / 00 00 00 01 removed)."""
    units, i, n = [], 0, len(data)
    starts = []
    while True:
        j = data.find(b"\x00\x00\x01", i)
        if j < 0:
            break
        starts.append(j + 3)
        i = j + 3
    for k, s in enumerate(starts):
        end = (starts[k + 1] - 3) if k + 1 < len(starts) else n
        unit = data[s:end]
        while unit.endswith(b"\x00"):         # the zero before a 4-byte start code belongs to no unit
            unit = unit[:-1]
        if unit:
            units.append(unit)
    return units


def nal_type(unit: bytes) -> int:
    return (unit[0] >> 1) & 0x3F


def _rbsp(unit: bytes) -> bytes:
    """Remove emulation prevention bytes (00 00 03 -> 00 00)."""
    out, zeros = bytearray(), 0
    for b in unit:
        if zeros >= 2 and b == 3:
            zeros = 0
            continue
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    return bytes(out)


def hvcc_box(units: list[bytes]) -> bytes:
    sps = next((u for u in units if nal_type(u) == _SPS), None)
    if sps is None or not any(nal_type(u) == _VPS for u in units) or not any(nal_type(u) == _PPS for u in units):
        raise ConversionError("FFmpeg did not produce a complete HEVC picture.")
    rbsp = _rbsp(sps)
    # rbsp[0:2] NAL header, rbsp[2]: vps id / max sub layers / nesting, rbsp[3:15]: general profile_tier_level
    ptl = rbsp[3:15]
    if len(ptl) < 12:
        raise ConversionError("FFmpeg produced an unreadable HEVC picture.")
    profile_byte, compat, constraint, level = ptl[0], ptl[1:5], ptl[5:11], ptl[11]
    body = bytearray()
    body.append(1)                                   # configurationVersion
    body.append(profile_byte)                        # profile_space, tier, profile_idc
    body += compat + constraint
    body.append(level)
    body += struct.pack(">H", 0xF000)                # min_spatial_segmentation_idc = 0
    body.append(0xFC)                                # parallelismType = 0
    body.append(0xFC | 1)                            # chroma_format_idc = 1 (4:2:0)
    body.append(0xF8 | 0)                            # bit depth luma - 8
    body.append(0xF8 | 0)                            # bit depth chroma - 8
    body += struct.pack(">H", 0)                     # avgFrameRate
    body.append((0 << 6) | (1 << 3) | (1 << 2) | 3)  # constantFrameRate, 1 temporal layer, nested, 4-byte lengths
    arrays = [(t, [u for u in units if nal_type(u) == t]) for t in (_VPS, _SPS, _PPS)]
    body.append(len(arrays))
    for t, nals in arrays:
        body.append(0x80 | t)                        # array_completeness = 1
        body += struct.pack(">H", len(nals))
        for u in nals:
            body += struct.pack(">H", len(u)) + u
    return _box(b"hvcC", bytes(body))


# ───────────────────────── HEIF boxes ─────────────────────────

def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _full_box(kind: bytes, version: int, flags: int, payload: bytes) -> bytes:
    return _box(kind, struct.pack(">I", (version << 24) | flags) + payload)


def build_heif(stream: bytes, coded_w: int, coded_h: int, width: int | None = None, height: int | None = None) -> bytes:
    units = split_annexb(stream)
    hvcc = hvcc_box(units)
    picture = b"".join(struct.pack(">I", len(u)) + u for u in units if nal_type(u) < 32)   # slice data only
    if not picture:
        raise ConversionError("FFmpeg did not produce a HEVC picture.")
    width, height = width or coded_w, height or coded_h

    props = [hvcc,
             _full_box(b"ispe", 0, 0, struct.pack(">II", coded_w, coded_h)),
             _box(b"colr", b"nclx" + struct.pack(">HHHB", 1, 13, 6, 0x80))]    # BT.709 primaries, sRGB, BT.601
    assoc = [(True, 1), (False, 2), (False, 3)]
    if (width, height) != (coded_w, coded_h):
        # clean aperture: the centre offset of the crop, (w - W) / 2, keeps the top-left corner in place
        props.append(_box(b"clap", struct.pack(">IIIIiIiI", width, 1, height, 1, width - coded_w, 2,
                                               height - coded_h, 2)))
        assoc.append((True, 4))

    ftyp = _box(b"ftyp", b"heic" + struct.pack(">I", 0) + b"mif1heic")
    hdlr = _full_box(b"hdlr", 0, 0, struct.pack(">I", 0) + b"pict" + b"\x00" * 12 + b"\x00")
    pitm = _full_box(b"pitm", 0, 0, struct.pack(">H", 1))
    infe = _full_box(b"infe", 2, 0, struct.pack(">HH", 1, 0) + b"hvc1" + b"\x00")
    iinf = _full_box(b"iinf", 0, 0, struct.pack(">H", 1) + infe)
    ipco = _box(b"ipco", b"".join(props))
    ipma = _full_box(b"ipma", 0, 0, struct.pack(">IHB", 1, 1, len(assoc))
                     + bytes((0x80 if essential else 0) | index for essential, index in assoc))
    iprp = _box(b"iprp", ipco + ipma)

    def meta_with(offset: int) -> bytes:
        iloc = _full_box(b"iloc", 0, 0, bytes([0x44, 0x00]) + struct.pack(">HHHHII", 1, 1, 0, 1, offset,
                                                                          len(picture)))
        return _full_box(b"meta", 0, 0, hdlr + pitm + iloc + iinf + iprp)

    meta = meta_with(0)
    offset = len(ftyp) + len(meta) + 8              # the picture starts right after the mdat header
    meta = meta_with(offset)
    return ftyp + meta + _box(b"mdat", picture)

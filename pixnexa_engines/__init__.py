"""PixNexa conversion engines: one module per kind of file, tied together by `registry`.

    from pixnexa_engines import Options, registry
    registry.convert_file("song.flac", "mp3", Options(audio_bitrate=192))
"""
from . import registry
from .base import Cancelled, ConversionError, Options

__all__ = ["Cancelled", "ConversionError", "Options", "registry"]

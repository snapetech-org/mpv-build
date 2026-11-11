#!/usr/bin/env python3
"""Execute the linked music filter graph with generated audio and file output."""
import argparse
import ctypes as c
import math
from pathlib import Path
import struct
import tempfile
import time
import wave

REQUIRED = ('aecho', 'aformat', 'aresample', 'asetrate', 'aspectralstats',
            'atempo', 'bass', 'equalizer', 'stereowiden', 'treble', 'volume')


def verify(library):
    lib = c.CDLL(str(Path(library).resolve()))
    lib.avfilter_get_by_name.argtypes = [c.c_char_p]
    lib.avfilter_get_by_name.restype = c.c_void_p
    missing = [name for name in REQUIRED if not lib.avfilter_get_by_name(name.encode())]
    if missing:
        raise ValueError('linked FFmpeg omits music filters: ' + ', '.join(missing))
    lib.mpv_create.restype = c.c_void_p
    lib.mpv_set_option_string.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
    lib.mpv_initialize.argtypes = [c.c_void_p]
    lib.mpv_command_string.argtypes = [c.c_void_p, c.c_char_p]
    lib.mpv_get_property.argtypes = [c.c_void_p, c.c_char_p, c.c_int, c.c_void_p]
    lib.mpv_terminate_destroy.argtypes = [c.c_void_p]
    with tempfile.TemporaryDirectory(prefix='music-dsp-') as directory:
        root = Path(directory)
        source = root / 'tone.wav'
        with wave.open(str(source), 'wb') as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(48000)
            writer.writeframes(b''.join(struct.pack('<hh', *(2 * [
                round(.2 * 32767 * math.sin(i * 2 * math.pi * 440 / 48000))
            ])) for i in range(24000)))
        for name, graph, expected in (
            ('flat', '', .2),
            ('peak', 'equalizer=f=440:t=q:w=1:g=6', .39905),
            ('low', 'bass=f=440:t=q:w=0.707:g=6', .2825),
            ('high', 'treble=f=440:t=q:w=0.707:g=6', .2825),
            ('gain', 'volume=-6.0206dB', .1),
        ):
            output = root / (name + '.wav')
            ctx = lib.mpv_create()
            if not ctx:
                raise ValueError('could not create native decoder')
            try:
                options = {'config': 'no', 'terminal': 'no', 'vo': 'null', 'ao': 'pcm',
                           'audio-display': 'no', 'audio-format': 'float',
                           'audio-samplerate': '48000', 'volume': '100',
                           'idle': 'yes', 'keep-open': 'yes', 'replaygain': 'no',
                           'ao-pcm-file': str(output), 'af': 'lavfi=[' + graph + ']' if graph else ''}
                for key, value in options.items():
                    if lib.mpv_set_option_string(ctx, key.encode(), value.encode()) < 0:
                        raise ValueError('native option rejected: ' + key)
                if lib.mpv_initialize(ctx) < 0:
                    raise ValueError('native initialization rejected')
                if lib.mpv_command_string(ctx, ('loadfile ' + str(source)).encode()) < 0:
                    raise ValueError('generated audio did not open')
                deadline = time.monotonic() + 5
                # keep-open parks at EOF, so poll its explicit EOF flag.
                while time.monotonic() < deadline:
                    eof = c.c_int()
                    if lib.mpv_get_property(ctx, b'eof-reached', 3, c.byref(eof)) == 0 and eof.value:
                        break
                    time.sleep(.01)
                else:
                    raise ValueError('generated audio did not finish: ' + name)
            finally:
                lib.mpv_terminate_destroy(ctx)
            data = output.read_bytes()
            position = 12
            encoding = bits = None
            payload = None
            while position + 8 <= len(data):
                kind, size = struct.unpack_from('<4sI', data, position)
                chunk = data[position + 8:position + 8 + size]
                if kind == b'fmt ':
                    encoding, channels, rate = struct.unpack_from('<HHI', chunk)
                    bits = struct.unpack_from('<H', chunk, 14)[0]
                    if encoding == 65534:
                        encoding = struct.unpack_from('<H', chunk, 24)[0]
                    if channels != 2 or rate != 48000:
                        raise ValueError('unexpected native output format')
                if kind == b'data':
                    payload = chunk
                position += 8 + size + (size & 1)
            if encoding != 3 or bits != 32 or payload is None:
                raise ValueError('expected float32 WAV')
            samples = struct.unpack('<' + 'f' * (len(payload) // 4), payload)
            middle = samples[4800:-4800]
            if not middle or any(not math.isfinite(v) for v in middle):
                raise ValueError('missing or non-finite native DSP output')
            peak = max(abs(v) for v in middle)
            if abs(peak - expected) > .003:
                raise ValueError(f'{name}: native peak {peak} differs from {expected}')
            print(f'{name}: native peak {peak:.7f}', flush=True)
    print('linked music filters and generated native DSP output verified', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    verify(parser.parse_args().library)

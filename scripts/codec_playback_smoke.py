#!/usr/bin/env python3
"""Decode and seek generated fixtures through the exact supplied libmpv.

Host ffmpeg only creates fixtures; it is never the decoder under test. A worker
process per fixture bounds native crashes/hangs. This verifies software decode
and seek, not HDR presentation, passthrough, performance or every codec profile.
"""
from __future__ import annotations

import argparse
import ctypes as c
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tempfile
import time

from codec_inventory import Node, decode_node


# name, encoder, container, pixel format, extra encoder arguments. All sources
# are generated test signals; no downloaded or redistributed media is needed.
VIDEO = (
    ('h264', 'libx264', 'mkv', 'yuv420p', ('-preset', 'ultrafast')),
    ('h264-10bit', 'libx264', 'mkv', 'yuv420p10le', ('-preset', 'ultrafast')),
    ('hevc-10bit', 'libx265', 'mkv', 'yuv420p10le', ('-preset', 'ultrafast', '-x265-params', 'pools=1:frame-threads=1:log-level=error')),
    ('av1', 'libaom-av1', 'mkv', 'yuv420p', ('-cpu-used', '8')),
    ('vp9-10bit', 'libvpx-vp9', 'webm', 'yuv420p10le', ('-deadline', 'realtime', '-cpu-used', '8')),
    ('vp8', 'libvpx', 'webm', 'yuv420p', ('-deadline', 'realtime')),
    ('mpeg2', 'mpeg2video', 'mpg', 'yuv420p', ()),
    ('mpeg4', 'mpeg4', 'avi', 'yuv420p', ()),
    ('wmv2', 'wmv2', 'asf', 'yuv420p', ()),
    ('prores', 'prores_ks', 'mov', 'yuv422p10le', ('-profile:v', '2')),
    ('ffv1', 'ffv1', 'mkv', 'yuv444p10le', ('-level', '3')),
    ('huffyuv', 'huffyuv', 'avi', 'yuv422p', ()),
    ('mjpeg', 'mjpeg', 'avi', 'yuvj420p', ()),
    ('jpeg2000', 'jpeg2000', 'mkv', 'yuv444p', ()),
    ('theora', 'libtheora', 'ogv', 'yuv420p', ()),
    ('flv1', 'flv', 'flv', 'yuv420p', ()),
    ('qtrle', 'qtrle', 'mov', 'rgb24', ()),
    ('cinepak', 'cinepak', 'avi', 'rgb24', ()),
)
AUDIO = (
    ('aac', 'aac', 'm4a'), ('mp3', 'libmp3lame', 'mp3'),
    ('opus', 'libopus', 'ogg'), ('vorbis', 'libvorbis', 'ogg'),
    ('flac', 'flac', 'flac'), ('alac', 'alac', 'm4a'),
    ('ac3', 'ac3', 'ac3'), ('eac3', 'eac3', 'eac3'),
    ('pcm', 'pcm_s24le', 'wav'), ('wavpack', 'wavpack', 'wv'),
)


class Event(c.Structure):
    _fields_ = [('event_id', c.c_int), ('error', c.c_int),
                ('reply_userdata', c.c_uint64), ('data', c.c_void_p)]


class EndFile(c.Structure):
    _fields_ = [('reason', c.c_int), ('error', c.c_int)]


def execute(library, source, kind, *, expected_dimensions=(128, 96), minimum_position=None,
            seek_position="0.5", extra_options=None):
    lib = c.CDLL(str(Path(library).resolve(strict=True)))
    lib.mpv_create.restype = c.c_void_p
    lib.mpv_set_option_string.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
    lib.mpv_initialize.argtypes = [c.c_void_p]
    lib.mpv_command.argtypes = [c.c_void_p, c.POINTER(c.c_char_p)]
    lib.mpv_get_property.argtypes = [c.c_void_p, c.c_char_p, c.c_int, c.c_void_p]
    lib.mpv_free_node_contents.argtypes = [c.POINTER(Node)]
    lib.mpv_terminate_destroy.argtypes = [c.c_void_p]
    lib.mpv_wait_event.argtypes = [c.c_void_p, c.c_double]
    lib.mpv_wait_event.restype = c.POINTER(Event)
    ctx = lib.mpv_create()
    if not ctx:
        raise ValueError('mpv_create failed')
    output_directory = tempfile.TemporaryDirectory(prefix='codec-pcm-')
    pcm = Path(output_directory.name) / 'decoded.wav'
    report = None

    def command(*args):
        argv = (c.c_char_p * (len(args) + 1))(*(arg.encode() for arg in args), None)
        if lib.mpv_command(ctx, argv) < 0:
            raise ValueError('native command rejected: ' + args[0])

    def prop(name):
        node = Node()
        if lib.mpv_get_property(ctx, name.encode(), 6, c.byref(node)) < 0:
            return None
        try:
            return decode_node(node)
        finally:
            lib.mpv_free_node_contents(c.byref(node))

    def finish(require_restart=False):
        deadline = time.monotonic() + 12
        restarted = not require_restart
        while time.monotonic() < deadline:
            event = lib.mpv_wait_event(ctx, .02).contents
            if event.event_id == 7 and event.data:  # MPV_EVENT_END_FILE
                end = c.cast(event.data, c.POINTER(EndFile)).contents
                if end.error < 0 or end.reason == 4:
                    raise ValueError(f'native playback failed: {end.error}')
            if event.event_id == 21:  # MPV_EVENT_PLAYBACK_RESTART
                restarted = True
            # eof-reached can precede draining the audio output queue. Wait
            # for the parked core before inspecting its final presentation time.
            if restarted and prop('eof-reached') is True and prop('core-idle') is True:
                position = prop('time-pos')
                # Packet-based audio clocks can park before the last decoded
                # samples. Audio completeness is checked in the PCM output.
                minimum = minimum_position if minimum_position is not None else (1.8 if kind == 'video' else .5)
                if not isinstance(position, (float, int)) or position < minimum:
                    raise ValueError(f'media ended before the generated signal decoded: {position}')
                return position
        raise TimeoutError('native decode/seek did not finish')

    try:
        options = {'config': 'no', 'terminal': 'no', 'vo': 'null', 'ao': 'null',
                           'hwdec': 'no', 'idle': 'yes', 'keep-open': 'yes',
                           'audio-display': 'no', 'ytdl': 'no', 'load-scripts': 'no',
                           'osc': 'no'}
        options.update(extra_options or {})
        if kind == 'audio':
            options.update({'ao': 'pcm', 'ao-pcm-file': str(pcm), 'audio-format': 's16',
                            'audio-samplerate': '48000', 'audio-channels': 'stereo'})
        for key, value in options.items():
            if lib.mpv_set_option_string(ctx, key.encode(), value.encode()) < 0:
                raise ValueError('native option rejected: ' + key)
        if lib.mpv_initialize(ctx) < 0:
            raise ValueError('native initialization failed')
        command('loadfile', str(Path(source).resolve()))
        first = finish(require_restart=True)
        params = prop('video-out-params' if kind == 'video' else 'audio-params')
        if not isinstance(params, dict) or not params:
            raise ValueError('no decoded output parameters')
        if kind == 'video' and (params.get('w'), params.get('h')) != expected_dimensions:
            raise ValueError('decoded dimensions differ from fixture')
        # Drain old playback-restart events before testing the seek operation.
        while lib.mpv_wait_event(ctx, 0).contents.event_id:
            pass
        command('seek', seek_position, 'absolute+exact')
        command('set', 'pause', 'no')
        second = finish(require_restart=True)
        report = {'decode': 'passed', 'seek': 'passed', 'firstEnd': first,
                  'seekEnd': second, 'output': params, 'hardwareDecoding': False}
    finally:
        lib.mpv_terminate_destroy(ctx)
        try:
            if report is not None and kind == 'audio':
                data = pcm.read_bytes()
                cursor, payload = 12, b''
                while cursor + 8 <= len(data):
                    tag, size = struct.unpack_from('<4sI', data, cursor)
                    if tag == b'data':
                        payload = data[cursor + 8:cursor + 8 + size]
                        break
                    cursor += 8 + size + (size & 1)
                seconds = len(payload) / (48000 * 2 * 2)
                if not 3.2 <= seconds <= 4.0 or not any(payload):
                    raise ValueError(f'incomplete decode/seek PCM output: {seconds}s')
                report['pcmSeconds'] = seconds
        finally:
            output_directory.cleanup()
    return report


def generate(ffmpeg, root):
    fixtures = []
    for name, encoder, container, pixels, extra in VIDEO:
        path = root / f'{name}.{container}'
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'testsrc2=size=128x96:rate=25:duration=2',
                        '-an', '-c:v', encoder, '-threads', '1', '-pix_fmt', pixels,
                        *extra, str(path)], check=True, timeout=90)
        fixtures.append((name, path, 'video'))
    for name, encoder, container in AUDIO:
        path = root / f'{name}.{container}'
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'sine=frequency=997:sample_rate=48000:duration=2',
                        '-ac', '2', '-c:a', encoder, str(path)], check=True, timeout=30)
        fixtures.append((name, path, 'audio'))
    return fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--kind', choices=['video', 'audio'])
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(execute(args.library, args.worker, args.kind)))
        return
    results = {}
    with tempfile.TemporaryDirectory(prefix='codec-playback-') as directory:
        for name, path, kind in generate(args.ffmpeg, Path(directory)):
            try:
                result = subprocess.run([sys.executable, __file__, str(args.library.resolve()),
                                         '--worker', str(path), '--kind', kind],
                                        capture_output=True, text=True, timeout=35)
                results[name] = (json.loads(result.stdout) if result.returncode == 0 else
                                 {'error': result.stderr[-4000:], 'returncode': result.returncode})
            except subprocess.TimeoutExpired:
                results[name] = {'error': 'native worker timed out'}
            results[name]['fixtureSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            print(f'{name}: ' + (results[name].get('error') or 'decode and seek passed'), flush=True)
    with args.library.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'schemaVersion': 1, 'evidence': 'generated-media-decode-and-seek',
              'binarySha256': digest, 'architecture': platform.machine(),
              'physicalOutputQualified': False, 'realTimeQualified': False,
              'results': results}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    failed = [name for name, result in results.items() if 'error' in result]
    if failed:
        raise SystemExit('Native playback failures: ' + ', '.join(failed))


if __name__ == '__main__':
    main()

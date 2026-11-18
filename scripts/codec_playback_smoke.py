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

from urllib.request import urlopen

from codec_inventory import Node, decode_node


# name, encoder, container, pixel format, extra encoder arguments. All sources
# are generated test signals; no downloaded or redistributed media is needed.
VIDEO = (
    ('h264', 'libx264', 'mkv', 'yuv420p', ('-preset', 'ultrafast')),
    ('h264-10bit', 'libx264', 'mkv', 'yuv420p10le', ('-preset', 'ultrafast')),
    ('h264-422-10bit', 'libx264', 'mkv', 'yuv422p10le', ('-preset', 'ultrafast')),
    ('h264-444-10bit', 'libx264', 'mkv', 'yuv444p10le', ('-preset', 'ultrafast')),
    ('hevc-422-10bit', 'libx265', 'mov', 'yuv422p10le', ('-preset', 'ultrafast', '-x265-params', 'pools=1:frame-threads=1:log-level=error')),
    ('hevc-444-12bit', 'libx265', 'mkv', 'yuv444p12le', ('-preset', 'ultrafast', '-x265-params', 'pools=1:frame-threads=1:log-level=error')),
    ('hevc-10bit', 'libx265', 'mkv', 'yuv420p10le', ('-preset', 'ultrafast', '-x265-params', 'pools=1:frame-threads=1:log-level=error')),
    ('av1', 'libaom-av1', 'mkv', 'yuv420p', ('-cpu-used', '8')),
    ('av1-10bit', 'libaom-av1', 'mkv', 'yuv420p10le', ('-cpu-used', '8')),
    ('av1-444-12bit', 'libaom-av1', 'mkv', 'yuv444p12le', ('-cpu-used', '8')),
    ('vp9-10bit', 'libvpx-vp9', 'webm', 'yuv420p10le', ('-deadline', 'realtime', '-cpu-used', '8')),
    ('vp8', 'libvpx', 'webm', 'yuv420p', ('-deadline', 'realtime')),
    ('mpeg2', 'mpeg2video', 'mpg', 'yuv420p', ()),
    ('mpeg4', 'mpeg4', 'avi', 'yuv420p', ()),
    ('wmv2', 'wmv2', 'asf', 'yuv420p', ()),
    ('mpeg2-interlaced', 'mpeg2video', 'ts', 'yuv420p', ('-flags', '+ildct+ilme', '-top', '1')),
    ('mpeg1', 'mpeg1video', 'mpg', 'yuv420p', ()),
    ('prores', 'prores_ks', 'mov', 'yuv422p10le', ('-profile:v', '2')),
    ('ffv1', 'ffv1', 'mkv', 'yuv444p10le', ('-level', '3')),
    ('huffyuv', 'huffyuv', 'avi', 'yuv422p', ()),
    ('mjpeg', 'mjpeg', 'avi', 'yuvj420p', ()),
    ('jpeg2000', 'jpeg2000', 'mkv', 'yuv444p', ()),
    ('theora', 'libtheora', 'ogv', 'yuv420p', ()),
    ('flv1', 'flv', 'flv', 'yuv420p', ()),
    ('qtrle', 'qtrle', 'mov', 'rgb24', ()),
    ('cinepak', 'cinepak', 'avi', 'rgb24', ()),
    ('dnxhr-lb', 'dnxhd', 'mov', 'yuv422p', ('-profile:v', 'dnxhr_lb')),
    ('cineform', 'cfhd', 'mov', 'yuv422p10le', ()),
    ('dv-pal', 'dvvideo', 'dv', 'yuv420p', ()),
    ('utvideo', 'utvideo', 'avi', 'gbrp', ()),
    ('v210', 'v210', 'mov', 'yuv422p10le', ()),
    ('ffvhuff', 'ffvhuff', 'mkv', 'yuv422p', ()),
    ('msvideo1', 'msvideo1', 'avi', 'rgb555le', ()),
    ('msmpeg4v3', 'msmpeg4', 'avi', 'yuv420p', ()),
    ('flash-screen', 'flashsv', 'flv', 'bgr24', ()),
    ('dosbox-capture', 'zmbv', 'avi', 'bgr0', ()),
    ('yuv4mpeg', 'wrapped_avframe', 'y4m', 'yuv420p', ('-f', 'yuv4mpegpipe')),
)
# DNxHR and PAL DV have coded-size constraints unlike the small synthetic cases.
VIDEO_SIZES = {'dnxhr-lb': (640, 360), 'dv-pal': (720, 576)}

AUDIO = (
    ('aac', 'aac', 'm4a'), ('mp3', 'libmp3lame', 'mp3'),
    ('opus', 'libopus', 'ogg'), ('vorbis', 'libvorbis', 'ogg'),
    ('flac', 'flac', 'flac'), ('alac', 'alac', 'm4a'),
    ('ac3', 'ac3', 'ac3'), ('eac3', 'eac3', 'eac3'),
    ('pcm', 'pcm_s24le', 'wav'), ('wavpack', 'wavpack', 'wv'),
    ('dts', 'dca', 'dts'), ('truehd', 'truehd', 'mka'),
    ('wmav2', 'wmav2', 'asf'), ('mp2', 'mp2', 'mka'),
    ('true-audio', 'tta', 'tta'), ('adpcm-ima', 'adpcm_ima_wav', 'wav'),
    ('adpcm-ms', 'adpcm_ms', 'wav'), ('g711-alaw', 'pcm_alaw', 'wav'),
    ('g711-mulaw', 'pcm_mulaw', 'wav'),
)


PASSTHROUGH_CODECS = {'ac3', 'eac3', 'dts', 'truehd'}

BITMAP_SUBTITLES = (
    ('pgs-bitmap', 'pgs_sub.sup', '0.2'),
    ('vobsub-bitmap', 'vobsub.idx', '-132.2'),
    ('dvb-bitmap', 'dvbsubtest_filter.ts', '-79695.2'),
)
SUBTITLE_SOURCE_HASHES = {
    'pgs_sub.sup': 'ce6d8ed89cf557e34b90d49c5ce955731935c485b93892f69ab276cfe0c36c27',
    'vobsub.idx': 'c4d073e2bbf515409e9ee8bf32114b81c1a11178d3bf0d52d88ebab0615525e2',
    'vobsub.sub': '5f6ac43324e5a35c6e525aa0c76bafa9dd965a17ce0880fd7eb69e19b6853c8b',
    'dvbsubtest_filter.ts': '93ad6d0be649bb29697275ff522a983d475a1e58ab070271f912b86799e04a86',
}


class ByteArray(c.Structure):
    _fields_ = [('data', c.c_void_p), ('size', c.c_size_t)]


class Event(c.Structure):
    _fields_ = [('event_id', c.c_int), ('error', c.c_int),
                ('reply_userdata', c.c_uint64), ('data', c.c_void_p)]


class EndFile(c.Structure):
    _fields_ = [('reason', c.c_int), ('error', c.c_int)]


def execute(library, source, kind, *, expected_dimensions=(128, 96), minimum_position=None,
            seek_position="0.5", extra_options=None, expected_pixel_format=None, expected_subtitle=None,
            expected_bitmap=False, source_uri=None, minimum_chapters=None, seek_tolerance=None,
            pcm_duration_range=(3.2, 4.0), decode_timeout=12):
    library = Path(library).resolve(strict=True)
    if sys.platform == 'win32':
        import os
        dll_directory = os.add_dll_directory(str(library.parent))
    else:
        dll_directory = None
    lib = c.CDLL(str(library))
    lib.mpv_create.restype = c.c_void_p
    lib.mpv_set_option_string.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
    lib.mpv_initialize.argtypes = [c.c_void_p]
    lib.mpv_command.argtypes = [c.c_void_p, c.POINTER(c.c_char_p)]
    if expected_bitmap:
        lib.mpv_command_ret.argtypes = [c.c_void_p, c.POINTER(c.c_char_p), c.POINTER(Node)]
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

    def screenshot(mode, *, require_coded_size=True):
        result = Node()
        argv = (c.c_char_p * 4)(b'screenshot-raw', mode.encode(), b'rgba', None)
        if lib.mpv_command_ret(ctx, argv, c.byref(result)) < 0:
            raise ValueError(f'could not capture a software screenshot in {mode} mode')
        try:
            if result.format != 8 or not result.u.list:
                raise ValueError('screenshot returned no pixel data')
            entries = result.u.list.contents
            fields = {entries.keys[i].decode(): entries.values[i] for i in range(entries.num)}
            width, height, stride = (fields[key].u.int64 for key in ('w', 'h', 'stride'))
            pixels = fields['data']
            if pixels.format != 9:
                raise ValueError('screenshot returned an unexpected pixel payload')
            array = c.cast(pixels.u.pointer, c.POINTER(ByteArray)).contents
            if (require_coded_size and (width, height) != expected_dimensions) or (
                width <= 0 or height <= 0 or stride < width * 4 or array.size < stride * height
            ):
                raise ValueError('screenshot returned an unexpected frame layout')
            return b''.join(c.string_at(array.data + stride * row, width * 4) for row in range(height))
        finally:
            lib.mpv_free_node_contents(c.byref(result))

    def finish(require_restart=False):
        deadline = time.monotonic() + decode_timeout
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

    verify_subtitle = expected_subtitle is not None or expected_bitmap
    try:
        options = {'config': 'no', 'terminal': 'no', 'vo': 'null', 'ao': 'null',
                           'hwdec': 'no', 'idle': 'yes', 'keep-open': 'yes',
                           'audio-display': 'no', 'ytdl': 'no', 'load-scripts': 'no',
                           'osc': 'no'}
        options.update(extra_options or {})
        if verify_subtitle:
            options['sid'] = '1'
        if kind == 'audio':
            options.update({'ao': 'pcm', 'ao-pcm-file': str(pcm), 'audio-format': 's16',
                            'audio-samplerate': '48000', 'audio-channels': 'stereo'})
        for key, value in options.items():
            if lib.mpv_set_option_string(ctx, key.encode(), value.encode()) < 0:
                raise ValueError('native option rejected: ' + key)
        if lib.mpv_initialize(ctx) < 0:
            raise ValueError('native initialization failed')
        command('loadfile', source_uri if source_uri else str(Path(source).resolve()))
        first = finish(require_restart=True)
        params = prop('video-out-params' if kind == 'video' else 'audio-params')
        if not isinstance(params, dict) or not params:
            raise ValueError('no decoded output parameters')
        if kind == 'video' and (params.get('w'), params.get('h')) != expected_dimensions:
            raise ValueError('decoded dimensions differ from fixture')
        if expected_pixel_format is not None:
            decoded = prop('video-params')
            if not isinstance(decoded, dict) or decoded.get('pixelformat') != expected_pixel_format:
                raise ValueError(f'unexpected decoded pixel format: {decoded}')
        if minimum_chapters is not None:
            chapter_count = prop('chapters')
            if not isinstance(chapter_count, int) or chapter_count < minimum_chapters:
                raise ValueError(f'Expected at least {minimum_chapters} chapters, found {chapter_count}')
        second = seek_landed_at = None
        if seek_position is not None:
            while lib.mpv_wait_event(ctx, 0).contents.event_id:
                pass
            if verify_subtitle or seek_tolerance is not None:
                command('set', 'pause', 'yes')
            command('seek', seek_position, 'absolute+exact')
            if seek_tolerance is not None:
                deadline = time.monotonic() + decode_timeout
                while time.monotonic() < deadline:
                    event = lib.mpv_wait_event(ctx, .02).contents
                    if event.event_id != 21 or prop('eof-reached') is not False:
                        continue
                    position = prop('time-pos')
                    if isinstance(position, (float, int)) and abs(position - float(seek_position)) <= seek_tolerance:
                        screenshot('video', require_coded_size=False)
                        seek_landed_at = position
                        break
                else:
                    raise ValueError('seek did not resume with a decoded frame near its target')
            if verify_subtitle:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    lib.mpv_wait_event(ctx, .02)
                    if expected_bitmap:
                        cue = prop('sub-start')
                        if isinstance(cue, (float, int)) and 0 < cue <= float(seek_position):
                            break
                    elif expected_subtitle in (prop('sub-text') or ''):
                        break
                else:
                    raise ValueError('selected subtitle cue was not decoded at the seek position')
            if expected_bitmap and screenshot('subtitles') == screenshot('video'):
                raise ValueError('the bitmap subtitle did not change the rendered pixels')
            command('set', 'pause', 'no')
            second = finish(require_restart=not verify_subtitle and seek_landed_at is None)
        report = {'decode': 'passed', 'seek': 'passed' if second is not None else 'not-exercised', 'firstEnd': first,
                  'seekEnd': second, 'output': params,
                  'subtitleTextVerified': expected_subtitle is not None,
                  'bitmapSubtitlePixelsVerified': expected_bitmap,
                  'hardwareDecoder': prop('hwdec-current'),
                  'hardwareDecoding': prop('hwdec-current') not in (None, '', 'no')}
        if seek_landed_at is not None:
            report['seekLandedAt'] = seek_landed_at
    finally:
        lib.mpv_terminate_destroy(ctx)
        if dll_directory is not None:
            dll_directory.close()
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
                minimum, maximum = pcm_duration_range
                if not minimum <= seconds <= maximum or not any(payload):
                    raise ValueError(f'incomplete decode/seek PCM output: {seconds}s')
                report['pcmSeconds'] = seconds
        finally:
            output_directory.cleanup()
    return report


def generate(ffmpeg, root, *, expect_dash=False, with_bitmap=False):
    fixtures = []
    for name, encoder, container, pixels, extra in VIDEO:
        path = root / f'{name}.{container}'
        width, height = VIDEO_SIZES.get(name, (128, 96))
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', f'testsrc2=size={width}x{height}:rate=25:duration=2',
                        '-an', '-c:v', encoder, '-threads', '1', '-pix_fmt', pixels,
                        *extra, str(path)], check=True, timeout=90)
        fixtures.append((name, path, 'video'))
    streams = [
        ('m3u8', ('-f', 'hls', '-hls_time', '0.5', '-hls_playlist_type', 'vod', '-hls_segment_type', 'fmp4')),
    ]
    if expect_dash:
        streams.append(('mpd', ('-f', 'dash', '-seg_duration', '0.5')))
    for extension, args in streams:
        directory = root / extension
        directory.mkdir()
        path = directory / f'manifest.{extension}'
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'testsrc2=size=128x96:rate=25:duration=2',
                        '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1',
                        '-g', '12', '-sc_threshold', '0', *args, str(path)], check=True, timeout=30)
        fixtures.append((extension, path, 'video'))
    for name, encoder, container in AUDIO:
        path = root / f'{name}.{container}'
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'sine=frequency=997:sample_rate=48000:duration=2',
                        '-ac', '2', '-strict', 'experimental', '-c:a', encoder, str(path)], check=True, timeout=30)
        fixtures.append((name, path, 'audio'))
        if name in PASSTHROUGH_CODECS:
            fixtures.append((f'passthrough-{name}', path, 'passthrough'))

    captions = root / 'captions.srt'
    captions.write_text('1\n00:00:00,250 --> 00:00:01,250\nPleazyng caption Ω\n', encoding='utf-8')
    for name, video_file, codec, container in (
        ('subrip', 'h264.mkv', 'srt', 'mkv'),
        ('ass', 'h264.mkv', 'ass', 'mkv'),
        ('webvtt', 'vp8.webm', 'webvtt', 'webm'),
    ):
        path = root / f'{name}.{container}'
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(root / video_file),
                        '-i', str(root / 'opus.ogg'), '-i', str(captions), '-map', '0:v:0', '-map', '1:a:0',
                        '-map', '2:s:0', '-c', 'copy', '-c:s', codec, str(path)], check=True, timeout=30)
        fixtures.append((name, path, 'video'))
    if with_bitmap:
        for name, digest in SUBTITLE_SOURCE_HASHES.items():
            with urlopen(f'https://fate-suite.ffmpeg.org/sub/{name}', timeout=45) as response:
                data = response.read(256 * 1024 + 1)
            if len(data) > 256 * 1024 or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'bitmap subtitle fixture hash mismatch: {name}')
            (root / name).write_bytes(data)
        for name, source, offset in BITMAP_SUBTITLES:
            path = root / f'{name}.mkv'
            timestamp_mode = ('-copyts',) if name == 'dvb-bitmap' else ()
            trim = ('-ss', '0') if name == 'dvb-bitmap' else ()
            subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *timestamp_mode,
                            '-i', str(root / 'h264.mkv'), '-itsoffset', offset, '-i', str(root / source),
                            '-map', '0:v:0', '-map', '1:s:0', '-c', 'copy', *trim, '-t', '2', str(path)],
                           check=True, timeout=30)
            fixtures.append((name, path, 'video'))
    return fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expect-dash', action='store_true')
    parser.add_argument('--with-bitmap', action='store_true')
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--kind', choices=['video', 'audio', 'passthrough'])
    args = parser.parse_args()
    if args.worker:
        name = args.worker.stem
        expected_subtitle = 'Pleazyng caption Ω' if name in ('subrip', 'ass', 'webvtt') else None
        expected_pixel_format = next(
            (pixels.removesuffix('le') for case, _, _, pixels, _ in VIDEO
             if case == name and pixels.endswith(('10le', '12le'))),
            None,
        )
        passthrough = args.kind == 'passthrough'
        options = {'untimed': 'yes'} if args.kind != 'audio' else {}
        if passthrough:
            if name not in PASSTHROUGH_CODECS:
                raise ValueError('Unexpected passthrough test codec')
            options['audio-spdif'] = name
        result = execute(
            args.library, args.worker, args.kind, expected_subtitle=expected_subtitle,
            expected_dimensions=VIDEO_SIZES.get(name, (128, 96)),
            expected_pixel_format=expected_pixel_format, expected_bitmap=name in {case[0] for case in BITMAP_SUBTITLES},
            extra_options=options, minimum_position=1.5 if passthrough else None,
        )
        if passthrough:
            expected = f'spdif-{name}'
            if result['output'].get('format') != expected:
                raise ValueError(f'Expected {expected} packetization, got {result["output"]}')
            result['physicalAudioOutputQualified'] = False
        result = json.dumps(result)
        if args.output:
            args.output.write_text(result, encoding='utf-8')
        else:
            print(result)
        return
    results = {}
    with tempfile.TemporaryDirectory(prefix='codec-playback-') as directory:
        root = Path(directory)
        for name, path, kind in generate(args.ffmpeg, root, expect_dash=args.expect_dash, with_bitmap=args.with_bitmap):
            worker_report = root / 'worker.json'
            worker_report.unlink(missing_ok=True)
            try:
                result = subprocess.run([sys.executable, __file__, str(args.library.resolve()),
                                         '--worker', str(path), '--kind', kind, '--output', str(worker_report)],
                                        capture_output=True, text=True, timeout=35)
                results[name] = (json.loads(worker_report.read_text(encoding='utf-8')) if result.returncode == 0 else
                                 {'error': (result.stdout + result.stderr)[-4000:], 'returncode': result.returncode})
            except subprocess.TimeoutExpired:
                results[name] = {'error': 'native worker timed out'}
            results[name]['fixtureSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            if name in {case[0] for case in BITMAP_SUBTITLES}:
                source = next(case[1] for case in BITMAP_SUBTITLES if case[0] == name)
                filenames = (source, 'vobsub.sub') if source == 'vobsub.idx' else (source,)
                results[name]['subtitleSourceSha256'] = {file: SUBTITLE_SOURCE_HASHES[file] for file in filenames}
            if name in ('mpd', 'm3u8'):
                results[name]['segmentsSha256'] = {
                    asset.name: hashlib.sha256(asset.read_bytes()).hexdigest()
                    for asset in sorted(path.parent.iterdir()) if asset != path
                }
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

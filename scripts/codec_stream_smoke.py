#!/usr/bin/env python3
"""Check packaged libmpv's HLS recovery through a local transient HTTP response."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.parse import urlparse

from codec_playback_smoke import execute

RETRY_OPTIONS = {
    'demuxer-lavf-o': 'reconnect=1,reconnect_streamed=1,reconnect_on_network_error=1,seg_max_retry=2',
    'network-timeout': '3',
    'untimed': 'yes',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--worker')
    parser.add_argument('--seek', action='store_true')
    args = parser.parse_args()
    if args.worker:
        report = execute(
            args.library, None, 'video', minimum_position=2.8, seek_position='0.6' if args.seek else None,
            extra_options=RETRY_OPTIONS, source_uri=args.worker,
        )
        args.output.write_text(json.dumps(report), encoding='utf-8')
        return

    with tempfile.TemporaryDirectory(prefix='codec-http-') as directory:
        root = Path(directory)
        manifest = root / 'program.m3u8'
        subprocess.run([
            args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=128x96:rate=25:duration=3',
            '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1',
            '-g', '12', '-sc_threshold', '0', '-hls_time', '0.48', '-hls_playlist_type', 'vod',
            '-hls_segment_type', 'fmp4', '-f', 'hls', str(manifest),
        ], check=True, timeout=30)
        lines = manifest.read_text(encoding='utf-8').splitlines()
        segments = [row for row in lines if row.endswith('.m4s')]
        if len(segments) < 5:
            raise ValueError('HLS fixture does not have enough fragments')
        failed_segment = segments[3]
        # A legal discontinuity marker followed by an unchanged timeline.
        lines.insert(lines.index(failed_segment) - 1, '#EXT-X-DISCONTINUITY')
        manifest.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        requests = Counter()
        failures = Counter()

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *handler_args, **kwargs):
                super().__init__(*handler_args, directory=directory, **kwargs)

            def do_GET(self):
                name = urlparse(self.path).path.removeprefix('/')
                requests[name] += 1
                if name == failed_segment and not failures[name]:
                    failures[name] += 1
                    self.send_response(503)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                super().do_GET()

            def log_message(self, *_):
                pass

        worker_report = root / 'worker.json'
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}/{manifest.name}'
                command = [
                    sys.executable, __file__, str(args.library.resolve()), '--worker', url,
                    '--output', str(worker_report),
                ]
                def run_worker(*flags):
                    process = subprocess.run([*command, *flags], capture_output=True, text=True, timeout=35)
                    if process.returncode:
                        raise RuntimeError((process.stdout + process.stderr)[-4000:])
                    return json.loads(worker_report.read_text(encoding='utf-8'))

                initial = run_worker()
                initial_attempts = requests[failed_segment]
                if failures[failed_segment] != 1 or initial_attempts < 2:
                    raise ValueError('Initial playback did not retry the fragment that returned HTTP 503')
                result = run_worker('--seek')
            finally:
                server.shutdown()
                thread.join()
        asset_hashes = {
            file.name: hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(root.iterdir()) if file != worker_report
        }
    with args.library.open('rb') as stream:
        binary_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {
        'schemaVersion': 1,
        'evidence': 'hls-vod-transient-segment-recovery',
        'binarySha256': binary_digest,
        'fixtureSha256': asset_hashes,
        'failedSegment': failed_segment,
        'initialAttemptsForFailedSegment': initial_attempts,
        'initialPlayback': initial,
        'playback': result,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('HLS playback recovered from a transient segment 503 and completed seeking')


if __name__ == '__main__':
    main()

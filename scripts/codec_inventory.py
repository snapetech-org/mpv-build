#!/usr/bin/env python3
"""Enumerate the exact loaded libmpv, without opening media or output devices.

Run on the matching native build host. The manifest is compiled availability,
not a claim of real-time playback or HDR/audio-output qualification.
"""
from __future__ import annotations

import argparse
import ctypes as c
import hashlib
import json
import os
import platform
import sys
from pathlib import Path


class Node(c.Structure):
    pass


class NodeList(c.Structure):
    _fields_ = [('num', c.c_int), ('values', c.POINTER(Node)), ('keys', c.POINTER(c.c_char_p))]


class NodeValue(c.Union):
    _fields_ = [('string', c.c_char_p), ('flag', c.c_int), ('int64', c.c_int64),
                ('double', c.c_double), ('list', c.POINTER(NodeList)), ('pointer', c.c_void_p)]


Node._fields_ = [('u', NodeValue), ('format', c.c_int)]


def decode_node(node, depth=0):
    if depth > 8:
        raise ValueError('native inventory exceeds depth limit')
    if node.format == 0:
        return None
    if node.format == 1:
        return node.u.string.decode('utf-8') if node.u.string else ''
    if node.format == 3:
        return bool(node.u.flag)
    if node.format == 4:
        return node.u.int64
    if node.format == 5:
        return node.u.double
    if node.format not in (7, 8) or not node.u.list:
        raise ValueError('unexpected native inventory node')
    items = node.u.list.contents
    if not 0 <= items.num <= 16384 or (items.num and not items.values):
        raise ValueError('invalid native inventory size')
    values = [decode_node(items.values[i], depth + 1) for i in range(items.num)]
    if node.format == 7:
        return values
    if not items.keys:
        raise ValueError('native inventory map has no keys')
    keys = [items.keys[i].decode('utf-8') for i in range(items.num)]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate native inventory key')
    return dict(zip(keys, values))


def validate_inventory(properties, required=(), required_protocols=()):
    decoders = properties.get('decoder-list')
    if not isinstance(decoders, list) or not decoders:
        raise ValueError('loaded engine reported no decoders')
    by_codec = {}
    for entry in decoders:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) and entry[key]
                                                   for key in ('codec', 'driver')):
            raise ValueError('invalid decoder entry')
        by_codec.setdefault(entry['codec'], set()).add(entry['driver'])
    missing = set(required) - set(by_codec)
    if missing:
        raise ValueError('loaded engine omits required decoders: ' + ', '.join(sorted(missing)))
    if 'av1' in required and not ({'libdav1d', 'libaom-av1', 'libaom_av1'} & by_codec.get('av1', set())):
        raise ValueError('AV1 requires a software fallback, not only a compiled hardware wrapper')
    for key in ('demuxer-lavf-list', 'protocol-list'):
        if not isinstance(properties.get(key), list) or not properties[key] or not all(isinstance(x, str) for x in properties[key]):
            raise ValueError('missing native ' + key)
    missing_protocols = set(required_protocols) - set(properties['protocol-list'])
    if missing_protocols:
        raise ValueError('loaded engine omits required protocols: ' + ', '.join(sorted(missing_protocols)))
    return {codec: sorted(drivers) for codec, drivers in sorted(by_codec.items())}


def inspect(library, required=(), required_protocols=()):
    path = Path(library).resolve(strict=True)
    if sys.platform == 'win32':
        with os.add_dll_directory(str(path.parent)):
            lib = c.CDLL(str(path))
    else:
        lib = c.CDLL(str(path))
    lib.mpv_create.restype = c.c_void_p
    lib.mpv_set_option_string.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
    lib.mpv_set_option_string.restype = c.c_int
    lib.mpv_initialize.argtypes = [c.c_void_p]
    lib.mpv_initialize.restype = c.c_int
    lib.mpv_get_property.argtypes = [c.c_void_p, c.c_char_p, c.c_int, c.c_void_p]
    lib.mpv_get_property.restype = c.c_int
    lib.mpv_free_node_contents.argtypes = [c.POINTER(Node)]
    lib.mpv_free_node_contents.restype = None
    lib.mpv_terminate_destroy.argtypes = [c.c_void_p]
    lib.mpv_terminate_destroy.restype = None
    ctx = lib.mpv_create()
    if not ctx:
        raise ValueError('mpv_create failed')
    try:
        for key, value in {'config': 'no', 'terminal': 'no', 'vo': 'null', 'ao': 'null',
                           'idle': 'yes', 'ytdl': 'no', 'load-scripts': 'no'}.items():
            if lib.mpv_set_option_string(ctx, key.encode(), value.encode()) < 0:
                raise ValueError('native option rejected: ' + key)
        if lib.mpv_initialize(ctx) < 0:
            raise ValueError('mpv_initialize failed')
        properties = {}
        for key in ('decoder-list', 'demuxer-lavf-list', 'protocol-list', 'mpv-version', 'ffmpeg-version'):
            node = Node()
            if lib.mpv_get_property(ctx, key.encode(), 6, c.byref(node)) < 0:
                raise ValueError('native inventory unavailable: ' + key)
            try:
                properties[key] = decode_node(node)
            finally:
                lib.mpv_free_node_contents(c.byref(node))
        codecs = validate_inventory(properties, required, required_protocols)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return {'schemaVersion': 1, 'evidence': 'runtime-enumeration', 'executionQualified': False,
                'binarySha256': digest,
                'architecture': platform.machine(), 'platform': platform.system().lower(),
                'decoders': codecs, 'properties': properties}
    finally:
        lib.mpv_terminate_destroy(ctx)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require', action='append', default=[])
    parser.add_argument('--require-protocol', action='append', default=[])
    args = parser.parse_args()
    result = json.dumps(inspect(args.library, args.require, args.require_protocol), indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end='')


if __name__ == '__main__':
    main()

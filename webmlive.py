"""
Copyright (C) 2026 ReviveMii Project & TheErrorExe, All rights reserved.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import io
import struct

ID_EBML = bytes.fromhex("1A45DFA3")
ID_INFO = bytes.fromhex("1549A966")
ID_SEEKHEAD = bytes.fromhex("114D9B74")
ID_CLUSTER = bytes.fromhex("1F43B675")
ID_DURATION = bytes.fromhex("4489")
ID_TRACKS = bytes.fromhex("1654AE6B")
ID_TRACKENTRY = b"\xAE"
ID_VIDEO = b"\xE0"
_DROP_IN_TRACKENTRY = {bytes.fromhex("56AA"), bytes.fromhex("56BB")}
_DROP_IN_VIDEO = {bytes.fromhex("55B0"), bytes.fromhex("54B0"), bytes.fromhex("54BA"),
                  bytes.fromhex("54B2"), bytes.fromhex("54B3")}
ID_TIMECODE = b"\xE7"
ID_CLUSTER_POSITION = b"\xA7"
ID_PREV_SIZE = b"\xAB"
ID_BLOCKGROUP = b"\xA0"
ID_BLOCK = b"\xA1"
ID_REFERENCE_BLOCK = b"\xFB"


def read_exact(f, n):
    buf = b""
    while len(buf) < n:
        d = f.read(n - len(buf))
        if not d:
            raise EOFError("stream ended")
        buf += d
    return buf


def read_id(f):
    b0 = read_exact(f, 1)
    n, mask = 1, 0x80
    while n <= 4 and not (b0[0] & mask):
        n += 1
        mask >>= 1
    return b0 + read_exact(f, n - 1)


def read_size(f):
    b0 = read_exact(f, 1)
    n, mask = 1, 0x80
    while n <= 8 and not (b0[0] & mask):
        n += 1
        mask >>= 1
    rest = read_exact(f, n - 1)
    val = b0[0] & (mask - 1)
    for x in rest:
        val = (val << 8) | x
    if val == (1 << (7 * n)) - 1:
        return b0 + rest, None
    return b0 + rest, val


def size_min(v):
    n = 1
    while v >= (1 << (7 * n)) - 1:
        n += 1
    return ((1 << (7 * n)) | v).to_bytes(n, "big")


def uint_min(v):
    v = max(int(v), 0)
    return v.to_bytes(max((v.bit_length() + 7) // 8, 1), "big")


def size8(v):
    return bytes([0x01]) + v.to_bytes(7, "big")


def _filter_children(data, drop):
    f = io.BytesIO(data)
    out = []
    while f.tell() < len(data):
        cid = read_id(f)
        raw, sz = read_size(f)
        body = read_exact(f, sz)
        if cid not in drop:
            out.append((cid, raw, body))
    return out


def clean_tracks(data):
    out = b""
    for cid, raw, body in _filter_children(data, set()):
        if cid == ID_TRACKENTRY:
            entry = b""
            for c2, r2, b2 in _filter_children(body, _DROP_IN_TRACKENTRY):
                if c2 == ID_VIDEO:
                    b2 = b"".join(c3 + r3 + b3 for c3, r3, b3 in _filter_children(b2, _DROP_IN_VIDEO))
                    r2 = size_min(len(b2))
                entry += c2 + r2 + b2
            body = entry
            raw = size_min(len(body))
        out += cid + raw + body
    return out


def read_header(src, total_length, duration_s):
    eid = read_id(src)
    esz_raw, esz = read_size(src)
    ebml = eid + esz_raw + read_exact(src, esz)

    sid = read_id(src)
    read_size(src)
    seg_size = max(total_length - len(ebml) - len(sid) - 8, 1)
    out = ebml + sid + size8(seg_size)

    while True:
        cid = read_id(src)
        csz_raw, csz = read_size(src)
        if cid == ID_CLUSTER:
            if csz is None:
                raise ValueError("live cluster has unknown size; cannot split")
            return out, cid, csz
        data = read_exact(src, csz)
        if cid == ID_INFO:
            data += ID_DURATION + b"\x88" + struct.pack(">d", duration_s * 1000.0)
            out += cid + size8(len(data)) + data
        elif cid == ID_TRACKS:
            data = clean_tracks(data)
            out += cid + size8(len(data)) + data
        elif cid == ID_SEEKHEAD:
            fill = len(cid) + len(csz_raw) + len(data) - 9
            out += b"\xEC" + size8(fill) + b"\x00" * fill
        else:
            out += cid + csz_raw + data


def iter_clusters(src, first_size):
    size = first_size
    while True:
        yield read_exact(src, size)
        while True:
            try:
                cid = read_id(src)
                _, size = read_size(src)
            except EOFError:
                return
            if size is None:
                if cid == ID_CLUSTER:
                    raise ValueError("live cluster has unknown size; cannot split")
                return
            if cid == ID_CLUSTER:
                break
            try:
                read_exact(src, size)
            except EOFError:
                return


VIDEO_TRACK = 1


def _block_info(cid, data):
    if cid != b"\xA3" or not data:
        return None, False
    b0 = data[0]
    n, mask = 1, 0x80
    while n <= 8 and not (b0 & mask):
        n += 1
        mask >>= 1
    track = b0 & (mask - 1)
    for x in data[1:n]:
        track = (track << 8) | x
    flags = data[n + 2] if len(data) > n + 2 else 0
    return track, bool(flags & 0x80)


def _blockgroup_to_simple(group, cid, raw):
    g = io.BytesIO(group)
    block = None
    has_ref = False
    while g.tell() < len(group):
        c = read_id(g)
        _, sz = read_size(g)
        d = read_exact(g, sz)
        if c == ID_BLOCK:
            block = d
        elif c == ID_REFERENCE_BLOCK:
            has_ref = True
    if block is None:
        return cid, raw, group
    b0 = block[0]
    n, mask = 1, 0x80
    while n <= 8 and not (b0 & mask):
        n += 1
        mask >>= 1
    if len(block) <= n + 2:
        return cid, raw, group
    flags = block[n + 2] & 0x0F
    if not has_ref:
        flags |= 0x80
    block = block[:n + 2] + bytes([flags]) + block[n + 3:]
    return b"\xA3", size_min(len(block)), block


def split_cluster(payload):
    f = io.BytesIO(payload)
    tc = 0
    elements = []
    key_index = None
    while f.tell() < len(payload):
        cid = read_id(f)
        raw, sz = read_size(f)
        data = read_exact(f, sz)
        if cid == ID_TIMECODE:
            tc = int.from_bytes(data, "big")
        elif cid in (ID_CLUSTER_POSITION, ID_PREV_SIZE):
            continue
        else:
            if cid == ID_BLOCKGROUP:
                cid, raw, data = _blockgroup_to_simple(data, cid, raw)
            track, is_key = _block_info(cid, data)
            is_video = track == VIDEO_TRACK
            if is_video and is_key and key_index is None:
                key_index = len(elements)
            elements.append((cid + raw + data, is_video))
    return tc, elements, key_index


def children_bytes(elements, key_index=None):
    if key_index is None:
        return b"".join(e for e, _ in elements)
    return b"".join(e for i, (e, is_video) in enumerate(elements) if not (is_video and i < key_index))


def build_cluster(timecode, children):
    tcb = uint_min(timecode)
    body = ID_TIMECODE + size_min(len(tcb)) + tcb + children
    return ID_CLUSTER + size_min(len(body)) + body

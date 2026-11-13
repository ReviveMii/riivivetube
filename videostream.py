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


import os
import subprocess
import threading
import time

from flask import Response, stream_with_context

import livestream
import webmlive

VIDEO_FORMAT = "18/best[height<=480]/bv*[height<=480]+ba/best"
VIDEO_LEAD_SECONDS = 12
VIDEO_STRIP_ARGS = ["-map_metadata", "-1", "-map_metadata:s:v", "-1", "-map_metadata:s:a", "-1",
                    "-map_chapters", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact"]
VIDEO_BYTES_PER_SECOND = 185_000

STREAM_VIDEOS = os.environ.get("STREAM_VIDEOS", "1") != "0"
MAX_VIDEO_STREAMS = int(os.environ.get("MAX_VIDEO_STREAMS", "4"))
_video_slots = threading.BoundedSemaphore(MAX_VIDEO_STREAMS)
_video_urls = {}
_video_urls_lock = threading.Lock()


def _resolve(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    base = livestream._ytdlp_cmd() + [url, "-g", "--no-playlist", "-f", VIDEO_FORMAT]
    attempts = []
    if os.path.exists("cookies.txt"):
        attempts.append(base + ["--extractor-args", "youtube:player_client=mweb,tv_simply,web,web_embedded",
                                "--cookies", "cookies.txt"])
    attempts.append(base + ["--extractor-args", "youtube:player_client=android"])
    attempts.append(base)

    last_err = ""
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:
            last_err = str(e)
            continue
        urls = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("http")]
        if r.returncode == 0 and urls:
            return urls[:2]
        last_err = (r.stderr or "")[-400:]
    raise RuntimeError(f"yt-dlp could not get the video URL: {last_err.strip()}")


def prepare_video(video_id):
    if not livestream._VIDEO_ID_RE.match(video_id or ""):
        return "invalid video id"
    try:
        urls = _resolve(video_id)
    except Exception as e:
        return str(e)
    with _video_urls_lock:
        now = time.time()
        for k in [k for k, v in _video_urls.items() if now - v[0] > 3600]:
            del _video_urls[k]
        _video_urls[video_id] = (now, urls)
    return None


def has_video_urls(video_id):
    with _video_urls_lock:
        return video_id in _video_urls


def _void(n):
    if n - 2 < 127:
        return b"\xEC" + bytes([0x80 | (n - 2)]) + b"\x00" * (n - 2)
    return b"\xEC" + webmlive.size8(n - 9) + b"\x00" * (n - 9)


def stream_video(video_id, duration):
    with _video_urls_lock:
        entry = _video_urls.get(video_id)
    if entry is None:
        return Response("Video not prepared, call get_video_info first", status=404, mimetype="text/plain")
    if not _video_slots.acquire(blocking=False):
        return Response("too many videos are being converted right now", status=503, mimetype="text/plain")
    proc = None
    try:
        cmd = livestream._build_cmd("ffmpeg", video_id, entry[1])
        i = cmd.index("-f")
        cmd[i:i] = VIDEO_STRIP_ARGS
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        src = proc.stdout
        total = max(int(duration * VIDEO_BYTES_PER_SECOND), 1_000_000)
        header, _cid, first_size = webmlive.read_header(src, total, duration)
    except Exception as e:
        if proc and proc.poll() is None:
            proc.kill()
        _video_slots.release()
        return Response(f"{type(e).__name__}: {e}", status=502, mimetype="text/plain")

    def gen():
        t0, sent, base, done = time.time(), len(header), None, False
        try:
            yield header
            for payload in webmlive.iter_clusters(src, first_size):
                tc, elements, _key = webmlive.split_cluster(payload)
                if base is None:
                    base = tc
                ahead = (tc - base) / 1000.0 - VIDEO_LEAD_SECONDS - (time.time() - t0)
                if ahead > 0:
                    time.sleep(ahead)
                out = webmlive.build_cluster(tc - base, webmlive.children_bytes(elements))
                if sent + len(out) > total:
                    break
                sent += len(out)
                yield out
            else:
                done = True
            pad = total - sent
            while done and pad > 0:
                take = min(pad, 65536)
                if pad - take == 1:
                    take -= 1
                if take < 2:
                    break
                yield _void(take)
                pad -= take
        finally:
            if proc.poll() is None:
                proc.kill()
            _video_slots.release()

    return Response(
        stream_with_context(gen()),
        mimetype="video/webm",
        headers={"Cache-Control": "no-cache, no-store", "Accept-Ranges": "none",
                 "Content-Length": str(total), "Connection": "close"},
    )

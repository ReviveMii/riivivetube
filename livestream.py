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
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

from flask import Response

import webmlive

LIVE_DURATION = 3 * 3600
LIVE_LENGTH_BYTES = 2_000_000_000
IDLE_SECONDS = 30
START_TIMEOUT = 75
MAX_SESSIONS = int(os.environ.get("MAX_LIVE_STREAMS", "4"))
SUB_QUEUE_MAX = 40

_HERE = os.path.dirname(os.path.abspath(__file__))


_live_ids = {}
_live_ids_lock = threading.Lock()


def mark_live(video_id):
    with _live_ids_lock:
        _live_ids[video_id] = time.time()


_started = {}
_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400,
                 "week": 604800, "month": 2592000, "year": 31536000}


def remember_start(video_id, text):
    m = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s+ago", text or "")
    if m:
        _started[video_id] = time.time() - int(m.group(1)) * _UNIT_SECONDS[m.group(2)]


def ensure_starts(ids, timeout=6):
    import youtubei
    from concurrent.futures import ThreadPoolExecutor, wait
    todo = [i for i in ids if i and i not in _started]
    if not todo:
        return
    def one(i):
        try:
            import requests
            from youtubei.client import _get_base_headers, _build_context
            r = requests.post("https://www.youtube.com/youtubei/v1/next",
                              json={"context": _build_context(video_id=i), "videoId": i},
                              headers=_get_base_headers(), timeout=10)
            for c in r.json()["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"]:
                if "videoPrimaryInfoRenderer" in c:
                    remember_start(i, c["videoPrimaryInfoRenderer"]["dateText"]["simpleText"])
        except Exception:
            pass
    ex = ThreadPoolExecutor(max_workers=8)
    wait([ex.submit(one, i) for i in todo], timeout=timeout)
    ex.shutdown(wait=False)


def started_text(video_id):
    t = _started.get(video_id)
    if t is None:
        return "Streaming live now"
    age = max(int(time.time() - t), 0)
    for unit in ("year", "month", "week", "day", "hour", "minute"):
        n = age // _UNIT_SECONDS[unit]
        if n >= 1:
            return f"Started streaming {n} {unit}{'' if n == 1 else 's'} ago"
    return "Started streaming just now"


def is_live_id(video_id):
    with _live_ids_lock:
        return video_id in _live_ids


def _ytdlp_cmd():
    return ["yt-dlp"]


def resolve_source_urls(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    base = _ytdlp_cmd() + [url, "-g", "--no-playlist",
                           "-f", "best[height<=480]/bv*[height<=480]+ba/best"]
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
    raise RuntimeError(f"yt-dlp could not get a live URL: {last_err.strip()}")


_OUT_ARGS = [
    "-c:v", "libvpx", "-deadline", "realtime", "-cpu-used", "16",
    "-lag-in-frames", "0", "-auto-alt-ref", "0",
    "-force_key_frames", "expr:gte(t,n_forced*2)",
    "-b:v", "1M", "-crf", "20", "-pix_fmt", "yuv420p",
    "-c:a", "libvorbis", "-b:a", "128k", "-ac", "2", "-ar", "44100",
    "-f", "webm", "-live", "1", "-cluster_time_limit", "1500", "pipe:1",
]


def _build_cmd(exe, video_id, urls):
    cmd = [exe, "-v", "error", "-nostdin"]
    net = ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5"]
    vf = ["-vf", "fps=30,scale=-2:'min(360,ih)':flags=fast_bilinear",
          "-af", "aresample=async=1"]
    if len(urls) == 1:
        cmd += net + ["-i", urls[0], "-map", "0:v:0", "-map", "0:a:0?"]
    else:
        cmd += net + ["-i", urls[0]] + net + ["-i", urls[1], "-map", "0:v:0", "-map", "1:a:0"]
    return cmd + vf + _OUT_ARGS


class Subscriber:
    def __init__(self):
        self.q = queue.Queue(maxsize=SUB_QUEUE_MAX)
        self.base_tc = None
        self.dead = False


class LiveSession:
    def __init__(self, video_id):
        self.video_id = video_id
        self.lock = threading.Lock()
        self.subs = []
        self.header = None
        self.gop = []
        self.error = None
        self.ready = threading.Event()
        self.stopped = threading.Event()
        self.proc = None
        self.ready_time = None
        self.last_empty = None
        threading.Thread(target=self._run, daemon=True, name=f"live-{video_id}").start()
        threading.Thread(target=self._watchdog, daemon=True, name=f"livewd-{video_id}").start()

    def subscribe(self):
        sub = Subscriber()
        with self.lock:
            if self.header is not None:
                sub.q.put_nowait(self.header)
                if self.gop:
                    tc0, el0, key0 = self.gop[0]
                    sub.base_tc = tc0
                    sub.q.put_nowait(webmlive.build_cluster(0, webmlive.children_bytes(el0, key0)))
                    for tc, el, _k in self.gop[1:]:
                        sub.q.put_nowait(webmlive.build_cluster(tc - tc0, webmlive.children_bytes(el)))
            self.subs.append(sub)
            self.last_empty = None
        return sub

    def unsubscribe(self, sub):
        with self.lock:
            if sub in self.subs:
                self.subs.remove(sub)
            if not self.subs:
                self.last_empty = time.time()

    def _broadcast_cluster(self, payload):
        tc, elements, key_index = webmlive.split_cluster(payload)
        full = webmlive.children_bytes(elements)
        cut = None
        with self.lock:
            for s in list(self.subs):
                if s.base_tc is None:
                    if key_index is None:
                        continue
                    s.base_tc = tc
                    if cut is None:
                        cut = webmlive.children_bytes(elements, key_index)
                    out = webmlive.build_cluster(0, cut)
                else:
                    out = webmlive.build_cluster(tc - s.base_tc, full)
                try:
                    s.q.put_nowait(out)
                except queue.Full:
                    s.dead = True
                    self.subs.remove(s)
                    try:
                        s.q.get_nowait()
                        s.q.put_nowait(None)
                    except Exception:
                        pass
            if key_index is not None:
                self.gop = [(tc, elements, key_index)]
            elif self.gop:
                self.gop.append((tc, elements, key_index))

    def _run(self):
        try:
            exe = "ffmpeg"
            urls = resolve_source_urls(self.video_id)
            if self.stopped.is_set():
                return
            cmd = _build_cmd(exe, self.video_id, urls)
            log_path = os.path.join(_HERE, "livestream_ffmpeg.log")
            try:
                if os.path.getsize(log_path) > 1_000_000:
                    os.remove(log_path)
            except OSError:
                pass
            log = open(log_path, "ab")
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log)
            src = self.proc.stdout

            header, _cid, first_size = webmlive.read_header(src, LIVE_LENGTH_BYTES, LIVE_DURATION)
            with self.lock:
                self.header = header
                self.ready_time = time.time()
                for s in self.subs:
                    s.q.put_nowait(header)
            self.ready.set()

            for payload in webmlive.iter_clusters(src, first_size):
                if self.stopped.is_set():
                    break
                self._broadcast_cluster(payload)
        except Exception as e:
            if not self.stopped.is_set():
                self.error = f"{type(e).__name__}: {e}"
        finally:
            self.ready.set()
            self._finish()

    def _finish(self):
        self.stopped.set()
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
        with self.lock:
            for s in self.subs:
                try:
                    s.q.put_nowait(None)
                except queue.Full:
                    pass
        with _sessions_lock:
            if _sessions.get(self.video_id) is self:
                del _sessions[self.video_id]

    def _watchdog(self):
        started = time.time()
        while not self.stopped.is_set():
            time.sleep(2)
            with self.lock:
                idle_since = self.last_empty
                n = len(self.subs)
                ready_time = self.ready_time
            ref = idle_since if idle_since else (ready_time if ready_time else started + 120)
            if n == 0 and ref and time.time() - ref > IDLE_SECONDS:
                self.stop()
                return

    def stop(self):
        self.stopped.set()
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass


_sessions = {}
_sessions_lock = threading.Lock()


_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def get_session(video_id):
    if not _VIDEO_ID_RE.match(video_id or ""):
        return None
    with _sessions_lock:
        s = _sessions.get(video_id)
        if s is None or s.stopped.is_set():
            if sum(1 for x in _sessions.values() if not x.stopped.is_set()) >= MAX_SESSIONS:
                return None
            s = LiveSession(video_id)
            _sessions[video_id] = s
        return s


def prepare(video_id, timeout=START_TIMEOUT):
    s = get_session(video_id)
    if s is None:
        return "too many livestreams are running right now"
    if not s.ready.wait(timeout):
        return "timed out waiting for the livestream to start"
    return s.error


def stream_response(video_id):
    s = get_session(video_id)
    if s is None:
        return Response("too many livestreams are running right now", status=503, mimetype="text/plain")
    if not s.ready.wait(START_TIMEOUT):
        return Response("livestream did not start in time", status=504, mimetype="text/plain")
    if s.error:
        return Response(s.error, status=502, mimetype="text/plain")
    sub = s.subscribe()

    def gen():
        t0 = time.time()
        first = True
        try:
            while True:
                try:
                    item = sub.q.get(timeout=45)
                except queue.Empty:
                    break
                if item is None:
                    break
                if first and len(item) > 0 and item[:4] != webmlive.ID_EBML:
                    first = False
                yield item
        finally:
            s.unsubscribe(sub)

    from flask import stream_with_context
    return Response(
        stream_with_context(gen()),
        mimetype="video/webm",
        headers={"Cache-Control": "no-cache, no-store", "Accept-Ranges": "none",
                 "Content-Length": str(LIVE_LENGTH_BYTES), "Connection": "close"},
    )

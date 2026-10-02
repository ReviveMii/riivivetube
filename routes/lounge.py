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

import atexit
import logging
import threading
import time
import requests
from flask import Blueprint, Response, request

from extensions import limiter

log = logging.getLogger("lounge")

bp = Blueprint("lounge", __name__, url_prefix="/api/lounge")

YT_LOUNGE = "https://www.youtube.com/api/lounge"
USER_AGENT = (
    "Mozilla/5.0 (PS4; Leanback Shell) Gecko/20100101 "
    "LeanbackShell/01.00.01.75 Sony PS4/ (PS4, , no, CH)"
)
IDLE_TIMEOUT = 120 
BIND_DEFAULTS = {
    "VER": "8",
    "CVER": "1",
    "device": "LOUNGE_SCREEN",
    "app": "lb-v4",
    "theme": "cl",
    "capabilities": "dsp",
    "mdxVersion": "2",
}
IDENTITY_KEYS = ("gsessionid", "loungeIdToken", "id", "device", "name", "app", "v")

http = requests.Session()
http.headers["User-Agent"] = USER_AGENT

_screen_for_token = {} 
_device_for_token = {} 
_sessions = {} 
_lock = threading.Lock()
_reaper_started = False
MAX_TOKENS = 500 


def _remember(mapping, key, value):
    with _lock:
        mapping.pop(key, None)
        mapping[key] = value
        while len(mapping) > MAX_TOKENS:
            mapping.pop(next(iter(mapping)))


def _text(body, status=200):
    return Response(body, status=status, mimetype="text/plain")


def _fail(what, resp=None, exc=None):
    if resp is not None:
        log.warning("lounge %s failed: HTTP %s %r", what, resp.status_code, resp.text[:300])
    else:
        log.warning("lounge %s failed: %r", what, exc)
    return _text("", 502)


def _terminate(sid, session, timeout=5):
    query = dict(session["ident"])
    query.update(VER="8", CVER="1", TYPE="terminate", SID=sid, RID=str(session["rid"] + 1))
    try:
        http.post(f"{YT_LOUNGE}/bc/bind", params=query, timeout=timeout)
    except requests.RequestException as e:
        log.warning("lounge terminate failed: %r", e)


def _reap_once():
    cutoff = time.time() - IDLE_TIMEOUT
    with _lock:
        stale = [sid for sid, s in _sessions.items() if s["seen"] < cutoff]
        stale = [(sid, _sessions.pop(sid)) for sid in stale]
    for sid, session in stale:
        _terminate(sid, session)


def _reap_loop():
    while True:
        time.sleep(15)
        _reap_once()


def _start_reaper():
    global _reaper_started
    with _lock:
        if _reaper_started:
            return
        _reaper_started = True
    threading.Thread(target=_reap_loop, daemon=True).start()


@atexit.register
def _terminate_all():
    with _lock:
        items = list(_sessions.items())
        _sessions.clear()
    for sid, session in items:
        _terminate(sid, session, timeout=3)


def _track(params):
    sid = params.get("SID")
    if not sid:
        return
    if params.get("TYPE") == "terminate":
        with _lock:
            _sessions.pop(sid, None)
        return
    with _lock:
        session = _sessions.setdefault(sid, {"ident": {}, "rid": 0, "seen": 0})
        session["ident"].update({k: params[k] for k in IDENTITY_KEYS if k in params})
        session["seen"] = time.time()
        if params.get("RID", "").isdigit():
            session["rid"] = max(session["rid"], int(params["RID"]))
    _start_reaper()


@bp.route("/pairing/generate_screen_id", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def generate_screen_id():
    try:
        r = http.post(f"{YT_LOUNGE}/pairing/generate_screen_id", timeout=15)
    except requests.RequestException as e:
        return _fail("generate_screen_id", exc=e)
    if r.status_code != 200 or not r.text.strip():
        return _fail("generate_screen_id", resp=r)
    return _text(r.text.strip())


@bp.route("/pairing/get_lounge_token", methods=["GET", "POST"])
@limiter.limit("30 per hour")
def get_lounge_token():
    screen_id = request.values.get("screen_id", "")
    if not screen_id:
        return _text("", 400)
    try:
        r = http.post(f"{YT_LOUNGE}/pairing/get_lounge_token_batch",
                      data={"screen_ids": screen_id}, timeout=15)
        token = r.json()["screens"][0]["loungeToken"]
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        return _fail("get_lounge_token", exc=e)
    _remember(_screen_for_token, token, screen_id)
    return _text(token)


@bp.route("/pairing/get_pairing_code", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def get_pairing_code():
    token = request.values.get("lounge_token", "")
    if not token:
        return _text("", 400)
    data = {
        "access_type": request.values.get("access_type", "permanent"),
        "app": BIND_DEFAULTS["app"],
        "lounge_token": token,
        "device_id": _device_for_token.get(token, "flashlite"),
    }
    screen_name = request.values.get("screen_name")
    if screen_name:
        data["screen_name"] = screen_name
    if token in _screen_for_token:
        data["screen_id"] = _screen_for_token[token]
    try:
        r = http.post(f"{YT_LOUNGE}/pairing/get_pairing_code",
                      params={"ctx": "pair"}, data=data, timeout=15)
    except requests.RequestException as e:
        return _fail("get_pairing_code", exc=e)
    code = r.text.strip()
    if r.status_code != 200 or not code.isdigit():
        return _fail("get_pairing_code", resp=r)
    return _text(code)


@bp.route("/bc/bind", methods=["GET", "POST"])
@limiter.exempt
def bind():
    params = request.args.to_dict()
    for key, value in BIND_DEFAULTS.items():
        params.setdefault(key, value)
    if params.get("loungeIdToken"):
        _remember(_device_for_token, params["loungeIdToken"], params.get("id", "flashlite"))
    _track(params)
    try:
        r = http.request(
            request.method, f"{YT_LOUNGE}/bc/bind",
            params=params,
            data=request.get_data() if request.method == "POST" else None,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=(10, 60), 
        )
    except requests.Timeout:
        return Response("", status=504)
    except requests.RequestException as e:
        return _fail("bind", exc=e)
    return Response(r.content, status=r.status_code,
                    content_type=r.headers.get("Content-Type", "text/plain"))

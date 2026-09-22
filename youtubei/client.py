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


import requests
import re
import json
import time
import threading

_client_version = None
_client_version_lock = threading.Lock()
_client_version_last_fetch = 0
_CLIENT_VERSION_TTL = 3600

def _fetch_client_version():
    global _client_version, _client_version_last_fetch
    with _client_version_lock:
        now = time.time()
        if _client_version and (now - _client_version_last_fetch) < _CLIENT_VERSION_TTL:
            return _client_version

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.5",
            }
            resp = requests.get("https://www.youtube.com", headers=headers, timeout=10)
            resp.raise_for_status()

            match = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', resp.text)
            if match:
                _client_version = match.group(1)
                _client_version_last_fetch = now
                return _client_version
        except Exception as e:
            print(f"[youtubei] Error fetching client version: {e}")
        _client_version = "2.20260918.00.00"
        _client_version_last_fetch = now
        return _client_version

# ported from https://github.com/erievs/FourthTube/blob/9f871f95f9fce14f3c109f0a403bb8b5224bc6c7/source/youtube_parser/video.cpp#L486-L517
def _fetch_visitor_data():
    try:
        headers = {
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        }
        resp = requests.get("https://www.youtube.com/sw.js_data", headers=headers, timeout=10)
        resp.raise_for_status()

        text = resp.text
        prefix = ")]}'\n"
        if text.startswith(prefix):
            text = text[len(prefix):]

        data = json.loads(text)
        visitor_data = data[0][2][0][0][13]
        return visitor_data
    except Exception as e:
        print(f"[youtubei] Error fetching visitor data: {e}")
        return "0"

def _get_base_headers():
    client_version = _fetch_client_version()
    visitor_data = _fetch_visitor_data()

    return {
        "Host": "www.youtube.com",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Priority": "u=1, i",
        "Referer": "https://www.youtube.com/",
        "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "Sec-Ch-Ua-Arch": '"x86"',
        "Sec-Ch-Ua-Bitness": '"64"',
        "Sec-Ch-Ua-Full-Version-List": '"Not;A=Brand";v="8.0.0.0", "Chromium";v="150.0.0.0", "Google Chrome";v="150.0.0.0"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Model": '""',
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Ch-Ua-Platform-Version": '""',
        "Sec-Ch-Ua-Wow64": "?0",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "same-origin",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Gpc": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        "X-Goog-Authuser": "1",
        "X-Goog-Visitor-Id": visitor_data,
        "X-Origin": "https://www.youtube.com",
        "X-Youtube-Bootstrap-Logged-In": "true",
        "X-Youtube-Client-Name": "1",
        "X-Youtube-Client-Version": client_version,
    }

def _build_context(video_id=None, graft_url=None):
    client_version = _fetch_client_version()
    visitor_data = _fetch_visitor_data()

    original_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else "https://www.youtube.com/"
    _graft_url = graft_url if graft_url else (f"/watch?v={video_id}" if video_id else "/")

    return {
        "client": {
            "acceptHeader": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "browserName": "Chrome",
            "browserVersion": "150.0.0.0",
            "clientFormFactor": "UNKNOWN_FORM_FACTOR",
            "clientName": "WEB",
            "clientVersion": client_version,
            "configInfo": {
                "appInstallData": ""
            },
            "deviceMake": "",
            "deviceModel": "",
            "gl": "US",
            "hl": "en",
            "mainAppWebInfo": {
                "graftUrl": _graft_url,
                "isWebNativeShareAvailable": True,
                "pwaInstallabilityStatus": "PWA_INSTALLABILITY_STATUS_CAN_BE_INSTALLED",
                "webDisplayMode": "WEB_DISPLAY_MODE_BROWSER"
            },
            "memoryTotalKbytes": "8000000",
            "originalUrl": original_url,
            "osName": "X11",
            "osVersion": "",
            "platform": "DESKTOP",
            "remoteHost": "2003:d2:cf2b:a85e:517a:451f:a30d:fbf5",
            "screenDensityFloat": 1,
            "screenHeightPoints": 953,
            "screenPixelDensity": 1,
            "screenWidthPoints": 974,
            "timeZone": "Europe/Berlin",
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36,gzip(gfe)",
            "userInterfaceTheme": "USER_INTERFACE_THEME_DARK",
            "utcOffsetMinutes": 120,
            "visitorData": visitor_data
        },
        "request": {
            "internalExperimentFlags": [],
            "useSsl": True
        },
        "user": {
            "enableSafetyMode": False,
            "lockedSafetyMode": False
        }
    }


_fetch_visitor_data_uncached = _fetch_visitor_data


_visitor_cache = {"value": None, "time": 0}


def _fetch_visitor_data():
    now = time.time()
    if _visitor_cache["value"] and now - _visitor_cache["time"] < 3600:
        return _visitor_cache["value"]
    value = _fetch_visitor_data_uncached()
    if value and value != "0":
        _visitor_cache["value"] = value
        _visitor_cache["time"] = now
    return value

import re
import html
import requests
import xml.etree.ElementTree as ET

from .client import _fetch_visitor_data

_PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"
_ANDROID_UA = "com.google.android.youtube/21.26.364 (Linux; U; Android 11) gzip"


def _player_request(video_id, visitor_data):
    payload = {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "21.26.364",
                "androidSdkVersion": 30,
                "userAgent": _ANDROID_UA,
                "osName": "Android",
                "osVersion": "11",
                "hl": "en",
                "gl": "US",
                "visitorData": visitor_data,
            }
        },
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _ANDROID_UA,
        "X-Goog-Visitor-Id": visitor_data,
    }
    resp = requests.post(_PLAYER_URL, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_caption_tracks(video_id):
    try:
        visitor_data = _fetch_visitor_data()
        data = _player_request(video_id, visitor_data)
        tracks = (
            data.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )
        result = []
        for t in tracks:
            base_url = t.get("baseUrl", "")
            if not base_url:
                continue
            name = t.get("name", {})
            if "runs" in name and name["runs"]:
                label = name["runs"][0].get("text", "")
            else:
                label = name.get("simpleText", "")
            result.append({
                "languageCode": t.get("languageCode", ""),
                "name": label or t.get("languageCode", ""),
                "kind": t.get("kind", ""),
                "baseUrl": base_url,
            })
        return result
    except Exception as e:
        print(f"[youtubei] Error fetching caption tracks: {e}")
        return []


def _clean_text(raw):
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def fetch_caption_cues(base_url):
    try:
        resp = requests.get(
            base_url,
            headers={"User-Agent": _ANDROID_UA, "X-Goog-Visitor-Id": _fetch_visitor_data()},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.text
        if not body:
            return []

        cues = []
        root = ET.fromstring(body)
        for el in root.iter():
            if el.tag == "p":
                start = int(el.get("t", "0")) / 1000.0
                dur = int(el.get("d", "0")) / 1000.0
            elif el.tag == "text":
                start = float(el.get("start", "0"))
                dur = float(el.get("dur", "0"))
            else:
                continue
            inner = ET.tostring(el, encoding="unicode", method="xml")
            inner = re.sub(r"^<[^>]+>", "", inner, count=1)
            inner = re.sub(r"</[^>]+>\s*$", "", inner)
            text = _clean_text(inner)
            if text:
                cues.append({
                    "text": text,
                    "start": start,
                    "duration": dur if dur > 0 else 2.5,
                })
        return cues
    except Exception as e:
        print(f"[youtubei] Error fetching caption cues: {e}")
        return []
